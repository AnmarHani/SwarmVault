#!/usr/bin/env python3
"""
swarmvault.py — the SwarmVault CLI: one file, stock Python 3, zero dependencies.

The vault is a plain, Obsidian-compatible markdown tree that any number of parallel
agents (Claude Code, Codex, or both) read and write. This script is their interface:
one query returns the relevant notes' names + descriptions instead of a repo-wide
Glob/Grep/Read sweep, and one sync mirrors everything durable a session produced.

Subcommands
-----------
  query     --search "auth flow" [--project P] [--type T] [--tag G] [--folder F]
            [--limit N] [--format list|json|paths]     BM25-ranked or filtered listing
  show      <note-name-or-path>                        print one note's body
  context   [CWD]                                      compact per-project context block
  hook      (stdin: {"cwd": ...})                      SessionStart hook JSON; always exit 0
  sync      [--dry-run] [--quiet]                      mirror memory/docs/sessions, rebuild MOCs
  init      [--vault PATH]                             create a vault + config file
  register  [--path P] [--name N] [--isolated] [--import-claude] [--repair]
  claim     <TICKET-ID> --project P [--agent A] [--break-stale]
  release   <TICKET-ID> --project P [--done]
  plan-continue set|show|clear --project P [--resume-at ISO] [--scope S]
                                                       usage-limit continuation record
  board     --project P [--verbose] [--watch N]        cross-platform swarm view
  checkpoint --project P [--did ..] [--next ..]        safe-state note before compaction
  doctor                                               self-check: config, vault, adapters

Optional orchestration (FR-22/FR-24, disabled by default): signal / inbox / control /
orchestrate / supervisor / board — see the swarm-orchestrate skill.

Resolution (FR-02): vault path = $SWARMVAULT_HOME, else ~/.swarmvault.json {"vault": ...}.
Project identity = nearest `.swarmvault` marker walking up from cwd, else deepest
registry path prefix. The registry lives IN the vault (registry.json) so it works
identically on every platform — no ~/.claude.json dependency.

Concurrency (FR-04/FR-05): agents write only their own files; shared notes (MOCs, Home)
are regenerated only by sync, which serializes on a lock file and writes atomically
(temp + os.replace). Ticket claims are O_CREAT|O_EXCL — the filesystem is the referee.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Layout constants (FR-01) — the folder names ARE the schema; do not localize.
# ---------------------------------------------------------------------------
MAPS, PROJECTS, MEMORY, PLANS, SESSIONS, DECISIONS, TEMPLATES = (
    "00 Maps", "10 Projects", "20 Memory", "30 Plans", "40 Sessions",
    "50 Decisions", "90 Templates",
)
FOLDERS = (MAPS, PROJECTS, MEMORY, PLANS, SESSIONS, DECISIONS, TEMPLATES)

CONFIG_NAME = ".swarmvault.json"
MARKER_NAME = ".swarmvault"
REGISTRY_NAME = "registry.json"
LOCK_NAME = ".sync.lock"
LOCK_STALE_S = 600          # a sync lock older than this is a crash leftover
CLAIM_TTL_S = 2 * 3600      # default claim staleness (FR-05); config: claim_ttl_hours

# Context injection budget (chars). A guideline, not a cap: essentials are never
# dropped to satisfy the number (NFR-P2, amended). Config: context_budget.
CONTEXT_BUDGET = 3500

DOC_NAMES = ("CLAUDE.md", "README.md", "AGENTS.md", "CONTRIBUTING.md")
DOC_DIRS = ("docs", "references", "documentation")
SKIP_PARTS = {"node_modules", ".git", "dist", "build", ".next", "vendor"}
MAX_DOC_BYTES = 120_000

TOKEN_RE = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------------------
# Config & resolution (FR-02)
# ---------------------------------------------------------------------------
def home() -> Path:
    return Path(os.path.expanduser("~"))


def config_path() -> Path:
    return home() / CONFIG_NAME


def load_config() -> dict:
    try:
        cfg = json.loads(config_path().read_text(encoding="utf-8"))
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(update: dict) -> None:
    cfg = load_config()
    cfg.update(update)
    atomic_write(config_path(), json.dumps(cfg, indent=2) + "\n")


def vault_path() -> Path | None:
    env = os.environ.get("SWARMVAULT_HOME")
    if env:
        return Path(env)
    v = load_config().get("vault")
    return Path(v) if v else None


def require_vault() -> Path:
    v = vault_path()
    if not v or not v.is_dir():
        # Hooks and session-start paths must never hard-fail (NFR-R2); callers
        # that can error do so themselves.
        print("SwarmVault is not set up here — run: swarmvault.py init")
        raise SystemExit(0)
    return v


def registry_path(vault: Path) -> Path:
    return vault / REGISTRY_NAME


def load_registry(vault: Path) -> list[dict]:
    p = registry_path(vault)
    if not p.exists():
        return []
    try:
        reg = json.loads(p.read_text(encoding="utf-8"))
        return [e for e in reg if isinstance(e, dict) and e.get("name")] if isinstance(reg, list) else []
    except (OSError, json.JSONDecodeError):
        # Corrupt registry must not kill a session; report and continue empty (FR-02).
        print(f"warning: could not parse {p}; treating registry as empty", file=sys.stderr)
        return []


def save_registry(vault: Path, entries: list[dict]) -> None:
    atomic_write(registry_path(vault), json.dumps(sorted(entries, key=lambda e: e["name"]), indent=2) + "\n")


def find_marker(cwd: Path) -> str | None:
    """Nearest .swarmvault marker walking up — survives project moves (FR-02)."""
    cur = cwd.resolve()
    for d in [cur, *cur.parents]:
        m = d / MARKER_NAME
        if m.is_file():
            try:
                name = json.loads(m.read_text(encoding="utf-8")).get("project")
                if name:
                    return str(name)
            except (OSError, json.JSONDecodeError):
                pass
    return None


def resolve_project(vault: Path, cwd: str) -> dict | None:
    """cwd -> registry entry. Marker first, deepest registry-path prefix second."""
    reg = load_registry(vault)
    name = find_marker(Path(cwd))
    if name:
        for e in reg:
            if e["name"] == name:
                return e
    cwd_r = str(Path(cwd).resolve())
    best = None
    for e in reg:
        p = str(Path(e.get("path", "")).resolve()) if e.get("path") else ""
        if p and (cwd_r == p or cwd_r.startswith(p.rstrip("/") + "/")):
            if best is None or len(p) > len(str(best.get("path", ""))):
                best = e
    return best


# ---------------------------------------------------------------------------
# Frontmatter — a deliberate YAML subset so the vault needs zero pip installs
# (C-1). Covers everything the FR-01 templates use: scalars, quoted strings,
# ints, bools, inline + dashed lists, one nesting level. Anything stranger is
# tolerated as raw text; a note that won't parse becomes type "note" (FR-01).
# ---------------------------------------------------------------------------
def _parse_scalar(s: str):
    s = s.strip()
    if not s:
        return ""
    if s[0] in "\"'" and len(s) >= 2 and s[-1] == s[0]:
        return s[1:-1]
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _parse_inline_list(s: str) -> list:
    inner = s.strip()[1:-1].strip()
    return [_parse_scalar(x) for x in inner.split(",") if x.strip()] if inner else []


def parse_frontmatter_block(block: str) -> dict:
    out: dict = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):  # stray indentation with no parent key
            continue
        m = re.match(r"^([^:\s][^:]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2)
        # Strip trailing same-line comments only after quoted values are safe.
        if val and not val.lstrip().startswith(("\"", "'")):
            val = re.split(r"\s+#", val)[0]
        if val.strip():
            if val.strip().startswith("[") and val.strip().endswith("]"):
                out[key] = _parse_inline_list(val)
            else:
                out[key] = _parse_scalar(val)
            continue
        # Empty value: an indented dashed list or a one-level nested mapping follows.
        items, mapping = [], {}
        while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
            sub = lines[i].strip()
            i += 1
            if not sub:
                continue
            if sub.startswith("- "):
                items.append(_parse_scalar(sub[2:]))
            elif sub == "-":
                items.append("")
            else:
                sm = re.match(r"^([^:]+):\s*(.*)$", sub)
                if sm:
                    mapping[sm.group(1).strip()] = _parse_scalar(sm.group(2))
        out[key] = items if items else (mapping if mapping else "")
    return out


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter, body); malformed frontmatter degrades to ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        fm = parse_frontmatter_block(m.group(1))
    except Exception:
        return {}, text
    return (fm, m.group(2)) if fm else ({}, text)


def _dump_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    # Quote only when YAML would misread it — keeps files human-pleasant.
    if s == "" or re.search(r"[:#\[\]{}]|^[-?&*!|>%@`\"']|\s$|^\s", s):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def dump_frontmatter(fm: dict) -> str:
    lines = []
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")  # bare "k:" would read back as "", not []
                continue
            lines.append(f"{k}:")
            lines.extend(f"  - {_dump_scalar(x)}" for x in v)
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            lines.extend(f"  {sk}: {_dump_scalar(sv)}" for sk, sv in v.items())
        else:
            lines.append(f"{k}: {_dump_scalar(v)}")
    return "\n".join(lines) + "\n"


def render(fm: dict, body: str) -> str:
    return f"---\n{dump_frontmatter(fm)}---\n\n{body.lstrip()}"


# ---------------------------------------------------------------------------
# Atomic writes (NFR-R3) — every shared-file write in this script goes here.
# ---------------------------------------------------------------------------
def atomic_write(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + f".tmp{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dest)


# ---------------------------------------------------------------------------
# Note loading & classification (FR-01 / FR-03)
# ---------------------------------------------------------------------------
def note_type(fm: dict, tags: list) -> str:
    """swarm/* (or legacy claude/*) tag wins — sync sets it and it is the only
    field guaranteed to mean what we think it means. A note's own `type:` must
    not shadow it (silent omissions are the one failure a query tool can't have)."""
    for prefix in ("swarm/", "claude/"):
        for t in tags:
            if str(t).startswith(prefix):
                return str(t).split("/", 1)[1]
    if fm.get("type"):
        return str(fm["type"])
    meta = fm.get("metadata")
    if isinstance(meta, dict) and meta.get("type"):
        return str(meta["type"])
    return "note"


def load_notes(vault: Path) -> list[dict]:
    notes = []
    for p in sorted(vault.rglob("*.md")):
        if ".obsidian" in p.parts or ".trash" in p.parts:
            continue
        try:
            fm, body = split_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        notes.append({
            "path": p,
            "rel": p.relative_to(vault).as_posix(),
            "stem": p.stem,
            "name": str(fm.get("name") or p.stem),
            "desc": " ".join(str(fm.get("description") or "").split()),
            "project": str(fm["project"]) if fm.get("project") else None,
            "type": note_type(fm, tags),
            "tags": [str(t) for t in tags],
            "body": body,
            "fm": fm,
        })
    return notes


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) > 1]


def bm25(notes: list[dict], query: str) -> list[tuple[float, dict]]:
    """BM25 with field boosting: name/description hits count far more than body
    hits, because those fields are the curated summary."""
    q = tokenize(query)
    if not q:
        return [(0.0, n) for n in notes]
    docs = []
    for n in notes:
        text = " ".join([n["name"]] * 3 + [n["desc"]] * 3 + [" ".join(n["tags"])] * 2 + [n["body"]])
        docs.append(Counter(tokenize(text)))
    N = len(docs) or 1
    avgdl = sum(sum(d.values()) for d in docs) / N or 1.0
    df = Counter()
    for d in docs:
        for term in set(d) & set(q):
            df[term] += 1
    k1, b = 1.5, 0.75
    scored = []
    for n, d in zip(notes, docs):
        dl = sum(d.values()) or 1
        s = 0.0
        for term in q:
            f = d.get(term, 0)
            if not f:
                continue
            idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        if s > 0:
            scored.append((s, n))
    scored.sort(key=lambda x: (-x[0], x[1]["rel"]))
    return scored


def isolation_filter(notes: list[dict], vault: Path, current: str | None, explicit: str | None) -> list[dict]:
    """Cooperative isolation (NFR-S2): isolated projects appear only in their own
    context — when named via --project or when cwd resolves to them. Not a
    security boundary, and documented as such."""
    hidden = {e["name"] for e in load_registry(vault) if e.get("isolation") == "isolated"}
    hidden -= {n for n in (current, explicit) if n}
    return [n for n in notes if n["project"] not in hidden]


# ---------------------------------------------------------------------------
# query / show (FR-03)
# ---------------------------------------------------------------------------
def fmt_list(rows: list[dict], show_score: bool = False) -> str:
    if not rows:
        return "No matching notes."
    out = []
    for n in rows:
        tag = f"[{n['project']}/{n['type']}]" if n["project"] else f"[{n['type']}]"
        line = f"- {tag} {n['name']}"
        if show_score and "score" in n:
            line += f"  (score {n['score']:.1f})"
        out.append(line)
        if n["desc"]:
            out.append(f"    {n['desc']}")
        out.append(f"    `{n['rel']}`")
    return "\n".join(out)


def cmd_query(args) -> int:
    vault = require_vault()
    notes = load_notes(vault)
    if not notes:
        print("Vault is empty — run swarm-init on a project to start filling it.")
        return 0
    current = None
    if not args.project:
        cur = resolve_project(vault, os.getcwd())
        current = cur["name"] if cur else None
    rows = isolation_filter(notes, vault, current, args.project)
    if args.project:
        p = args.project.lower()
        rows = [n for n in rows if (n["project"] or "").lower() == p]
    if args.type:
        rows = [n for n in rows if n["type"].lower() == args.type.lower()]
    if args.tag:
        want = args.tag.lstrip("#").lower()
        rows = [n for n in rows if any(want == t.lower() or t.lower().startswith(want + "/") for t in n["tags"])]
    if args.folder:
        rows = [n for n in rows if n["rel"].lower().startswith(args.folder.lower())]

    total = len(rows)
    if args.search:
        rows = [dict(n, score=s) for s, n in bm25(rows, args.search)[: args.limit]]
        total = len(rows)
    else:
        rows = [dict(n) for n in rows[: args.limit]]

    if args.format == "json":
        print(json.dumps([
            {k: v for k, v in r.items() if k in ("rel", "name", "desc", "project", "type", "tags", "score")}
            for r in rows
        ], indent=2))
    elif args.format == "paths":
        print("\n".join(str(vault / r["rel"]) for r in rows))
    else:
        print(fmt_list(rows, show_score=bool(args.search)))
        if total > len(rows):
            print(f"\n({len(rows)} of {total} shown — raise --limit)")
    return 0


def cmd_show(args) -> int:
    vault = require_vault()
    key = args.note.lower()
    notes = load_notes(vault)
    hits = [n for n in notes if n["stem"].lower() == key or n["rel"].lower() == key or n["name"].lower() == key]
    if not hits:
        print(f"No note matching '{args.note}'.")
        return 1
    if len(hits) > 1:
        print(f"'{args.note}' is ambiguous — candidates:")
        for n in hits:
            print(f"  {n['rel']}")
        return 1
    n = hits[0]
    print(f"# {n['name']}  ({n['rel']})\n")
    print(n["body"].strip())
    return 0


# ---------------------------------------------------------------------------
# context / hook (FR-03) — the SessionStart payload. Budget is a guideline:
# whole low-value sections are trimmed first (oldest sessions), and essentials
# are kept even when that exceeds the number (NFR-P2, amended).
# ---------------------------------------------------------------------------
def build_context(vault: Path, project: str, notes: list[dict]) -> str:
    mem = [n for n in notes if n["project"] == project and n["type"] == "memory"]
    digest = [n for n in notes if n["project"] == project and n["type"] == "digest"]
    flow = [n for n in notes if n["project"] == project and n["stem"] == "flow-state"]
    sess = sorted(
        [n for n in notes if n["project"] == project and n["type"] == "session"],
        key=lambda n: str(n["fm"].get("date") or ""), reverse=True,
    )
    if not (mem or digest or sess or flow):
        return ""

    b = [f"## SwarmVault — {project}", ""]
    b.append(f"The vault has prior knowledge of this project — prefer it over re-scanning the repo. "
             f"Full map: `{PROJECTS}/{project}/{project} MOC.md`. "
             f"Query: `python3 {Path(__file__).resolve()} query --project {project}`.")
    b.append("")
    if flow:
        phase = flow[0]["fm"].get("phase") or flow[0]["desc"]
        if phase:
            b += [f"**Current phase:** {phase}", ""]
    cont = read_continuation(vault, project)
    if cont:
        b += [f"**⏳ Scheduled continuation:** resume at {cont.get('resume_at', '?')} "
              f"(scope: {cont.get('scope', 'until-finish')}) — {cont.get('reason', '')}. "
              f"If now is past that time, continue the work; if the project is finished, "
              f"clear it (`plan-continue clear --project {project}`).", ""]
    if digest:
        b += [f"**Architecture digest:** `{digest[0]['rel']}` — {digest[0]['desc']}", ""]
    if mem:
        b.append(f"**Memory ({len(mem)}):**")
        b += [f"- {n['name']} — {n['desc']}" if n["desc"] else f"- {n['name']}" for n in mem]
        b.append("")

    budget = int(load_config().get("context_budget") or CONTEXT_BUDGET)
    essentials = "\n".join(b)
    session_lines = [f"**Recent sessions:** " + "; ".join(n["name"] for n in sess[:3])] if sess else []
    text = "\n".join(b + session_lines)
    if len(text) > budget and session_lines:
        text = essentials  # drop the whole sessions line before touching memory
    # Still over? Keep it: essentials beat the budget by design (quality wins).
    return text


def cmd_context(args) -> int:
    vault = require_vault()
    proj = resolve_project(vault, args.cwd or os.getcwd())
    if proj:
        out = build_context(vault, proj["name"], load_notes(vault))
        if out:
            print(out)
    return 0


def cmd_hook(_args) -> int:
    """SessionStart hook: swallow everything, always exit 0 (NFR-R2)."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        vault = vault_path()
        if not vault or not vault.is_dir():
            return 0
        proj = resolve_project(vault, str(payload.get("cwd") or os.getcwd()))
        if proj:
            ctx = build_context(vault, proj["name"], load_notes(vault))
            if ctx:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "SessionStart", "additionalContext": ctx}}))
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Sync engine (FR-04) — a faithful generalization of the author's vault_sync.py.
# Idempotent by construction: write only on change, prune only `generated: true`
# notes whose source vanished, never touch human files.
# ---------------------------------------------------------------------------
class Stats:
    def __init__(self) -> None:
        self.written = 0
        self.skipped = 0
        self.pruned = 0

    def __str__(self) -> str:
        return f"{self.written} written, {self.skipped} unchanged, {self.pruned} pruned"


def encode_claude_dir(real_path: str) -> str:
    """Real path -> ~/.claude/projects dir name. Forward-only: '/' and '_' both
    map to '-', so decoding back is ambiguous; we only ever encode."""
    return real_path.replace("/", "-").replace("_", "-")


class Sync:
    def __init__(self, vault: Path, dry_run: bool = False) -> None:
        self.vault = vault
        self.dry = dry_run
        self.stats = Stats()

    def write(self, dest: Path, content: str) -> bool:
        if dest.exists() and dest.read_text(encoding="utf-8") == content:
            self.stats.skipped += 1
            return False
        if self.dry:
            print(f"  [dry-run] would write {dest.relative_to(self.vault)}")
        else:
            atomic_write(dest, content)
        self.stats.written += 1
        return True

    def prune(self, folder: Path, keep: set[Path]) -> None:
        if not folder.exists():
            return
        for f in folder.rglob("*.md"):
            if f in keep:
                continue
            fm, _ = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            if fm.get("generated") is True:
                if not self.dry:
                    f.unlink()
                self.stats.pruned += 1

    # -- sources ------------------------------------------------------------
    def memory_sources(self, proj: dict) -> list[Path]:
        """Claude Code's per-project memory dir, plus the platform-neutral
        <project>/.swarm/memory/ that Codex (or any) agents write to."""
        out = []
        claude = home() / ".claude" / "projects" / encode_claude_dir(proj["path"]) / "memory"
        if claude.is_dir():
            out.append(claude)
        local = Path(proj["path"]) / ".swarm" / "memory"
        if local.is_dir():
            out.append(local)
        return out

    def sync_memory(self, proj: dict) -> list[dict]:
        name = proj["name"]
        dest_dir = self.vault / MEMORY / name
        titles, keep = [], set()
        for src in self.memory_sources(proj):
            for f in sorted(src.glob("*.md")):
                text = f.read_text(encoding="utf-8", errors="replace")
                fm, body = split_frontmatter(text)
                # MEMORY.md is an index, not a memory — rename so the graph
                # doesn't show identical "MEMORY" nodes for every project.
                is_index = f.name == "MEMORY.md"
                out_name = f"{name} Memory Index.md" if is_index else f.name
                fm["project"] = name
                fm["source"] = str(f)
                fm["generated"] = True
                kind = "index" if is_index else "memory"
                fm["tags"] = sorted({f"swarm/{kind}", f"project/{name}"})
                if is_index and "name" not in fm:
                    fm["name"] = f"{name} Memory Index"
                dest = dest_dir / out_name
                keep.add(dest)
                self.write(dest, render(fm, body))
                if not is_index:
                    titles.append({
                        "link": f"{MEMORY}/{name}/{f.stem}",
                        "label": str(fm.get("name") or f.stem),
                        # The description is the MOC's whole point: it conveys the
                        # project's knowledge without opening a single note.
                        "desc": " ".join(str(fm.get("description") or "").split()),
                    })
        self.prune(dest_dir, keep)
        return titles

    def _mirror_doc(self, f: Path, dest: Path, proj: dict, keep: set) -> bool:
        if not f.is_file() or f.stat().st_size > MAX_DOC_BYTES:
            return False
        _, body = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        fm = {
            "project": proj["name"],
            "source": str(f),
            "generated": True,
            "tags": sorted({"swarm/doc", f"project/{proj['name']}"}),
        }
        keep.add(dest)
        self.write(dest, render(fm, body))
        return True

    def sync_docs(self, proj: dict) -> list[str]:
        root = Path(proj["path"])
        name = proj["name"]
        dest_dir = self.vault / PROJECTS / name / "Docs"
        found, keep = [], set()
        for doc in DOC_NAMES:
            f = root / doc
            dest = dest_dir / f"{name} {f.stem}.md"
            if self._mirror_doc(f, dest, proj, keep):
                found.append(f"{PROJECTS}/{name}/Docs/{dest.stem}|{f.name}")
        for d in DOC_DIRS:
            tree = root / d
            if not tree.is_dir():
                continue
            for f in sorted(tree.rglob("*.md")):
                if SKIP_PARTS & set(f.parts):
                    continue
                rel = f.relative_to(root)
                dest = dest_dir / rel
                if self._mirror_doc(f, dest, proj, keep):
                    found.append(f"{PROJECTS}/{name}/Docs/{rel.with_suffix('')}|{rel}")
        self.prune(dest_dir, keep)
        return found

    def sync_sessions(self, proj: dict) -> list[str]:
        """Claude Code JSONL transcripts -> compact metadata notes (never the
        transcript). Codex agents journal directly into 40 Sessions instead —
        write-isolation makes both paths safe."""
        claude_dir = home() / ".claude" / "projects" / encode_claude_dir(proj["path"])
        name = proj["name"]
        dest_dir = self.vault / SESSIONS / name
        rows, keep = [], set()
        if claude_dir.is_dir():
            for f in sorted(claude_dir.glob("*.jsonl")):
                s = read_session(f)
                if not s:
                    continue
                safe = re.sub(r'[<>:"/\\|?*\[\]#^]', "", s["title"]).strip()[:60] or s["id"][:8]
                stamp = s["date"].strftime("%Y-%m-%d")
                fm = {
                    "project": name,
                    "session_id": s["id"],
                    "date": stamp,
                    "generated": True,
                    "tags": sorted({"swarm/session", f"project/{name}"}),
                }
                body = (
                    f"# {s['title']}\n\n"
                    f"Session on **{s['date'].strftime('%Y-%m-%d %H:%M')}** in "
                    f"[[{PROJECTS}/{name}/{name} MOC|{name}]] "
                    f"— {s['n_user']} prompts, {s['n_asst']} replies.\n\n"
                )
                if s["kickoff"]:
                    body += f"## Kickoff\n\n> {s['kickoff']}\n\n"
                body += f"## Transcript\n\n`{f}`\n\n*(Not mirrored — read on demand to keep the vault compact.)*\n"
                dest = dest_dir / f"{stamp} {safe}.md"
                keep.add(dest)
                self.write(dest, render(fm, body))
                rows.append((stamp, f"{SESSIONS}/{name}/{dest.stem}|{s['title']}"))
        # Agent-journaled session notes (not generated) are kept as-is; list them too.
        if dest_dir.is_dir():
            for f in sorted(dest_dir.glob("*.md")):
                if f in keep:
                    continue
                fm, _ = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if fm.get("generated") is not True:
                    rows.append((str(fm.get("date") or ""), f"{SESSIONS}/{name}/{f.stem}|{f.stem}"))
        self.prune(dest_dir, keep)
        return [link for _, link in sorted(rows, reverse=True)]

    # -- MOCs ----------------------------------------------------------------
    def project_moc(self, proj: dict, mem: list[dict], docs: list[str], sess: list[str]) -> None:
        name = proj["name"]
        fm = {
            "project": name,
            "type": "moc",
            "generated": True,
            "tags": sorted({"swarm/moc", f"project/{name}"}),
        }
        b = [f"# {name}", "", f"Map of Content for `{proj['path']}`.", ""]
        if g := git_info(proj["path"]):
            b += [g, ""]
        b += ["> [!tip] Start here"]
        # A digest is hand- or skill-authored (not `generated`) so it survives sync.
        if (self.vault / PROJECTS / name / f"{name} Digest.md").exists():
            b += [f"> Architecture digest: [[{PROJECTS}/{name}/{name} Digest|{name} Digest]]"]
        b += [f"> Human notes: [[{PROJECTS}/{name}/{name} Notes|{name} Notes]]", ""]
        b += [f"## Memory ({len(mem)})", ""]
        b += [f"- [[{m['link']}|{m['label']}]]" + (f" — {m['desc']}" if m["desc"] else "") for m in mem] \
             or ["*No memories yet.*"]
        b += ["", f"## Docs ({len(docs)})", ""]
        b += [f"- [[{l}]]" for l in docs] or ["*No docs mirrored.*"]
        b += ["", f"## Sessions ({len(sess)})", ""]
        b += [f"- [[{l}]]" for l in sess[:15]] or ["*No sessions recorded.*"]
        if len(sess) > 15:
            b += [f"- *…and {len(sess) - 15} older.*"]
        b += ["", "---", f"Back to [[{MAPS}/Home|Home]]", ""]
        self.write(self.vault / PROJECTS / name / f"{name} MOC.md", render(fm, "\n".join(b)))

        # Human-owned companion: created once, never overwritten (no `generated`).
        notes = self.vault / PROJECTS / name / f"{name} Notes.md"
        if not notes.exists() and not self.dry:
            atomic_write(notes, render(
                {"project": name, "tags": [f"project/{name}"]},
                f"# {name} Notes\n\nYour notes. This file is yours — sync never overwrites it.\n",
            ))

    def home_moc(self, rows: list[dict]) -> None:
        fm = {"type": "moc", "generated": True, "tags": ["swarm/moc"]}
        ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
        b = [
            "# Home", "",
            "Root map of every project in the SwarmVault. Regenerated by `swarmvault.py sync`.", "",
            f"*Last sync: {ts}*", "",
            "## Projects", "",
            "| Project | Memory | Docs | Sessions |",
            "|---|--:|--:|--:|",
        ]
        for r in rows:
            link = f"[[{PROJECTS}/{r['name']}/{r['name']} MOC|{r['name']}]]"
            b.append(f"| {link} | {r['mem']} | {r['docs']} | {r['sess']} |")
        if rows:
            tot = {k: sum(r[k] for r in rows) for k in ("mem", "docs", "sess")}
            b.append(f"| **Total** | **{tot['mem']}** | **{tot['docs']}** | **{tot['sess']}** |")
        b += [
            "", "## Folders", "",
            f"- `{MAPS}` — entry points",
            f"- `{PROJECTS}` — per-project MOCs, docs, your notes",
            f"- `{MEMORY}` — the agents' memory graph",
            f"- `{PLANS}` — specs, plans, tickets, question queues",
            f"- `{SESSIONS}` — work journal",
            f"- `{DECISIONS}` — ADRs",
            f"- `{TEMPLATES}` — note templates", "",
        ]
        self.write(self.vault / MAPS / "Home.md", render(fm, "\n".join(b)))

    def run(self, quiet: bool = False) -> Stats:
        rows = []
        for proj in load_registry(self.vault):
            if not proj.get("path") or not Path(proj["path"]).is_dir():
                print(f"warning: {proj['name']} path missing, skipped", file=sys.stderr)
                continue
            mem = self.sync_memory(proj)
            docs = self.sync_docs(proj)
            sess = self.sync_sessions(proj)
            self.project_moc(proj, mem, docs, sess)
            rows.append({"name": proj["name"], "mem": len(mem), "docs": len(docs), "sess": len(sess)})
            if not quiet:
                print(f"  {proj['name']:<22} memory:{len(mem):>3}  docs:{len(docs):>2}  sessions:{len(sess):>3}")
        self.home_moc(rows)
        return self.stats


def read_session(f: Path) -> dict | None:
    """Compact metadata from a Claude Code JSONL transcript — never the content."""
    title, kickoff, n_user, n_asst = None, None, 0, 0
    try:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = o.get("type")
                if t == "ai-title" and o.get("aiTitle"):
                    title = o["aiTitle"]
                elif t == "user":
                    n_user += 1
                    if kickoff is None:
                        kickoff = extract_text(o)
                elif t == "assistant":
                    n_asst += 1
    except OSError:
        return None
    if not (title or kickoff):
        return None
    return {
        "id": f.stem,
        "title": title or (kickoff or "")[:60] or f.stem,
        "kickoff": kickoff,
        "n_user": n_user,
        "n_asst": n_asst,
        "date": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).astimezone(),
    }


def extract_text(o: dict) -> str | None:
    msg = o.get("message")
    if not isinstance(msg, dict):
        return None
    c = msg.get("content")
    if isinstance(c, str):
        text = c
    elif isinstance(c, list):
        parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        text = " ".join(p for p in parts if p)
    else:
        return None
    text = " ".join(text.split())
    # Harness-injected context isn't a user intent; skip it.
    if not text or text.startswith(("<command-", "<local-command", "Caveat:", "<system-reminder")):
        return None
    return text[:300]


def git_info(path: str) -> str | None:
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", path, "log", "-1", "--format=%cd|%s", "--date=short"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        date, _, subject = r.stdout.strip().partition("|")
        return f"Last commit **{date}** — {subject[:80]}"
    except Exception:
        return None


def cmd_sync(args) -> int:
    vault = require_vault()
    lock = vault / LOCK_NAME
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        # A concurrent sync is running — skipping is correct (the next trigger
        # catches up), unless the lock is a crash leftover.
        try:
            age = time.time() - lock.stat().st_mtime
        except OSError:
            age = 0.0
        if age < LOCK_STALE_S:
            if not args.quiet:
                print("sync: another sync holds the lock — skipped")
            return 0
        print(f"sync: breaking stale lock ({int(age)}s old)", file=sys.stderr)
        try:
            lock.unlink()
        except OSError:
            return 0
        return cmd_sync(args)
    try:
        stats = Sync(vault, dry_run=args.dry_run).run(quiet=args.quiet)
        if not args.quiet:
            print(f"sync: {stats}")
    finally:
        try:
            lock.unlink()
        except OSError:
            pass
    return 0


# ---------------------------------------------------------------------------
# Ticket claims (FR-05) — O_CREAT|O_EXCL makes the filesystem the referee, so
# exactly one of N racing agents wins. No locks are held while working.
# ---------------------------------------------------------------------------
def tickets_dir(vault: Path, project: str) -> Path:
    return vault / PLANS / project / "tickets"


def _claim_age(claim: Path) -> float | None:
    """Claim age in seconds, or None if it vanished mid-look (TOCTOU-safe)."""
    try:
        return time.time() - claim.stat().st_mtime
    except OSError:
        return None


def cmd_claim(args) -> int:
    vault = require_vault()
    tdir = tickets_dir(vault, args.project)
    matches = list(tdir.glob(f"{args.ticket}*.md"))
    if not matches:
        print(f"error: no ticket {args.ticket} under {tdir}")
        return 1
    claim = tdir / f"{args.ticket}.claim"

    def try_create() -> bool:
        try:
            fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        os.write(fd, json.dumps({
            "agent": args.agent,
            "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pid": os.getpid(),
        }).encode())
        os.close(fd)
        return True

    if try_create():
        print(f"claimed {matches[0].name}")
        return 0

    try:
        info = json.loads(claim.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        info = {}
    age = _claim_age(claim)
    if age is None:  # holder released between our create and our look — one retry
        if try_create():
            print(f"claimed {matches[0].name}")
            return 0
        print("lost the race — another agent claimed it first")
        return 1

    ttl = float(load_config().get("claim_ttl_hours") or CLAIM_TTL_S / 3600) * 3600
    if age <= ttl or not args.break_stale:
        holder = info.get("agent", "unknown")
        state = "STALE — re-run with --break-stale to take over" if age > ttl else "active"
        print(f"already claimed by {holder} ({state})")
        return 1

    # Breaking a stale claim: breakers serialize on a break-lock, and staleness is
    # RE-VERIFIED under that lock — otherwise a second breaker that also saw "stale"
    # could unlink the winner's fresh claim (two winners; found by the M1 race test).
    brk = tdir / f"{args.ticket}.claim.break"
    try:
        os.close(os.open(brk, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        try:
            if time.time() - brk.stat().st_mtime > LOCK_STALE_S:
                brk.unlink()  # crashed breaker; cleared for the next attempt
        except OSError:
            pass
        print("another agent is breaking this stale claim — stand down")
        return 1
    try:
        age = _claim_age(claim)
        if age is not None and age > ttl:
            with matches[0].open("a", encoding="utf-8") as fh:
                fh.write(f"\n> claim by `{info.get('agent', '?')}` went stale "
                         f"({int(age / 60)} min); broken by `{args.agent}`.\n")
            try:
                claim.unlink()
            except FileNotFoundError:
                pass
        won = try_create()
    finally:
        try:
            brk.unlink()
        except OSError:
            pass
    if won:
        print(f"claimed {matches[0].name} (stale claim broken)")
        return 0
    print("lost the race — another agent claimed it first")
    return 1


def cmd_release(args) -> int:
    vault = require_vault()
    tdir = tickets_dir(vault, args.project)
    claim = tdir / f"{args.ticket}.claim"
    if args.done:
        matches = list(tdir.glob(f"{args.ticket}*.md"))
        if matches:
            fm, body = split_frontmatter(matches[0].read_text(encoding="utf-8"))
            fm["status"] = "done"
            atomic_write(matches[0], render(fm, body))
            print(f"{matches[0].name}: status -> done")
    if claim.exists():
        claim.unlink()
        print("claim released")
    return 0


# ---------------------------------------------------------------------------
# Optional orchestration supervisor (FR-22). It is disabled unless explicitly
# enabled. Tickets/claims remain the ownership authority; these files only
# coordinate workers and leave an auditable, cross-platform trail.
# ---------------------------------------------------------------------------
def orchestration_dir(vault: Path, project: str) -> Path:
    return vault / PLANS / project / "orchestration"


def _json_read(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def _json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _orchestration_config(root: Path) -> dict:
    path = root / "config.json"
    cfg = _json_read(path, {})
    if not path.exists():
        cfg = {"enabled": False, "interval_seconds": 60, "heartbeat_ttl_seconds": 180}
        _json_write(path, cfg)
    return cfg


def _event(root: Path, agent: str, event: str, **extra) -> Path:
    data = {"agent": agent, "event": event,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}
    dest = root / "signals" / agent / f"{time.time_ns()}-{uuid.uuid4().hex[:8]}.json"
    _json_write(dest, data)
    return dest


def _latest_agents(root: Path) -> dict:
    """Latest *work* status per agent. Budget reports are platform telemetry
    (tracked by _latest_budgets), not a change in what an agent is doing, so they
    never overwrite a worker's real work state."""
    latest = {}
    for path in (root / "signals").glob("*/*.json") if (root / "signals").exists() else []:
        data = _json_read(path, {})
        agent = data.get("agent")
        if data.get("event") == "budget":
            continue
        if agent and (agent not in latest or path.name > latest[agent][0].name):
            latest[agent] = (path, data)
    return {agent: data for agent, (_, data) in latest.items()}


