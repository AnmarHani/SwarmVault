---
name: fr-18-install
description: Three-door install — agent bootstrap via repo URL + INSTALL.md written for agents, install.sh for humans, documented manual copy
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-03-query-cli, fr-06-platform-adapters]
---

# FR-18 — Installation (three doors)

**Story:** As a new user, I paste the repo URL into my agent with one sentence and the
agent installs SwarmVault itself — or I run one script, or I copy folders by hand. All
three end in the same working state (E1).

## Door 1 — Agent bootstrap (the differentiator)

README's first section: a copy-paste block like *"Read
https://github.com/<owner>/swarmvault/blob/main/INSTALL.md and integrate SwarmVault into my
setup."* `INSTALL.md` is written FOR agents: exact ordered steps (clone → run
`swarmvault.py init` → ask the user the defined questions: vault path, platforms, global
vs project skills → wire adapters → verify), the questions to ask verbatim, verification
commands with expected output, and failure remedies. No ambiguity, no creativity required.

## Door 2 — `install.sh`

Idempotent bash: clones/updates to `~/.swarmvault/`, runs `init`, prints the adapter
wiring instructions it couldn't do automatically. POSIX-lean, no sudo, no network beyond
the git clone.

## Door 3 — Manual

README documents: copy `skills/` → `.claude/skills/`, copy `scripts/`, create config,
add hooks JSON (given verbatim), add AGENTS.md block (given verbatim).

## Acceptance criteria (EARS)

- An agent following INSTALL.md on a clean machine shall reach a state where
  `swarmvault.py query` works and at least one adapter is wired, within one session,
  asking only INSTALL.md's defined questions (NFR-U1).
- `install.sh` shall be re-runnable (updates in place, never duplicates hooks/fences).
- Every door shall end with the same verification step (`swarmvault.py doctor` — a small
  self-check subcommand: config readable, vault present, adapters detected) so success is
  observable, not assumed.
- IF a step fails, THEN INSTALL.md shall tell the agent what to check — never "figure it
  out".

## Edge case

- Install over an existing older SwarmVault → treated as update: scripts replaced, vault
  and user content untouched.
