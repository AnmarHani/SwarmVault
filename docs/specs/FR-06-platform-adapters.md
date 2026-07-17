---
name: fr-06-platform-adapters
description: Thin adapters wiring the canonical skills and vault scripts into Claude Code (hooks + .claude/skills) and Codex (AGENTS.md index)
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-03-query-cli, fr-04-sync-engine]
---

# FR-06 — Platform adapters (Claude Code + Codex)

**Story:** As a user of either platform, the same canonical `skills/` directory and scripts
serve my agents natively — no per-platform skill rewrites, no format drift (D3).

## Claude Code adapter

- Installer copies (or symlinks) `skills/*` → `.claude/skills/` (project) or
  `~/.claude/skills/` (global — user's choice at install).
- `settings.json` hooks: SessionStart → `swarmvault.py hook` (context injection);
  SessionEnd → `swarmvault.py sync`.
- Optional CLAUDE.md block (marker-fenced) describing the vault contract — mirrors the
  author's proven setup.

## Codex adapter

- Installer writes/updates an `AGENTS.md` section (marker-fenced for idempotent updates):
  the skill index (name, one-line description, when-to-use, path to SKILL.md) + the vault
  contract ("run `swarmvault.py context .` at session start; read the relevant SKILL.md
  before each phase; run `swarmvault.py sync` before finishing").
- Skills are read directly from canonical `skills/` — markdown is the universal format; no
  conversion step exists (D3).

## Acceptance criteria (EARS)

- WHEN installed for Claude Code, a new session in a registered project shall receive vault
  context automatically and sync on session end.
- WHEN installed for Codex, AGENTS.md shall contain the complete, current skill index; a
  Codex agent following it shall reach any skill file by path.
- Adapter (re)runs shall be idempotent: existing user content in CLAUDE.md/AGENTS.md
  outside the marker fences shall never be modified (echoes NFR-R1).
- A platform update shall require touching only its adapter — canonical skills stay
  untouched (NFR-M2).

## Edge cases

- Both platforms in one repo → both adapters coexist; single vault contract.
- Pre-existing user hooks in settings.json → installer merges, never overwrites, and shows
  the diff before writing.