def _leader(root: Path, agent: str, ttl: int) -> bool:
    """Acquire/renew a leader lease. Expired leases are broken under an O_EXCL lock."""
    lease, lock = root / "leader.lease", root / "leader.break"
    now = time.time()
    mine = {"agent": agent, "expires_at": now + ttl,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        fd = os.open(lease, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, json.dumps(mine).encode()); os.close(fd)
        return True
    except FileExistsError:
        old = _json_read(lease, {})
    if old.get("agent") == agent:
        _json_write(lease, mine)
        return True
    if float(old.get("expires_at", 0) or 0) > now:
        return False
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    try:
        old = _json_read(lease, {})
        if float(old.get("expires_at", 0) or 0) <= time.time():
            try: lease.unlink()
            except FileNotFoundError: pass
        try:
            fd = os.open(lease, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps(mine).encode()); os.close(fd)
            return True
        except FileExistsError:
            return False
    finally:
        try: lock.unlink()
        except OSError: pass


def _open_tickets(vault: Path, project: str) -> list[tuple[str, dict]]:
    result = []
    for path in tickets_dir(vault, project).glob("*.md") if tickets_dir(vault, project).exists() else []:
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("status", "open") == "open":
            result.append((path.stem.split("-", 2)[0] + "-" + path.stem.split("-", 2)[1] if path.stem.startswith("TK-") else path.stem, fm))
    return result


def _pending_control(root: Path, agent: str) -> bool:
    for path in (root / "control" / agent).glob("*.json") if (root / "control" / agent).exists() else []:
        if _json_read(path, {}).get("status", "pending") == "pending":
            return True
    return False


def _write_status(root: Path, project: str, leader: str, agents: dict, stale: list[str], queued: list[dict]) -> dict:
    state = {"project": project, "leader": leader, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "agents": agents, "stale_agents": stale, "queued_controls": queued}
    _json_write(root / "status.json", state)
    lines = [f"# Orchestration status — {project}", "", f"Leader: `{leader}`", "",
             f"Active agents: {', '.join(sorted(agents)) or 'none'}", f"Stale agents: {', '.join(stale) or 'none'}",
             f"Queued controls: {len(queued)}"]
    atomic_write(root / "status.md", "\n".join(lines) + "\n")
    return state


# Launch adapters. A declarative registry: each entry builds the argv for a
# headless, non-interactive worker. `claude-code` and `codex` are verified; the
# rest are best-effort defaults for fast-moving CLIs — confirm the flags against
# your installed version, or override per project with `configure --launch-cmd`.
# Read-only headless launch is offered ONLY where a real read/plan mode is known,
# so a read-only request can never accidentally start a writing agent; every other
# adapter launches only with explicit --allow-write. A brand-new or unlisted agent
# is wired with a `launch_cmd` template. Tokens: {cwd} {model} {prompt}. Unknown
# platform under the requested mode -> the supervisor records a manual action
# instead of guessing.
ADAPTERS: dict[str, dict] = {
    "claude-code": {"bin": "claude", "verified": True,
        "args": ["-p", "--output-format", "json"], "model": ["--model", "{model}"],
        "write": ["--permission-mode", "acceptEdits"], "read": ["--permission-mode", "plan"],
        "prompt": ["{prompt}"]},
    "codex": {"bin": "codex", "verified": True,
        "args": ["exec", "-C", "{cwd}"], "model": ["-m", "{model}"],
        "write": ["-s", "workspace-write", "-a", "never"],
        "read": ["-s", "read-only", "-a", "never"], "prompt": ["{prompt}"]},
    # Best-effort — verify flags for your installed version, or set --launch-cmd:
    "gemini": {"bin": "gemini", "verified": False,
        "args": [], "model": ["-m", "{model}"], "write": ["--yolo"], "prompt": ["-p", "{prompt}"]},
    "opencode": {"bin": "opencode", "verified": False,
        "args": ["run"], "model": ["-m", "{model}"], "write": [], "prompt": ["{prompt}"]},
    "droid": {"bin": "droid", "verified": False,
        "args": ["exec"], "write": [], "prompt": ["{prompt}"]},
    "cursor": {"bin": "cursor-agent", "verified": False,
        "args": ["-p"], "model": ["-m", "{model}"], "write": ["--force"], "prompt": ["{prompt}"]},
    "copilot": {"bin": "copilot", "verified": False,
        "args": [], "model": ["--model", "{model}"], "write": ["--allow-all-tools"],
        "prompt": ["-p", "{prompt}"]},
}


def _subst(tokens: list[str], mapping: dict) -> list[str]:
    return [mapping.get(t[1:-1], t) if t[:1] == "{" and t[-1:] == "}" else t for t in tokens]


def build_launch_argv(platform: str, adapter: dict, cwd: str, prompt: str,
                      model: str | None, allow_write: bool) -> list[str] | None:
    """Argv to spawn a headless worker, or None if this platform can't be launched
    under the requested write mode (the caller then records a manual action)."""
    mapping = {"cwd": cwd, "model": model or "", "prompt": prompt}
    override = adapter.get("launch_cmd")
    if override:  # the user vouches for their own template; it can wire ANY agent
        return [a for a in _subst(shlex.split(override), mapping) if a != ""]
    spec = ADAPTERS.get(platform)
    if not spec:
        return None
    mode = spec.get("write") if allow_write else spec.get("read")
    if mode is None:  # requested mode unsupported for this adapter -> manual
        return None
    argv = [spec["bin"], *_subst(spec.get("args", []), mapping)]
    if model and spec.get("model"):
        argv += _subst(spec["model"], mapping)
    argv += _subst(mode, mapping)
    argv += _subst(spec.get("prompt", ["{prompt}"]), mapping)
    return argv


def _launch_worker(vault: Path, project: str, root: Path, platform: str, ticket: str, fm: dict,
                   cfg: dict, model: str | None = None) -> str | None:
    """Launch one explicitly configured headless CLI worker without a shell.
    `model` overrides the adapter default (the scheduler passes a kind-matched one)."""
    adapter = (cfg.get("adapters") or {}).get(platform, {})
    if not adapter.get("enabled"):
        return None
    entry = next((e for e in load_registry(vault) if e.get("name") == project), None)
    if not entry or not Path(entry.get("path", "")).is_dir():
        return None
    worker = f"{platform}-{uuid.uuid4().hex[:10]}"
    script = str(Path(__file__).resolve())
    prompt = (f"You are SwarmVault worker {worker}. Work only ticket {ticket} in project {project}. "
              f"First run: python3 {script} signal --project {project} --agent {worker} --event registered --platform {platform} --ticket {ticket}. "
              f"Claim it with: python3 {script} claim {ticket} --project {project} --agent {worker}. "
              "Read the ticket context, implement and test its DoD. Signal progress at meaningful checkpoints; "
              "on completion release with --done and signal done; on a real blocker signal blocked with a reason.")
    model = model or adapter.get("model")
    allow_write = bool(adapter.get("allow_write"))
    command = build_launch_argv(platform, adapter, str(entry["path"]), prompt, model, allow_write)
    if command is None:
        _event(root, f"{platform}-manual", "blocked", platform=platform, ticket=ticket,
               reason=(f"no launch adapter for '{platform}' under "
                       f"{'write' if allow_write else 'read-only'} mode; start it manually or set "
                       "launch_cmd via `supervisor configure --launch-cmd`"))
        return None
    log = (root / "logs" / f"{worker}.log"); log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        proc = subprocess.Popen(command, cwd=str(entry["path"]), stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    _json_write(root / "processes" / f"{worker}.json", {"agent": worker, "platform": platform, "ticket": ticket,
                "pid": proc.pid, "model": model or "", "tier": fm.get("tier", "mid"),
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "log": str(log), "prompt": prompt})
    _event(root, worker, "registered", platform=platform, ticket=ticket, tier=fm.get("tier", "mid"), model=model or "")
    return worker


# Smart assignment (FR-24): match runnable tickets to (platform, model) by task
# size, per-platform remaining usage budget, and per-kind model strength. Pure and
# testable; the judgment (which model is strong at what) lives in config + the
# model-routing reference, not hardcoded here.
_SIZE_RANK = {"top": 3, "mid": 2, "small": 1}
TASK_KINDS = ("design", "planning", "coding", "review", "docs")


def _budget_bucket(frac: float | None) -> str:
    if frac is None: return "unknown"
    if frac <= 0.02: return "empty"
    if frac >= 0.5: return "high"
    if frac >= 0.2: return "medium"
    return "low"


def _budget_frac(budgets: dict, platform: str, default: float | None = None) -> float | None:
    f = (budgets.get(platform) or {}).get("fraction")
    return default if f is None else f


def _model_for(adapter: dict, kind: str, tier: str) -> str:
    """Strongest configured model for this task kind: explicit per-kind map wins,
    then per-tier, then the platform's default model."""
    models = adapter.get("models") or {}
    return models.get(kind) or models.get(tier) or adapter.get("model") or ""


def _latest_budgets(root: Path) -> dict:
    """Latest reported remaining-usage budget per platform (from `budget` or
    `quota-wait` signals). Unreported platforms are simply unknown, never assumed."""
    latest: dict[str, tuple[str, dict]] = {}
    paths = (root / "signals").glob("*/*.json") if (root / "signals").exists() else []
    for path in paths:
        d = _json_read(path, {})
        plat = d.get("platform")
        if not plat or ("budget" not in d and d.get("event") != "quota-wait"):
            continue
        if plat not in latest or path.name > latest[plat][0]:
            latest[plat] = (path.name, d)
    out = {}
    for plat, (_, d) in latest.items():
        frac = d.get("budget")
        if frac is None and d.get("event") == "quota-wait":
            frac = 0.0
        out[plat] = {"fraction": frac, "reset": d.get("retry_at"), "at": d.get("at"),
                     "used": d.get("used"), "limit": d.get("limit"), "unit": d.get("unit"),
                     "weekly": d.get("weekly"), "weekly_reset": d.get("weekly_reset")}
    return out


def plan_assignments(tickets: list[dict], adapters: dict, budgets: dict,
                     running_by: dict) -> tuple[list[dict], list[dict]]:
    """Biggest tasks first, to the platform with the MOST remaining budget; small
    tasks to the LEAST (preserve headroom for big work); empty/quota platforms are
    skipped; the model is the strongest configured for the task kind. Applies to a
    single platform too — it just picks the right model per task and stops when its
    budget is empty. Returns (assignments, deferred)."""
    caps = {p: int(a.get("max_workers", 0)) - int(running_by.get(p, 0))
            for p, a in adapters.items() if a.get("enabled")}
    plan, deferred = [], []

    def fits(p, kind):  # platform has a model explicitly configured for this kind
        return 1 if (adapters[p].get("models") or {}).get(kind) else 0

    for tk in sorted(tickets, key=lambda t: (-_SIZE_RANK.get(t.get("tier", "mid"), 2), t.get("id", ""))):
        tier = tk.get("tier", "mid")
        kind = tk.get("kind") or "coding"
        big = _SIZE_RANK.get(tier, 2) >= 2
        usable = [p for p, c in caps.items()
                  if c > 0 and _budget_bucket(_budget_frac(budgets, p)) != "empty"]
        if not usable:
            deferred.append({"ticket": tk.get("id"), "reason": "no platform with capacity and budget"})
            continue
        if big:
            # capability first (right model for the kind), then most remaining budget
            usable.sort(key=lambda p: (fits(p, kind), _budget_frac(budgets, p, default=0.4), p), reverse=True)
        else:
            # small work → least budget (reserve high-budget platforms for big tasks)
            usable.sort(key=lambda p: (_budget_frac(budgets, p, default=0.4), -fits(p, kind), p))
        plat = usable[0]
        bucket = _budget_bucket(_budget_frac(budgets, plat))
        why = ("capability+budget" if big and fits(plat, kind) else
               "budget headroom" if big else "reserved for small work")
        plan.append({"ticket": tk.get("id"), "platform": plat,
                     "model": _model_for(adapters[plat], kind, tier), "kind": kind,
                     "size": tier, "budget": bucket,
                     "reason": f"{'large' if big else 'small'} {kind} task → {plat} ({why}, budget {bucket})"})
        caps[plat] -= 1
    return plan, deferred


def reconcile(vault: Path, project: str, agent: str) -> tuple[int, dict]:
    root = orchestration_dir(vault, project); root.mkdir(parents=True, exist_ok=True)
    cfg = _orchestration_config(root)
    if not _leader(root, agent, max(30, int(cfg.get("heartbeat_ttl_seconds", 180)))):
        return 1, {"error": "another healthy leader holds the lease"}
    for procfile in list((root / "processes").glob("*.json")) if (root / "processes").exists() else []:
        proc = _json_read(procfile, {}); pid = int(proc.get("pid", 0) or 0)
        try:
            os.kill(pid, 0)
        except OSError:
            _event(root, proc.get("agent", "unknown"), "blocked", platform=proc.get("platform", ""),
                   ticket=proc.get("ticket", ""), reason="launched process exited; inspect worker log")
            try: procfile.unlink()
            except OSError: pass
    agents = _latest_agents(root)
    now = time.time(); ttl = int(cfg.get("heartbeat_ttl_seconds", 180)); stale = []
    active = {}
    for ident, data in agents.items():
        try: age = now - datetime.fromisoformat(data["at"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError): age = ttl + 1
        if data.get("event") not in {"done", "stopped", "quota-wait"} and age > ttl:
            stale.append(ident)
        else: active[ident] = data
    queued = []
    # Dispatch is a durable request only. Workers retain exclusive ownership by claiming.
    idle = [a for a, d in active.items()
            if d.get("event") in {"registered", "heartbeat", "done"} and not _pending_control(root, a)]
    for ticket, fm in _open_tickets(vault, project):
        if not idle: break
        if (tickets_dir(vault, project) / f"{ticket}.claim").exists(): continue
        worker = idle.pop(0)
        control = {"status": "pending", "action": "claim", "ticket": ticket, "tier": fm.get("tier", "mid"),
                   "issued_by": agent, "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        _json_write(root / "control" / worker / f"{time.time_ns()}-{ticket}.json", control)
        queued.append({"agent": worker, **control})
    # No registered idle worker? Launch enabled adapters, but choose platform+model
    # smartly: biggest tasks to the most-budget platform, model matched to task kind.
    if cfg.get("enabled") and not idle:
        procs = ([_json_read(p, {}) for p in (root / "processes").glob("*.json")]
                 if (root / "processes").exists() else [])
        running_by = Counter(p.get("platform") for p in procs)
        adapters = {k: v for k, v in (cfg.get("adapters") or {}).items() if v.get("enabled")}
        budgets = _latest_budgets(root)
        open_tks = [{"id": t, "tier": fm.get("tier", "mid"), "kind": fm.get("kind")}
                    for t, fm in _open_tickets(vault, project)
                    if not (tickets_dir(vault, project) / f"{t}.claim").exists()]
        assignments, _deferred = plan_assignments(open_tks, adapters, budgets, running_by)
        for a in assignments:
            worker = _launch_worker(vault, project, root, a["platform"], a["ticket"],
                                    {"tier": a["size"], "kind": a["kind"]}, cfg, model=a["model"])
            if worker:
                queued.append({"agent": worker, "action": "launch", "ticket": a["ticket"],
                               "platform": a["platform"], "model": a["model"], "reason": a["reason"]})
    return 0, _write_status(root, project, agent, active, stale, queued)


def cmd_signal(args) -> int:
    root = orchestration_dir(require_vault(), args.project); root.mkdir(parents=True, exist_ok=True)
    extra = {k: v for k, v in {"platform": args.platform, "ticket": args.ticket, "tier": args.tier,
             "model": args.model, "reason": args.reason, "retry_at": args.retry_at}.items() if v}
    if args.budget is not None:  # 0.0 is meaningful (empty), so don't drop it by falsiness
        extra["budget"] = args.budget
    for k in ("used", "limit", "unit", "weekly", "weekly_reset"):
        v = getattr(args, k, None)
        if v is not None:
            extra[k] = v
    print(_event(root, args.agent, args.event, **extra))
    return 0


def cmd_inbox(args) -> int:
    root = orchestration_dir(require_vault(), args.project)
    paths = sorted((root / "control" / args.agent).glob("*.json")) if (root / "control" / args.agent).exists() else []
    if args.ack:
        matches = [p for p in paths if p.name == args.ack or p.stem == args.ack]
        if not matches:
            print("error: control request not found"); return 1
        data = _json_read(matches[0], {}); data["status"] = "acknowledged"; data["acknowledged_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _json_write(matches[0], data); _event(root, args.agent, "progress", reason=f"acknowledged {matches[0].name}")
        print(matches[0].name); return 0
    items = [_json_read(p, {}) | {"id": p.name} for p in paths if _json_read(p, {}).get("status", "pending") == "pending"]
    print(json.dumps(items, indent=2))
    return 0


def cmd_control(args) -> int:
    root = orchestration_dir(require_vault(), args.project); root.mkdir(parents=True, exist_ok=True)
    request = {"status": "pending", "action": args.action, "issued_by": args.by or f"manual-{os.getpid()}",
               "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reason": args.reason or ""}
    dest = root / "control" / args.agent / f"{time.time_ns()}-{args.action}.json"
    _json_write(dest, request); print(dest.name); return 0


def cmd_orchestrate(args) -> int:
    vault = require_vault(); agent = args.agent or f"leader-{os.getpid()}"
    code, state = reconcile(vault, args.project, agent)
    print(json.dumps(state, indent=2)); return code


def cmd_supervisor(args) -> int:
    vault = require_vault(); root = orchestration_dir(vault, args.project); root.mkdir(parents=True, exist_ok=True)
    cfg = _orchestration_config(root); pidfile = root / "supervisor.pid"
    if args.action == "enable":
        cfg["enabled"] = True; _json_write(root / "config.json", cfg); print("supervisor enabled (not started)"); return 0
    if args.action == "configure":
        if not args.platform:
            print("error: configure requires --platform <name> (e.g. claude-code, codex, gemini, …)"); return 1
        if args.max_workers < 1:
            print("error: --max-workers must be at least 1"); return 1
        adapters = cfg.setdefault("adapters", {})
        entry = {"enabled": True, "max_workers": args.max_workers,
                 "model": args.model or "", "allow_write": bool(args.allow_write)}
        if args.launch_cmd:
            entry["launch_cmd"] = args.launch_cmd
        if args.models:  # per-kind model strengths, e.g. "design=A,coding=B,planning=C"
            entry["models"] = {k.strip(): v.strip()
                               for k, v in (kv.split("=", 1) for kv in args.models.split(",") if "=" in kv)}
        adapters[args.platform] = entry
        _json_write(root / "config.json", cfg)
        spec = ADAPTERS.get(args.platform)
        if args.launch_cmd:
            note = "custom launch_cmd"
        elif spec and spec.get("verified"):
            note = "verified adapter"
        elif spec:
            note = "best-effort adapter — verify flags or set --launch-cmd"
        else:
            note = "no built-in adapter — set --launch-cmd or run this platform manually"
        print(f"configured {args.platform}: max_workers={args.max_workers}, "
              f"allow_write={bool(args.allow_write)} ({note})")
        return 0
    if args.action == "disable":
        cfg["enabled"] = False; _json_write(root / "config.json", cfg); print("supervisor disabled"); return 0
    if args.action == "status":
        print(json.dumps({"enabled": cfg.get("enabled", False), "pid": _json_read(pidfile, {}), "state": _json_read(root / "status.json", {})}, indent=2)); return 0
    if args.action == "stop":
        info = _json_read(pidfile, {}); pid = int(info.get("pid", 0) or 0)
        if pid:
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
        try: pidfile.unlink()
        except OSError: pass
        print("supervisor stopped"); return 0
    if args.action == "start":
        if not cfg.get("enabled"):
            print("error: enable first: supervisor enable --project " + args.project); return 1
        info = _json_read(pidfile, {}); pid = int(info.get("pid", 0) or 0)
        try: os.kill(pid, 0); print(f"supervisor already running ({pid})"); return 0
        except OSError: pass
        log = (root / "supervisor.log").open("a", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "supervisor", "run", "--project", args.project], stdout=log, stderr=log, start_new_session=True)
        _json_write(pidfile, {"pid": proc.pid, "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        print(f"supervisor started ({proc.pid})"); return 0
    # foreground loop: suitable for systemd/launchd or a terminal.
    if not cfg.get("enabled"):
        print("error: supervisor is disabled"); return 1
    while True:
        reconcile(vault, args.project, f"supervisor-{os.getpid()}")
        time.sleep(max(5, int(_orchestration_config(root).get("interval_seconds", 60))))


# ---------------------------------------------------------------------------
# Orchestration board (FR-24): a cross-platform, single-CLI view of the swarm.
# Every agent — any platform — shows as "platform · model · effort · task · latest
# progress", with ticket and budget bars. It reads only shared vault files, so a
# Claude Code session sees the Codex workers and vice versa. `--watch` redraws for
# a real terminal; a chat-style CLI just re-runs it to refresh.
# ---------------------------------------------------------------------------
def _bar(frac: float | None, width: int = 10) -> str:
    f = 0.0 if frac is None else max(0.0, min(1.0, frac))
    fill = int(round(f * width))
    return "█" * fill + "░" * (width - fill)


def _age_str(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        secs = int(max(0, time.time() - datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()))
    except (ValueError, AttributeError):
        return "—"
    if secs < 90: return f"{secs}s ago"
    if secs < 5400: return f"{secs // 60}m ago"
    return f"{secs // 3600}h ago"


def _until_str(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        secs = int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() - time.time())
    except (ValueError, AttributeError):
        return "—"
    if secs <= 0: return "now"
    if secs < 5400: return f"in {max(1, secs // 60)}m"
    if secs < 172800: return f"in {secs // 3600}h"
    return f"in {secs // 86400}d"


def _num(n) -> str:
    """Compact number: 38000 -> 38k, 1500000 -> 1.5M."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    for suffix, div in (("M", 1e6), ("k", 1e3)):
        if abs(n) >= div:
            return f"{n / div:.1f}{suffix}".replace(".0" + suffix, suffix)
    return str(int(n)) if n == int(n) else f"{n:.1f}"


def _ticket_stats(vault: Path, project: str) -> Counter:
    counts: Counter = Counter()
    tdir = tickets_dir(vault, project)
    for p in tdir.glob("*.md") if tdir.exists() else []:
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        counts[fm.get("status", "open")] += 1
    return counts


_LIVE_EVENTS = {"registered", "heartbeat", "progress"}


def _render_board(vault: Path, project: str, verbose: bool = False) -> str:
    root = orchestration_dir(vault, project)
    cfg = _json_read(root / "config.json", {})
    lease = _json_read(root / "leader.lease", {})
    agents = _latest_agents(root)
    budgets = _latest_budgets(root)
    procs = ({pp.stem: _json_read(pp, {}) for pp in (root / "processes").glob("*.json")}
             if (root / "processes").exists() else {})
    tk = _ticket_stats(vault, project); total = sum(tk.values()); done = tk.get("done", 0)

    out = [f"SwarmVault orchestration — {project}",
           f"  leader: {lease.get('agent', '—')}   supervisor: "
           f"{'enabled' if cfg.get('enabled') else 'disabled'}   updated {_age_str(lease.get('updated_at'))}"]
    if total:
        out.append(f"  tickets  [{_bar(done / total)}] {done}/{total} done · {tk.get('open', 0)} open · "
                   f"{tk.get('claimed', 0)} claimed · {tk.get('blocked', 0)} blocked")
    if budgets:
        out.append("  usage / limits")
        for p, b in sorted(budgets.items()):
            frac = b.get("fraction")
            line = f"    {p:12} [{_bar(frac)}] " + (f"{frac * 100:.0f}% left" if frac is not None else "?")
            if b.get("used") is not None and b.get("limit"):
                line += f" · {_num(b['used'])}/{_num(b['limit'])} {b.get('unit') or 'tokens'}"
            if b.get("reset"):
                line += f" · resets {_until_str(b['reset'])}"
            if b.get("weekly") is not None:
                w = b["weekly"]
                line += (f" · weekly [{_bar(w)}] {w * 100:.0f}%"
                         + (" ⚠ near weekly limit" if w <= 0.15 else ""))
                if b.get("weekly_reset"):
                    line += f" (resets {_until_str(b['weekly_reset'])})"
            out.append(line)
    out.append("  workers")
    if not agents:
        out.append("    (none registered)")
    for name, d in sorted(agents.items()):
        proc = procs.get(name, {})
        ev = d.get("event", "?")
        dot = "●" if ev in _LIVE_EVENTS else "○"
        plat = d.get("platform") or proc.get("platform") or "?"
        model = d.get("model") or proc.get("model") or "—"
        tier = d.get("tier") or proc.get("tier") or "—"
        ticket = d.get("ticket") or proc.get("ticket") or "—"
        tail = f" — {ev} {_age_str(d.get('at'))}" + (f": {d['reason']}" if d.get("reason") else "")
        out.append(f"    {dot} {name:16} {plat:12} · {model:12} · {tier:5} · {ticket}{tail}")
        if verbose:
            if proc.get("prompt"):
                out.append(f"        prompt: {proc['prompt'][:200]}")
            log = proc.get("log")
            if log and Path(log).exists():
                for ln in Path(log).read_text(encoding="utf-8", errors="replace").splitlines()[-3:]:
                    out.append(f"        · {ln[:160]}")
    changes = []
    for pth in (sorted((root / "signals").glob("*/*.json"), reverse=True)
                if (root / "signals").exists() else []):
        d = _json_read(pth, {})
        if d.get("event") in {"progress", "done"} and d.get("reason"):
            changes.append(f"    {d.get('ticket') or '—'}: {d['reason']} "
                           f"({d.get('agent')}, {_age_str(d.get('at'))})")
        if len(changes) >= 5:
            break
    if changes:
        out.append("  recent changes")
        out.extend(changes)
    return "\n".join(out) + "\n"


def cmd_board(args) -> int:
    vault = require_vault()
    project = args.project or (resolve_project(vault, os.getcwd()) or {}).get("name")
    if not project:
        print("error: not a registered project; pass --project"); return 1
    if args.watch:
        try:
            while True:
                sys.stdout.write("\033[2J\033[H" + _render_board(vault, project, args.verbose))
                sys.stdout.flush()
                time.sleep(max(1, args.watch))
        except KeyboardInterrupt:
            return 0
    print(_render_board(vault, project, args.verbose), end="")
    return 0


# ---------------------------------------------------------------------------
# Usage-limit continuation (FR-23). A durable record that a session approaching
# its provider usage limit has scheduled a "continue project X" wake for after
# the limit resets. It is scheduler-agnostic: the agent creates the actual wake
# with its platform's native scheduler (Claude Code scheduled task, cron, …) and
# mirrors the intent here so ANY later session sees it (it surfaces in context)
# and can cancel it. It self-clears when the project is finished. Works with or
# without the optional supervisor.
# ---------------------------------------------------------------------------
def continuation_path(vault: Path, project: str) -> Path:
    return vault / PLANS / project / "continuation.json"


def read_continuation(vault: Path, project: str) -> dict:
    """The active (still-scheduled) continuation for a project, else {}."""
    data = _json_read(continuation_path(vault, project), {})
    return data if data.get("status") == "scheduled" else {}


def _write_continuation_md(vault: Path, project: str, rec: dict) -> None:
    """Human/Obsidian/query-visible mirror of the machine record."""
    dest = vault / PLANS / project / "continuation.md"
    platforms = ", ".join(rec.get("platforms") or []) or "any configured agent"
    body = [
        "---", "name: continuation",
        f'description: "scheduled continuation — resume {rec.get("resume_at", "?")} '
        f'(scope: {rec.get("scope", "until-finish")})"',
        f"project: {project}", "type: plan", f"status: {rec.get('status', 'scheduled')}", "---", "",
        f"# Scheduled continuation — {project}", "",
        f"- **Resume at:** {rec.get('resume_at', '?')} (when the provider usage limit resets)",
        f"- **Scope:** {rec.get('scope', 'until-finish')}",
        f"- **Platforms:** {platforms}",
        f"- **Prompt to fire:** {rec.get('prompt') or ('continue project ' + project)}",
        f"- **Reason:** {rec.get('reason', '')}",
        f"- **Set by:** {rec.get('created_by', '')} at {rec.get('created_at', '')}", "",
        "A session approaching its provider usage limit scheduled this wake, with the user's "
        "consent, so work resumes automatically after the limit resets. The vault holds all "
        "state, so the resumed session rebuilds context from memory/tickets/flow-state alone. "
        "It self-clears when the project is finished (`plan-continue clear`).",
    ]
    atomic_write(dest, "\n".join(body) + "\n")


def cmd_plan_continue(args) -> int:
    vault = require_vault()
    pdir = vault / PLANS / args.project
    path = continuation_path(vault, args.project)
    if args.action == "show":
        print(json.dumps(_json_read(path, {}), indent=2))
        return 0
    if args.action == "clear":
        existed = path.exists()
        for p in (path, pdir / "continuation.md"):
            try: p.unlink()
            except OSError: pass
        print("continuation cleared" if existed else "no continuation scheduled")
        return 0
    # set
    if not args.resume_at:
        print("error: set requires --resume-at <ISO-8601> (the provider usage-limit reset time)")
        return 1
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prior = _json_read(path, {})
    rec = {
        "project": args.project, "status": "scheduled",
        "scope": args.scope or "until-finish", "resume_at": args.resume_at,
        "platforms": [p.strip() for p in (args.platforms or "").split(",") if p.strip()],
        "prompt": args.prompt or f"continue project {args.project}",
        "reason": args.reason or "provider usage limit approaching; scheduled continuation",
        "created_by": args.by or os.environ.get("SWARMVAULT_AGENT", f"agent-{os.getpid()}"),
        "created_at": prior.get("created_at", now), "updated_at": now,
    }
    _json_write(path, rec)
    _write_continuation_md(vault, args.project, rec)
    print(f"continuation scheduled: resume {rec['resume_at']} (scope: {rec['scope']})")
    return 0


# ---------------------------------------------------------------------------
# Safe-state checkpoint (FR-21 token economy). Records a compact session note at a
# resumable point so the main agent can compact/clear its context to save tokens
# and continue — the vault holds the state (J1). Quality-bounded: the *skill*
# decides WHEN it is safe; this just writes the record and prints the resume line.
# ---------------------------------------------------------------------------
def cmd_checkpoint(args) -> int:
    vault = require_vault()
    project = args.project or (resolve_project(vault, os.getcwd()) or {}).get("name")
    if not project:
        print("error: not a registered project; pass --project"); return 1
    now = datetime.now(timezone.utc); date = now.date().isoformat()
    slug = args.slug or f"{now.strftime('%H%M%S')}-checkpoint"
    agent = args.agent or os.environ.get("SWARMVAULT_AGENT", f"agent-{os.getpid()}")
    fm = {"name": f"{date}-{slug}", "description": (args.did or "safe-state checkpoint")[:120],
          "project": project, "type": "session", "date": date, "agent": agent,
          "safe_state": True, "tags": ["swarm/session"]}
    body = [f"DID: {args.did or '—'}", f"NEXT: {args.next or '—'}"]
    if args.blocked:
        body.append(f"BLOCKED: {args.blocked}")
    dest = vault / SESSIONS / project / f"{date}-{slug}.md"
    atomic_write(dest, render(fm, "\n".join(body) + "\n"))
    print(f"checkpoint saved: {dest.relative_to(vault)}")
    print(f"safe to compact/clear — resume with: continue project {project}"
          f"  (NEXT: {args.next or 'see flow-state'})")
    return 0


# ---------------------------------------------------------------------------
# init / register / doctor (FR-02 / FR-03 / FR-18)
# ---------------------------------------------------------------------------
TEMPLATE_NOTES = {
    "memory.md": ("""---
name: short-kebab-slug
description: one line — this is what queries and MOCs show, make it carry the fact
project: ProjectName
type: memory
tags:
  - swarm/memory
---

The fact, stated once. Link related notes with [[their-name]].
**Why:** why it matters.
**How to apply:** what a future agent should do with it.
"""),
    "spec.md": ("""---
name: fr-00-feature-slug
description: one-line summary of the feature this spec defines
project: ProjectName
type: spec
status: draft
priority: must
requires: []
---

# FR-00 — Feature title

**Story:** As a <role>, I <want>, so that <outcome>.

## Acceptance criteria (EARS)
- WHEN <trigger>, the system shall <response>.

## Edge cases
- <case>
"""),
    "ticket.md": ("""---
name: TK-000-short-slug
description: "compact: verb + object + outcome"
project: ProjectName
type: ticket
status: open
fr: FR-00
requires: []
tier: mid
kind: coding
---

DO: implement X per [[fr-00-feature-slug]] acceptance criteria.
DONE WHEN: criteria met; unit tests happy+edge+exception pass; commit `feat(FR-00): ...`.
CONTEXT: read [[design-doc]] section X + code-note [[hot-file-note]]. Nothing else needed.
"""),
    "session.md": ("""---
name: 2026-01-01-what-happened
description: "compact: outcome of the session in one line"
project: ProjectName
type: session
date: 2026-01-01
tags:
  - swarm/session
---

DID: <what changed, files touched>.
NEXT: <the one thing a resuming agent should do first>.
BLOCKED: <or "nothing">.
"""),
    "decision.md": ("""---
name: adr-000-short-slug
description: one-line decision summary
project: ProjectName
type: decision
status: accepted
date: 2026-01-01
---

# ADR-000 — Title

## Context
## Options considered
## Decision
## Consequences
Links: [[fr-00-feature-slug]]
"""),
    "code-note.md": ("""---
name: path-to-file-note
description: why this file is the way it is — reasoning too heavy for inline comments
project: ProjectName
type: doc
---

File: `src/path/file.py`
Reasoning, history, and invariants that inline comments shouldn't carry.
Changes to this file should update this note.
"""),
}


def cmd_init(args) -> int:
    vault = Path(args.vault or vault_path() or (home() / "SwarmVault")).expanduser()
    for folder in FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    for fname, content in TEMPLATE_NOTES.items():
        dest = vault / TEMPLATES / fname
        if not dest.exists():
            atomic_write(dest, content)
    if not registry_path(vault).exists():
        save_registry(vault, [])
    if not (vault / MAPS / "Home.md").exists():
        atomic_write(vault / MAPS / "Home.md", render(
            {"type": "moc", "generated": True, "tags": ["swarm/moc"]},
            "# Home\n\nEmpty vault — register a project (`swarmvault.py register`) "
            "and run `swarmvault.py sync`.\n"))
    save_config({"vault": str(vault)})
    me = Path(__file__).resolve()
    print(f"vault ready: {vault}")
    print(f"config:      {config_path()}")
    print("\nNext steps:")
    print(f"  1. register a project:   cd <project> && python3 {me} register")
    print(f"  2. Claude Code hooks:    SessionStart -> python3 {me} hook")
    print(f"                           SessionEnd   -> python3 {me} sync --quiet")
    print(f"  3. Codex: add the SwarmVault section to AGENTS.md (see INSTALL.md)")
    print(f"  4. optional: open {vault} as an Obsidian vault for the graph view")
    return 0


def cmd_register(args) -> int:
    vault = require_vault()
    entries = load_registry(vault)

    if args.import_claude:
        added = 0
        try:
            data = json.loads((home() / ".claude.json").read_text(encoding="utf-8"))
            raw = [p for p in data.get("projects", {}) if Path(p).is_dir()]
        except (OSError, json.JSONDecodeError):
            print("no readable ~/.claude.json — nothing imported")
            raw = []
        # Drop container dirs that merely parent other projects.
        paths = sorted(raw, key=len)
        kept = [p for p in paths if not any(o != p and o.startswith(p.rstrip("/") + "/") for o in paths)]
        for p in sorted(kept):
            name = Path(p).name
            if any(e["name"] == name for e in entries):
                continue
            entries.append(_entry(name, p, False))
            _write_marker(Path(p), name)
            added += 1
        save_registry(vault, entries)
        print(f"imported {added} project(s) from ~/.claude.json")
        return 0

    path = Path(args.path or os.getcwd()).resolve()
    name = args.name or path.name
    existing = next((e for e in entries if e["name"] == name), None)

    if args.repair:
        if existing and str(existing["path"]) != str(path):
            existing["path"] = str(path)
            save_registry(vault, entries)
            print(f"repaired: {name} -> {path}")
        else:
            print("nothing to repair")
        return 0

    if existing:
        print(f"error: '{name}' is already registered ({existing['path']}) — pick another --name")
        return 1
    marker_name = find_marker(path)
    if marker_name and marker_name != name:
        print(f"error: this directory carries a marker for '{marker_name}' — use --name {marker_name} or remove {MARKER_NAME}")
        return 1
    entries.append(_entry(name, str(path), args.isolated))
    save_registry(vault, entries)
    _write_marker(path, name)
    print(f"registered {name} ({'isolated' if args.isolated else 'shared'}): {path}")
    return 0


def _entry(name: str, path: str, isolated: bool) -> dict:
    return {
        "name": name,
        "path": path,
        "isolation": "isolated" if isolated else "shared",
        "registered": datetime.now().strftime("%Y-%m-%d"),
    }


def _write_marker(project_dir: Path, name: str) -> None:
    marker = project_dir / MARKER_NAME
    if not marker.exists():
        atomic_write(marker, json.dumps({"project": name}) + "\n")


def cmd_doctor(_args) -> int:
    def check(ok: bool, label: str, detail: str = "") -> None:
        print(f"  {'✓' if ok else '✗'} {label}" + (f" — {detail}" if detail else ""))

    print("SwarmVault doctor")
    v = vault_path()
    check(v is not None, "config", str(config_path()) if v else "missing — run init")
    check(bool(v and v.is_dir()), "vault", str(v) if v else "")
    if v and v.is_dir():
        missing = [f for f in FOLDERS if not (v / f).is_dir()]
        check(not missing, "folders", ("missing: " + ", ".join(missing)) if missing else "all present")
        reg = load_registry(v)
        check(registry_path(v).exists(), "registry", f"{len(reg)} project(s)")
        cur = resolve_project(v, os.getcwd())
        check(cur is not None, "current project", cur["name"] if cur else "cwd is not a registered project")
        if cur:
            root = Path(cur["path"])
            check((root / ".claude" / "skills").is_dir() or (home() / ".claude" / "skills").is_dir(),
                  "claude-code skills", "found" if (root / ".claude" / "skills").is_dir() else "not in project (global?)")
            agents = root / "AGENTS.md"
            wired = agents.is_file() and "swarmvault" in agents.read_text(encoding="utf-8", errors="replace").lower()
            check(wired, "codex AGENTS.md", "swarmvault section found" if wired else "no swarmvault section")
    return 0


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="swarmvault.py", description="SwarmVault CLI — query and sync the agent knowledge vault.")
    sub = ap.add_subparsers(dest="cmd")

    q = sub.add_parser("query", help="search / filter vault notes")
    q.add_argument("--search"), q.add_argument("--project"), q.add_argument("--type")
    q.add_argument("--tag"), q.add_argument("--folder")
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--format", choices=["list", "json", "paths"], default="list")
    q.set_defaults(fn=cmd_query)

    s = sub.add_parser("show", help="print one note's body")
    s.add_argument("note")
    s.set_defaults(fn=cmd_show)

    c = sub.add_parser("context", help="compact context block for a project directory")
    c.add_argument("cwd", nargs="?")
    c.set_defaults(fn=cmd_context)

    h = sub.add_parser("hook", help="SessionStart hook mode (stdin JSON, always exit 0)")
    h.set_defaults(fn=cmd_hook)

    y = sub.add_parser("sync", help="mirror memory/docs/sessions into the vault")
    y.add_argument("--dry-run", action="store_true")
    y.add_argument("--quiet", action="store_true")
    y.set_defaults(fn=cmd_sync)

    i = sub.add_parser("init", help="create a vault and config file")
    i.add_argument("--vault")
    i.set_defaults(fn=cmd_init)

    r = sub.add_parser("register", help="register a project in the vault")
    r.add_argument("--path"), r.add_argument("--name")
    r.add_argument("--isolated", action="store_true")
    r.add_argument("--import-claude", action="store_true")
    r.add_argument("--repair", action="store_true")
    r.set_defaults(fn=cmd_register)

    cl = sub.add_parser("claim", help="atomically claim a ticket")
    cl.add_argument("ticket")
    cl.add_argument("--project", required=True)
    cl.add_argument("--agent", default=os.environ.get("SWARMVAULT_AGENT", f"agent-{os.getpid()}"))
    cl.add_argument("--break-stale", action="store_true")
    cl.set_defaults(fn=cmd_claim)

    rl = sub.add_parser("release", help="release a ticket claim")
    rl.add_argument("ticket")
    rl.add_argument("--project", required=True)
    rl.add_argument("--done", action="store_true")
    rl.set_defaults(fn=cmd_release)

    sg = sub.add_parser("signal", help="write a durable worker signal for the optional supervisor")
    sg.add_argument("--project", required=True); sg.add_argument("--agent", required=True)
    sg.add_argument("--event", required=True, choices=["registered", "heartbeat", "progress", "done", "blocked", "quota-wait", "stopped", "budget"])
    sg.add_argument("--platform"); sg.add_argument("--ticket"); sg.add_argument("--tier")
    sg.add_argument("--model"); sg.add_argument("--reason"); sg.add_argument("--retry-at")
    sg.add_argument("--budget", type=float, help="remaining usage budget 0..1 for --event budget (0 = exhausted)")
    sg.add_argument("--used", type=float, help="usage consumed so far, in --unit")
    sg.add_argument("--limit", type=float, help="usage limit, in --unit")
    sg.add_argument("--unit", help="unit for --used/--limit (default tokens)")
    sg.add_argument("--weekly", type=float, help="remaining weekly budget 0..1, if the plan has a weekly cap")
    sg.add_argument("--weekly-reset", help="ISO-8601 time the weekly limit resets")
    sg.set_defaults(fn=cmd_signal)

    ib = sub.add_parser("inbox", help="read or acknowledge durable supervisor requests")
    ib.add_argument("--project", required=True); ib.add_argument("--agent", required=True)
    ib.add_argument("--ack", help="acknowledge one request id returned by inbox")
    ib.set_defaults(fn=cmd_inbox)

    ct = sub.add_parser("control", help="send a durable start/stop/wake request to a registered worker")
    ct.add_argument("--project", required=True); ct.add_argument("--agent", required=True)
    ct.add_argument("--action", required=True, choices=["start", "stop", "wake", "retry"])
    ct.add_argument("--by"); ct.add_argument("--reason")
    ct.set_defaults(fn=cmd_control)

    oc = sub.add_parser("orchestrate", help="run one orchestration reconciliation; no daemon required")
    oc.add_argument("--project", required=True); oc.add_argument("--agent")
    oc.set_defaults(fn=cmd_orchestrate)

    sp = sub.add_parser("supervisor", help="manage the optional local orchestration process")
    sp.add_argument("action", choices=["enable", "disable", "configure", "start", "run", "stop", "status"])
    sp.add_argument("--project", required=True)
    sp.add_argument("--platform", help="agent platform to launch: claude-code, codex (verified), gemini/opencode/droid/cursor/copilot (best-effort), or any name with --launch-cmd")
    sp.add_argument("--max-workers", type=int, default=1)
    sp.add_argument("--model")
    sp.add_argument("--allow-write", action="store_true", help="allow launched workers to edit the registered project")
    sp.add_argument("--launch-cmd", help="override the launch command template; tokens {cwd} {model} {prompt}")
    sp.add_argument("--models", help="per-kind model strengths, e.g. 'design=A,planning=B,coding=C,review=D'")
    sp.set_defaults(fn=cmd_supervisor)

    bd = sub.add_parser("board", help="render a cross-platform orchestration board (see every agent in the current CLI)")
    bd.add_argument("--project")
    bd.add_argument("--verbose", action="store_true", help="also show each worker's prompt and recent log lines")
    bd.add_argument("--watch", type=int, default=0, help="redraw every N seconds (real terminal only)")
    bd.set_defaults(fn=cmd_board)

    ck = sub.add_parser("checkpoint", help="record a safe-state session note so you can compact/clear and resume")
    ck.add_argument("--project"); ck.add_argument("--agent"); ck.add_argument("--slug")
    ck.add_argument("--did", help="what was accomplished up to this safe point")
    ck.add_argument("--next", help="the exact next step to resume with")
    ck.add_argument("--blocked", help="anything blocking, if applicable")
    ck.set_defaults(fn=cmd_checkpoint)

    pc = sub.add_parser("plan-continue", help="record/show/clear a usage-limit continuation (resume after the provider limit resets)")
    pc.add_argument("action", choices=["set", "show", "clear"])
    pc.add_argument("--project", required=True)
    pc.add_argument("--resume-at", help="ISO-8601 time the provider usage limit resets (when to resume)")
    pc.add_argument("--scope", help="'until-finish' (default) or free text like 'until M3'")
    pc.add_argument("--platforms", help="comma-separated platforms to resume, e.g. claude-code,codex")
    pc.add_argument("--prompt", help="prompt to fire on resume (default: 'continue project P')")
    pc.add_argument("--reason"); pc.add_argument("--by")
    pc.set_defaults(fn=cmd_plan_continue)

    d = sub.add_parser("doctor", help="self-check the installation")
    d.set_defaults(fn=cmd_doctor)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
