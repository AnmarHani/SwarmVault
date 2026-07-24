#!/usr/bin/env python3
"""M1 test suite for swarmvault.py — stdlib unittest only (C-1).

Each test class maps to spec acceptance criteria; test names carry the FR/NFR
they verify (traceability, SRS §7). Run: python3 -m unittest discover tests -v
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("swarmvault", ROOT / "scripts" / "swarmvault.py")
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)


def note(path: Path, fm: dict, body: str = "body") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sv.render(fm, body), encoding="utf-8")


class Base(unittest.TestCase):
    """Sandboxed home + vault per test; nothing touches the real ~."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self._orig_home = sv.home
        sv.home = lambda: self.home
        os.environ.pop("SWARMVAULT_HOME", None)
        self.vault = self.home / "SwarmVault"
        self.run_cli("init", "--vault", str(self.vault))

    def tearDown(self):
        sv.home = self._orig_home
        os.environ.pop("SWARMVAULT_HOME", None)
        self.tmp.cleanup()

    def run_cli(self, *argv, stdin: str | None = None) -> tuple[int, str]:
        out = io.StringIO()
        old_stdin = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                try:
                    code = sv.main(list(argv))
                except SystemExit as e:  # require_vault path
                    code = int(e.code or 0)
        finally:
            sys.stdin = old_stdin
        return code, out.getvalue()

    def make_project(self, name: str, isolated: bool = False) -> Path:
        p = self.home / "projects" / name
        p.mkdir(parents=True, exist_ok=True)
        args = ["register", "--path", str(p), "--name", name]
        if isolated:
            args.append("--isolated")
        code, _ = self.run_cli(*args)
        self.assertEqual(code, 0)
        return p


class TestFrontmatter(unittest.TestCase):
    """FR-01/FR-03: the zero-dep parser covers the template range, degrades safely."""

    def test_scalars_lists_nesting(self):
        fm, body = sv.split_frontmatter(
            "---\n"
            "name: my-note\n"
            'description: "has: colon"\n'
            "count: 42\n"
            "generated: true\n"
            "inline: [a, b]\n"
            "tags:\n  - swarm/memory\n  - project/X\n"
            "metadata:\n  type: user\n"
            "---\n\nBody here.\n")
        self.assertEqual(fm["name"], "my-note")
        self.assertEqual(fm["description"], "has: colon")
        self.assertEqual(fm["count"], 42)
        self.assertIs(fm["generated"], True)
        self.assertEqual(fm["inline"], ["a", "b"])
        self.assertEqual(fm["tags"], ["swarm/memory", "project/X"])
        self.assertEqual(fm["metadata"], {"type": "user"})
        self.assertEqual(body.strip(), "Body here.")

    def test_malformed_degrades_to_note(self):
        for text in ("no frontmatter", "---\nnever closed", "---\n---\n\nbody"):
            fm, _ = sv.split_frontmatter(text)
            self.assertEqual(fm, {})
        self.assertEqual(sv.note_type({}, []), "note")

    def test_roundtrip(self):
        fm = {"name": "x", "description": "a: tricky", "n": 7, "generated": True,
              "tags": ["swarm/spec"], "metadata": {"type": "project"}}
        parsed, _ = sv.split_frontmatter(sv.render(fm, "b"))
        self.assertEqual(parsed, fm)

    def test_roundtrip_empty_list(self):
        # `requires: []` must survive a rewrite (release --done re-renders tickets).
        fm = {"name": "t", "requires": []}
        parsed, _ = sv.split_frontmatter(sv.render(fm, "b"))
        self.assertEqual(parsed["requires"], [])

    def test_type_precedence_tag_wins(self):
        # swarm/* tag must shadow a stray `type:` (silent omission guard, FR-03).
        self.assertEqual(sv.note_type({"type": "project"}, ["swarm/memory"]), "memory")
        self.assertEqual(sv.note_type({"type": "project"}, ["claude/session"]), "session")
        self.assertEqual(sv.note_type({"type": "spec"}, []), "spec")
        self.assertEqual(sv.note_type({"metadata": {"type": "user"}}, []), "user")


