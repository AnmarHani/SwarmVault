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
  doctor                                               self-check: config, vault, adapters

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
import sys
import time
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
    except (OSError, Exception):
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


def cmd_claim(args) -> int:
    vault = require_vault()
    tdir = tickets_dir(vault, args.project)
    matches = list(tdir.glob(f"{args.ticket}*.md"))
    if not matches:
        print(f"error: no ticket {args.ticket} under {tdir}")
        return 1
    claim = tdir / f"{args.ticket}.claim"
    if claim.exists():
        try:
            info = json.loads(claim.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            info = {}
        age = time.time() - claim.stat().st_mtime
        ttl = float(load_config().get("claim_ttl_hours") or CLAIM_TTL_S / 3600) * 3600
        if age > ttl and args.break_stale:
            # Log the takeover on the ticket itself, then fall through to re-claim.
            note = f"\n> claim by `{info.get('agent', '?')}` went stale ({int(age / 60)} min); broken by `{args.agent}`.\n"
            with matches[0].open("a", encoding="utf-8") as fh:
                fh.write(note)
            claim.unlink()
        else:
            holder = info.get("agent", "unknown")
            state = "STALE — re-run with --break-stale to take over" if age > ttl else "active"
            print(f"already claimed by {holder} ({state})")
            return 1
    try:
        fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print("lost the race — another agent claimed it first")
        return 1
    os.write(fd, json.dumps({
        "agent": args.agent,
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pid": os.getpid(),
    }).encode())
    os.close(fd)
    print(f"claimed {matches[0].name}")
    return 0


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

    d = sub.add_parser("doctor", help="self-check the installation")
    d.set_defaults(fn=cmd_doctor)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
