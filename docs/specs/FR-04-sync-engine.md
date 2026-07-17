---
name: fr-04-sync-engine
description: Sync engine mirroring memory, docs, and session journals into the vault and regenerating MOCs — idempotent, atomic, lock-serialized
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-01-vault-structure, fr-02-config-registry]
---

# FR-04 — Sync engine (`swarmvault.py sync`)

**Story:** As a user running many agent sessions, everything durable those sessions produce
(memory, docs, session summaries) lands in the vault automatically, so the next session —
on any platform — starts already knowing it.

## Behavior (generalizes the author's `vault_sync.py` per B4/B5)

Per registered project: mirror platform memory dirs (Claude Code `~/.claude/projects/<enc>/memory/`;
Codex equivalents when present) → `20 Memory/`; mirror repo docs (CLAUDE.md, AGENTS.md,
README.md, docs/ trees) → `10 Projects/<P>/`; extract compact session metadata (never full
transcripts) → `40 Sessions/`; regenerate the project MOC and `00 Maps/Home.md`.

- Mirrored notes get `generated: true`; pruning removes only generated notes whose source
  vanished. Human files are never touched (FR-01).
- All writes: write-if-changed + atomic replace. One `flock`-style lock file serializes
  concurrent sync runs (NFR-R3); a waiting sync may simply skip (the next trigger catches up).
- Triggers (B5): Claude Code SessionEnd hook; Codex — AGENTS.md instructs running sync
  before finishing; manual `swarmvault.py sync` always available. `--dry-run` supported.

## Acceptance criteria (EARS)

- Running sync twice consecutively shall report zero writes on the second run (NFR-R1).
- WHEN a memory file changes, the next sync shall update its mirror and the MOC line.
- WHEN a source memory/doc is deleted, its generated mirror shall be pruned; human notes
  with the same project shall remain.
- IF the lock is held, THEN a second sync shall exit 0 with a "skipped, locked" note within
  2 s (never deadlock a session-end hook).
- WHILE 10 agents work in parallel, session journals shall never collide: one file per
  session keyed by session id/date+slug (write-isolation, B4).
- Sync shall complete in under 10 s for 20 projects / 1,000 notes on commodity hardware.

## Edge cases

- Stale lock (crashed sync) → locks older than a threshold (e.g. 10 min) are broken with a
  logged note.
- Project registered but path missing → skipped with a warning line, never fatal.
- Doc exceeding size cap (~120 KB, as today) → skipped with a note in the MOC.