class TestQuery(Base):
    def seed(self):
        note(self.vault / "20 Memory/Alpha/auth-flow.md",
             {"name": "auth-flow", "description": "JWT auth flow with refresh tokens",
              "project": "Alpha", "tags": ["swarm/memory"]})
        note(self.vault / "20 Memory/Alpha/db-schema.md",
             {"name": "db-schema", "description": "postgres tables layout",
              "project": "Alpha", "tags": ["swarm/memory"]})
        note(self.vault / "20 Memory/Beta/beta-secret.md",
             {"name": "beta-secret", "description": "internal auth secret handling",
              "project": "Beta", "tags": ["swarm/memory"]})

    def test_fr03_bm25_ranks_match_first(self):
        self.seed()
        code, out = self.run_cli("query", "--search", "auth refresh tokens", "--format", "json")
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["name"], "auth-flow")

    def test_fr03_filters(self):
        self.seed()
        code, out = self.run_cli("query", "--project", "Alpha", "--format", "json")
        rows = json.loads(out)
        self.assertEqual({r["name"] for r in rows}, {"auth-flow", "db-schema"})

    def test_nfr_s2_isolation_cross_project(self):
        self.seed()
        self.make_project("Alpha")
        self.make_project("Beta", isolated=True)
        # Cross-project search from an unrelated cwd: Beta hidden.
        code, out = self.run_cli("query", "--search", "auth", "--format", "json")
        names = {r["name"] for r in json.loads(out)}
        self.assertIn("auth-flow", names)
        self.assertNotIn("beta-secret", names)
        # Explicit --project names it: included.
        code, out = self.run_cli("query", "--project", "Beta", "--format", "json")
        self.assertEqual({r["name"] for r in json.loads(out)}, {"beta-secret"})

    def test_fr03_show_ambiguous_lists_candidates(self):
        note(self.vault / "20 Memory/Alpha/dup.md", {"name": "dup", "project": "Alpha"})
        note(self.vault / "20 Memory/Beta/dup.md", {"name": "dup", "project": "Beta"})
        code, out = self.run_cli("show", "dup")
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", out)
        self.assertIn("20 Memory/Alpha/dup.md", out)


class TestResolution(Base):
    """FR-02: env > config; marker > registry prefix; moves survive via marker."""

    def test_env_wins_over_config(self):
        other = self.home / "OtherVault"
        other.mkdir()
        os.environ["SWARMVAULT_HOME"] = str(other)
        self.assertEqual(sv.vault_path(), other)
        os.environ.pop("SWARMVAULT_HOME")
        self.assertEqual(sv.vault_path(), self.vault)

    def test_marker_survives_move(self):
        p = self.make_project("Mover")
        moved = self.home / "projects" / "Mover2"
        p.rename(moved)
        e = sv.resolve_project(self.vault, str(moved))
        self.assertIsNotNone(e)
        self.assertEqual(e["name"], "Mover")
        # --repair updates the registry path from the new location.
        code, _ = self.run_cli("register", "--path", str(moved), "--name", "Mover", "--repair")
        self.assertEqual(code, 0)
        self.assertEqual(sv.resolve_project(self.vault, str(moved))["path"], str(moved))

    def test_prefix_fallback_and_subdir(self):
        p = self.make_project("Deep")
        subdir = p / "src" / "x"
        subdir.mkdir(parents=True)
        self.assertEqual(sv.resolve_project(self.vault, str(subdir))["name"], "Deep")

    def test_duplicate_name_rejected(self):
        self.make_project("Same")
        q = self.home / "projects" / "Same2"
        q.mkdir(parents=True)
        code, out = self.run_cli("register", "--path", str(q), "--name", "Same")
        self.assertEqual(code, 1)
        self.assertIn("already registered", out)

    def test_import_claude(self):
        a = self.home / "code" / "ImpA"
        a.mkdir(parents=True)
        (self.home / ".claude.json").write_text(json.dumps(
            {"projects": {str(a): {}, str(self.home / "code"): {}}}), encoding="utf-8")
        code, out = self.run_cli("register", "--import-claude")
        self.assertEqual(code, 0)
        names = {e["name"] for e in sv.load_registry(self.vault)}
        self.assertIn("ImpA", names)
        self.assertNotIn("code", names)  # container dirs dropped


