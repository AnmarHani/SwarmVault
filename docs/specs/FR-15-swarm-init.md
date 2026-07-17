---
name: fr-15-swarm-init
description: swarm-init skill — start a new project connected to the vault; offers vault-as-default, isolation choice, git init, and platform wiring
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-02-config-registry, fr-06-platform-adapters]
---

# FR-15 — `swarm-init` (new project onboarding)

**Story:** As a user starting a project, one skill wires it into the vault (registry,
marker, MOC skeleton, platform adapters, git) and asks me only the few questions that are
genuinely mine to answer (E2).

## Behavior

1. Checks vault exists (else offers `swarmvault.py init` first — including Obsidian
   pointer: vault opens as an Obsidian vault if the user wants the graph; link to the
   Obsidian setup guide in docs).
2. Asks: project name (default: dir name); isolation — shared or isolated (B8); platforms
   to wire (Claude Code / Codex / both); git init if absent (C8); **make vault the default
   for new projects?** → stores preference in config; when true, future inits skip the
   ceremony (E2).
3. Does: `register` + `.swarmvault` marker + MOC skeleton + adapter wiring (FR-06) +
   initial session journal entry.
4. Shows the security disclaimer once (NFR-S3) and points at swarm-flow to begin the SDLC.

## Acceptance criteria (EARS)

- After init, `swarmvault.py context .` shall return a valid context block for the project.
- WHEN vault-default is set, init on a new project shall need zero questions beyond
  confirmation.
- Init shall be safely re-runnable on an already-initialized project (repairs missing
  pieces, changes nothing else — idempotent like everything).
- WHEN the user declines git, everything else shall still work (git is recommended, not
  required).

## Edge cases

- Project dir already inside another registered project's tree → warn (nested projects)
  and require explicit confirmation.
- Name collision with existing registry entry → prompt for a different name (FR-02).
