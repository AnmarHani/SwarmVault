---
name: swarm-init
description: Start a new project connected to the SwarmVault — register it, wire platform adapters, offer git init, set vault-as-default. Use when starting a new project, connecting a project to the vault, or when the user asks to set up SwarmVault in a directory.
---

# swarm-init — new project onboarding

Idempotent: safe to re-run on an initialized project (repairs missing pieces, changes
nothing else).

## Steps

1. **Vault exists?** `swarmvault.py doctor`. If no vault: offer `swarmvault.py init`
   first. Mention once: opening the vault folder in Obsidian gives the graph and
   backlinks — optional, never required (`docs/obsidian-guide.md`).
2. **Ask** (only what is genuinely the user's):
   - Project name (default: directory name).
   - Isolation: shared (cross-project queries see it) or isolated?
   - Platforms to wire: Claude Code / Codex / both.
   - Git init, if no repo (recommended — the flow's traceability uses commits; optional).
   - If not already set: make the vault the default for new projects? → save
     `"auto_init_new_projects": true` in `~/.swarmvault.json`; future inits skip the
     ceremony.
3. **Do:** `swarmvault.py register --path . --name <name> [--isolated]` (writes registry
   entry + `.swarmvault` marker) → wire the chosen platform adapters (INSTALL.md carries
   the exact hook JSON and AGENTS.md block) → run `swarmvault.py sync --quiet` →
   `swarmvault.py doctor` to verify.
4. **Disclaimer** (show once, verbatim):
   > SwarmVault stores project knowledge as plain files and runs local scripts. Auditing
   > your environment, installed packages, and the data you place in the vault is your
   > responsibility. Isolation flags are cooperative filtering between agents, not a
   > security boundary.
5. Point forward: `/swarm-flow` starts the SDLC (first stop: swarm-spec).

## Edge cases

- Directory inside an already-registered project → warn (nested projects) and require
  explicit confirmation.
- Name collision → `register` refuses; pick another name.
- Existing marker with a different name → repair with `register --repair` or honor the
  marker; never two names for one directory.

---
*Influences: the original Claude Vault setup — see CREDITS.md.*