class TestSync(Base):
    def setup_project_with_memory(self):
        p = self.make_project("Proj")
        mem = self.home / ".claude" / "projects" / sv.encode_claude_dir(str(p)) / "memory"
        mem.mkdir(parents=True)
        (mem / "gotcha.md").write_text(
            "---\nname: gotcha\ndescription: watch out for X\n---\n\nfact\n", encoding="utf-8")
        (p / "README.md").write_text("# Proj\n", encoding="utf-8")
        return p, mem

    def test_nfr_r1_idempotent(self):
        self.setup_project_with_memory()
        code, _ = self.run_cli("sync", "--quiet")
        self.assertEqual(code, 0)
        s = sv.Sync(self.vault)
        s.run(quiet=True)
        self.assertEqual(s.stats.written, 0, "second sync must be a no-op (NFR-R1)")

    def test_fr04_mirror_and_prune(self):
        p, mem = self.setup_project_with_memory()
        self.run_cli("sync", "--quiet")
        mirrored = self.vault / "20 Memory/Proj/gotcha.md"
        self.assertTrue(mirrored.exists())
        fm, _ = sv.split_frontmatter(mirrored.read_text(encoding="utf-8"))
        self.assertIs(fm["generated"], True)
        moc = (self.vault / "10 Projects/Proj/Proj MOC.md").read_text(encoding="utf-8")
        self.assertIn("watch out for X", moc)  # description surfaces in MOC
        (mem / "gotcha.md").unlink()
        self.run_cli("sync", "--quiet")
        self.assertFalse(mirrored.exists(), "generated note pruned when source vanished")

    def test_fr04_human_notes_never_touched(self):
        self.setup_project_with_memory()
        self.run_cli("sync", "--quiet")
        notes = self.vault / "10 Projects/Proj/Proj Notes.md"
        notes.write_text("MINE — hands off\n", encoding="utf-8")
        self.run_cli("sync", "--quiet")
        self.assertEqual(notes.read_text(encoding="utf-8"), "MINE — hands off\n")

    def test_fr04_swarm_memory_source(self):
        p = self.make_project("Codexy")
        local = p / ".swarm" / "memory"
        local.mkdir(parents=True)
        (local / "from-codex.md").write_text(
            "---\nname: from-codex\ndescription: codex-side fact\n---\n\nfact\n", encoding="utf-8")
        self.run_cli("sync", "--quiet")
        self.assertTrue((self.vault / "20 Memory/Codexy/from-codex.md").exists())

    def test_nfr_r3_lock_skips_and_breaks_stale(self):
        self.setup_project_with_memory()
        lock = self.vault / ".sync.lock"
        lock.write_text("held", encoding="utf-8")
        code, out = self.run_cli("sync")
        self.assertEqual(code, 0)
        self.assertIn("skipped", out)
        os.utime(lock, (time.time() - 999, time.time() - 999))
        code, _ = self.run_cli("sync", "--quiet")
        self.assertEqual(code, 0)
        self.assertFalse(lock.exists(), "stale lock broken, sync ran, lock released")


class TestClaims(Base):
    """FR-05 / NFR-R4: the filesystem referees; exactly one winner."""

    def make_ticket(self, project="P", tid="TK-001"):
        self.make_project(project)
        t = self.vault / "30 Plans" / project / "tickets" / f"{tid}-do-thing.md"
        note(t, {"name": f"{tid}-do-thing", "project": project, "type": "ticket",
                 "status": "open", "fr": "FR-00"})
        return t

    def test_nfr_r4_exactly_one_winner(self):
        self.make_ticket()
        wins = []
        barrier = threading.Barrier(8)

        def racer(i):
            barrier.wait()
            code, _ = self.run_cli("claim", "TK-001", "--project", "P", "--agent", f"a{i}")
            if code == 0:
                wins.append(i)

        threads = [threading.Thread(target=racer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(wins), 1, f"expected exactly 1 winner, got {wins}")

    def test_fr05_stale_break_and_release_done(self):
        t = self.make_ticket()
        claim = t.parent / "TK-001.claim"
        code, _ = self.run_cli("claim", "TK-001", "--project", "P", "--agent", "a1")
        self.assertEqual(code, 0)
        # Active claim: refused even with --break-stale.
        code, out = self.run_cli("claim", "TK-001", "--project", "P", "--agent", "a2", "--break-stale")
        self.assertEqual(code, 1)
        # Age it past the TTL: takeover allowed and logged on the ticket.
        old = time.time() - sv.CLAIM_TTL_S - 60
        os.utime(claim, (old, old))
        code, _ = self.run_cli("claim", "TK-001", "--project", "P", "--agent", "a2", "--break-stale")
        self.assertEqual(code, 0)
        self.assertIn("stale", t.read_text(encoding="utf-8"))
        code, _ = self.run_cli("release", "TK-001", "--project", "P", "--done")
        self.assertEqual(code, 0)
        fm, _ = sv.split_frontmatter(t.read_text(encoding="utf-8"))
        self.assertEqual(fm["status"], "done")
        self.assertFalse(claim.exists())

    def test_fr05_stale_break_race_no_crash(self):
        # Two agents may both see a stale claim; both must survive, one must win.
        t = self.make_ticket()
        claim = t.parent / "TK-001.claim"
        self.run_cli("claim", "TK-001", "--project", "P", "--agent", "a1")
        old = time.time() - sv.CLAIM_TTL_S - 60
        os.utime(claim, (old, old))
        results = []
        barrier = threading.Barrier(4)

        def breaker(i):
            barrier.wait()
            code, _ = self.run_cli("claim", "TK-001", "--project", "P",
                                   "--agent", f"b{i}", "--break-stale")
            results.append(code)

        threads = [threading.Thread(target=breaker, args=(i,)) for i in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(len(results), 4, "no breaker thread may crash")
        self.assertEqual(results.count(0), 1, f"exactly one breaker wins: {results}")
        self.assertFalse((t.parent / "TK-001.claim.break").exists(), "break-lock released")

    def test_fr05_claim_requires_ticket(self):
        self.make_project("P")
        code, out = self.run_cli("claim", "TK-404", "--project", "P")
        self.assertEqual(code, 1)
        self.assertIn("no ticket", out)


class TestOrchestration(Base):
    def test_fr22_disabled_by_default_and_enable_is_explicit(self):
        self.make_project("P")
        code, out = self.run_cli("supervisor", "status", "--project", "P")
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out)["enabled"])
        code, _ = self.run_cli("supervisor", "start", "--project", "P")
        self.assertEqual(code, 1)
        code, _ = self.run_cli("supervisor", "enable", "--project", "P")
        self.assertEqual(code, 0)
        code, out = self.run_cli("supervisor", "status", "--project", "P")
        self.assertTrue(json.loads(out)["enabled"])

    def test_fr22_adapter_configuration_requires_explicit_write_authorization(self):
        self.make_project("P")
        code, _ = self.run_cli("supervisor", "configure", "--project", "P", "--platform", "codex",
                               "--max-workers", "2", "--model", "gpt-test")
        self.assertEqual(code, 0)
        cfg = json.loads((self.vault / "30 Plans/P/orchestration/config.json").read_text())
        self.assertFalse(cfg["adapters"]["codex"]["allow_write"])
        code, _ = self.run_cli("supervisor", "configure", "--project", "P", "--platform", "claude-code",
                               "--allow-write")
        self.assertEqual(code, 0)
        cfg = json.loads((self.vault / "30 Plans/P/orchestration/config.json").read_text())
        self.assertTrue(cfg["adapters"]["claude-code"]["allow_write"])

    def test_fr22_configure_custom_platform_with_launch_cmd(self):
        self.make_project("P")
        code, out = self.run_cli("supervisor", "configure", "--project", "P", "--platform", "warp",
                                 "--max-workers", "1", "--allow-write", "--launch-cmd", "warpcli {prompt}")
        self.assertEqual(code, 0)
        self.assertIn("custom launch_cmd", out)
        cfg = json.loads((self.vault / "30 Plans/P/orchestration/config.json").read_text())
        self.assertEqual(cfg["adapters"]["warp"]["launch_cmd"], "warpcli {prompt}")

    def test_fr22_signal_control_and_inbox_ack(self):
        self.make_project("P")
        code, _ = self.run_cli("signal", "--project", "P", "--agent", "codex-1",
                               "--event", "registered", "--platform", "codex")
        self.assertEqual(code, 0)
        code, out = self.run_cli("control", "--project", "P", "--agent", "codex-1",
                                 "--action", "wake")
        self.assertEqual(code, 0)
        code, out = self.run_cli("inbox", "--project", "P", "--agent", "codex-1")
        item = json.loads(out)[0]
        self.assertEqual(item["action"], "wake")
        code, _ = self.run_cli("inbox", "--project", "P", "--agent", "codex-1", "--ack", item["id"])
        self.assertEqual(code, 0)
        code, out = self.run_cli("inbox", "--project", "P", "--agent", "codex-1")
        self.assertEqual(json.loads(out), [])


class TestLaunchAdapters(unittest.TestCase):
    """FR-22: declarative, overridable launch registry (pure argv builder)."""

    def test_verified_write_and_read_modes(self):
        w = sv.build_launch_argv("codex", {}, "/repo", "PROMPT", "gpt-x", True)
        self.assertEqual(w[0], "codex")
        self.assertIn("workspace-write", w)
        self.assertIn("PROMPT", w)
        self.assertIn("gpt-x", w)
        ro = sv.build_launch_argv("codex", {}, "/repo", "P", None, False)
        self.assertIn("read-only", ro)
        self.assertNotIn("-m", ro)  # no model given → model flag omitted
        cc = sv.build_launch_argv("claude-code", {}, "/repo", "P", None, True)
        self.assertEqual(cc[0], "claude")
        self.assertIn("acceptEdits", cc)

    def test_best_effort_is_write_only(self):
        w = sv.build_launch_argv("gemini", {}, "/repo", "P", "g-1", True)
        self.assertEqual(w[0], "gemini")
        self.assertIn("--yolo", w)
        # read-only unsupported for best-effort → None (never launch a writer as a reader)
        self.assertIsNone(sv.build_launch_argv("gemini", {}, "/repo", "P", None, False))

    def test_unknown_platform_is_none(self):
        self.assertIsNone(sv.build_launch_argv("warp", {}, "/repo", "P", None, True))

    def test_launch_cmd_override_wires_any_agent(self):
        argv = sv.build_launch_argv(
            "warp", {"launch_cmd": "mycli run --dir {cwd} -m {model} {prompt}"},
            "/repo", "hello world", "m1", True)
        self.assertEqual(argv, ["mycli", "run", "--dir", "/repo", "-m", "m1", "hello world"])

    def test_launch_cmd_drops_empty_model(self):
        argv = sv.build_launch_argv("x", {"launch_cmd": "cli {model} {prompt}"}, "/r", "P", None, True)
        self.assertEqual(argv, ["cli", "P"])  # empty {model} token removed


class TestScheduler(unittest.TestCase):
    """FR-24: budget- and capability-aware assignment (pure)."""

    def test_big_to_most_budget_small_to_least(self):
        adapters = {"codex": {"enabled": True, "max_workers": 2, "model": "c"},
                    "claude-code": {"enabled": True, "max_workers": 2, "model": "cc"}}
        budgets = {"codex": {"fraction": 0.85}, "claude-code": {"fraction": 0.30}}
        tickets = [{"id": "TK-A", "tier": "top", "kind": "coding"},
                   {"id": "TK-B", "tier": "small", "kind": "docs"}]
        plan, deferred = sv.plan_assignments(tickets, adapters, budgets, {})
        by = {a["ticket"]: a["platform"] for a in plan}
        self.assertEqual(by["TK-A"], "codex")          # big → most budget
        self.assertEqual(by["TK-B"], "claude-code")    # small → least budget (reserve codex)
        self.assertEqual(deferred, [])

    def test_capability_beats_budget_for_big_task(self):
        adapters = {"codex": {"enabled": True, "max_workers": 1, "model": "c", "models": {"coding": "c-code"}},
                    "claude-code": {"enabled": True, "max_workers": 1, "model": "cc", "models": {"design": "cc-design"}}}
        budgets = {"codex": {"fraction": 0.90}, "claude-code": {"fraction": 0.30}}
        plan, _ = sv.plan_assignments([{"id": "TK-D", "tier": "top", "kind": "design"}], adapters, budgets, {})
        self.assertEqual(plan[0]["platform"], "claude-code")  # has the design model despite less budget
        self.assertEqual(plan[0]["model"], "cc-design")

    def test_empty_budget_platform_skipped(self):
        plan, deferred = sv.plan_assignments(
            [{"id": "TK-1", "tier": "top", "kind": "coding"}],
            {"codex": {"enabled": True, "max_workers": 1, "model": "c"}},
            {"codex": {"fraction": 0.0}}, {})
        self.assertEqual(plan, [])
        self.assertEqual(deferred[0]["ticket"], "TK-1")

    def test_capacity_respected(self):
        adapters = {"codex": {"enabled": True, "max_workers": 1, "model": "c"}}
        tickets = [{"id": "TK-1", "tier": "top"}, {"id": "TK-2", "tier": "top"}]
        plan, deferred = sv.plan_assignments(tickets, adapters, {"codex": {"fraction": 0.9}}, {})
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(deferred), 1)

    def test_self_orchestration_picks_per_kind_model(self):
        adapters = {"claude-code": {"enabled": True, "max_workers": 1, "model": "cc",
                                    "models": {"design": "cc-design"}}}
        plan, _ = sv.plan_assignments([{"id": "TK-D", "tier": "top", "kind": "design"}], adapters, {}, {})
        self.assertEqual(plan[0]["model"], "cc-design")


class TestObservability(Base):
    """FR-24: budget signals + cross-platform board; FR-21: safe-state checkpoint."""

    def test_budget_signal_latest_wins_with_usage(self):
        self.make_project("P")
        self.run_cli("signal", "--project", "P", "--agent", "codex-1", "--event", "budget",
                     "--platform", "codex", "--budget", "0.9")
        self.run_cli("signal", "--project", "P", "--agent", "codex-1", "--event", "budget",
                     "--platform", "codex", "--budget", "0.4", "--used", "36000", "--limit", "60000",
                     "--unit", "tokens", "--weekly", "0.1")
        root = self.vault / "30 Plans/P/orchestration"
        budgets = sv._latest_budgets(root)
        self.assertEqual(budgets["codex"]["fraction"], 0.4)  # latest, not 0.9
        self.assertEqual(budgets["codex"]["limit"], 60000)
        self.assertEqual(budgets["codex"]["weekly"], 0.1)

    def test_board_shows_cross_platform_workers_and_limits(self):
        self.make_project("P")
        note(self.vault / "30 Plans/P/tickets/TK-001-x.md",
             {"name": "TK-001-x", "project": "P", "type": "ticket", "status": "open", "tier": "top"})
        self.run_cli("signal", "--project", "P", "--agent", "codex-1", "--event", "progress",
                     "--platform", "codex", "--model", "gpt-x", "--tier", "top", "--ticket", "TK-001",
                     "--reason", "auth wired")
        self.run_cli("signal", "--project", "P", "--agent", "codex-1", "--event", "budget",
                     "--platform", "codex", "--budget", "0.5", "--weekly", "0.1")
        code, out = self.run_cli("board", "--project", "P")
        self.assertEqual(code, 0)
        self.assertIn("codex", out)
        self.assertIn("gpt-x", out)           # model shown
        self.assertIn("TK-001", out)          # task shown
        self.assertIn("usage / limits", out)
        self.assertIn("near weekly limit", out)
        self.assertIn("auth wired", out)      # recent change / progress

    def test_checkpoint_writes_safe_state_note(self):
        self.make_project("P")
        code, out = self.run_cli("checkpoint", "--project", "P", "--agent", "lead",
                                 "--did", "planned M2", "--next", "review TK-003")
        self.assertEqual(code, 0)
        self.assertIn("continue project P", out)
        notes = list((self.vault / "40 Sessions/P").glob("*.md"))
        self.assertTrue(notes)
        fm, body = sv.split_frontmatter(notes[0].read_text(encoding="utf-8"))
        self.assertIs(fm.get("safe_state"), True)
        self.assertIn("review TK-003", body)


class TestContinuation(Base):
    """FR-23: consent-gated usage-limit continuation record."""

    def test_fr23_set_show_clear_roundtrip(self):
        self.make_project("P")
        code, _ = self.run_cli("plan-continue", "set", "--project", "P",
                               "--resume-at", "2026-07-25T09:00:00Z", "--scope", "until-finish",
                               "--platforms", "claude-code,codex", "--reason", "usage ~92%")
        self.assertEqual(code, 0)
        rec = json.loads((self.vault / "30 Plans/P/continuation.json").read_text())
        self.assertEqual(rec["status"], "scheduled")
        self.assertEqual(rec["resume_at"], "2026-07-25T09:00:00Z")
        self.assertEqual(rec["platforms"], ["claude-code", "codex"])
        self.assertTrue((self.vault / "30 Plans/P/continuation.md").exists())

        code, out = self.run_cli("plan-continue", "show", "--project", "P")
        self.assertEqual(json.loads(out)["scope"], "until-finish")

        code, _ = self.run_cli("plan-continue", "clear", "--project", "P")
        self.assertEqual(code, 0)
        self.assertFalse((self.vault / "30 Plans/P/continuation.json").exists())
        self.assertFalse((self.vault / "30 Plans/P/continuation.md").exists())
        code, out = self.run_cli("plan-continue", "show", "--project", "P")
        self.assertEqual(json.loads(out), {})

    def test_fr23_set_requires_resume_at(self):
        self.make_project("P")
        code, _ = self.run_cli("plan-continue", "set", "--project", "P")
        self.assertEqual(code, 1)

    def test_fr23_clear_without_plan_is_idempotent(self):
        self.make_project("P")
        code, out = self.run_cli("plan-continue", "clear", "--project", "P")
        self.assertEqual(code, 0)
        self.assertIn("no continuation", out)

    def test_fr23_scheduled_plan_surfaces_in_context(self):
        p = self.make_project("P")
        note(self.vault / "30 Plans/P/flow-state.md",
             {"name": "flow-state", "description": "implement M2", "project": "P",
              "type": "plan", "phase": "implement"})
        self.run_cli("plan-continue", "set", "--project", "P",
                     "--resume-at", "2026-07-25T09:00:00Z", "--reason", "usage ~92%")
        code, out = self.run_cli("context", str(p))
        self.assertEqual(code, 0)
        self.assertIn("Scheduled continuation", out)
        self.assertIn("2026-07-25T09:00:00Z", out)


class TestContextAndHook(Base):
    def seed_context(self, sessions=0):
        p = self.make_project("Ctx")
        note(self.vault / "20 Memory/Ctx/fact-a.md",
             {"name": "fact-a", "description": "alpha fact", "project": "Ctx",
              "tags": ["swarm/memory"]})
        note(self.vault / "30 Plans/Ctx/flow-state.md",
             {"name": "flow-state", "description": "implementation, M2 open",
              "project": "Ctx", "type": "plan", "phase": "implement"})
        for i in range(sessions):
            note(self.vault / f"40 Sessions/Ctx/2026-01-{i + 1:02d} s{i}.md",
                 {"name": f"s{i}", "project": "Ctx", "date": f"2026-01-{i + 1:02d}",
                  "tags": ["swarm/session"]})
        return p

    def test_fr03_context_content(self):
        p = self.seed_context(sessions=2)
        code, out = self.run_cli("context", str(p))
        self.assertEqual(code, 0)
        self.assertIn("fact-a — alpha fact", out)
        self.assertIn("Current phase:** implement", out)
        self.assertIn("Recent sessions", out)

    def test_nfr_p2_budget_trims_sessions_keeps_essentials(self):
        p = self.seed_context(sessions=3)
        sv.save_config({"context_budget": 200})  # absurdly small on purpose
        code, out = self.run_cli("context", str(p))
        self.assertNotIn("Recent sessions", out, "sessions are the first whole section dropped")
        self.assertIn("fact-a", out, "essentials survive even over budget (soft cap)")

    def test_nfr_r2_hook_never_fails(self):
        p = self.seed_context()
        for stdin in ("not json at all", "", json.dumps({"cwd": str(p)})):
            code, out = self.run_cli("hook", stdin=stdin)
            self.assertEqual(code, 0, f"hook must exit 0 on stdin={stdin!r}")
        code, out = self.run_cli("hook", stdin=json.dumps({"cwd": str(p)}))
        payload = json.loads(out)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        # Vault gone entirely: still exit 0, no output (NFR-R2).
        sv.save_config({"vault": str(self.home / "nowhere")})
        code, out = self.run_cli("hook", stdin="{}")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")


class TestInitDoctor(Base):
    def test_fr01_init_creates_standard_tree(self):
        for folder in sv.FOLDERS:
            self.assertTrue((self.vault / folder).is_dir(), folder)
        for tpl in sv.TEMPLATE_NOTES:
            f = self.vault / "90 Templates" / tpl
            self.assertTrue(f.exists(), tpl)
            fm, _ = sv.split_frontmatter(f.read_text(encoding="utf-8"))
            self.assertTrue(fm, f"{tpl} template frontmatter must parse cleanly")
        self.assertEqual(sv.load_registry(self.vault), [])
        self.assertEqual(sv.load_config()["vault"], str(self.vault))

    def test_fr18_doctor_exits_zero_everywhere(self):
        code, out = self.run_cli("doctor")
        self.assertEqual(code, 0)
        self.assertIn("registry", out)


if __name__ == "__main__":
    unittest.main()
