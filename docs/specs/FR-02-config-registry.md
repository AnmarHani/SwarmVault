---
name: fr-02-config-registry
description: Config file, in-vault project registry, and .swarmvault markers — how scripts resolve vault location and project identity on any platform
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-01-vault-structure]
---

# FR-02 — Config, registry, markers

**Story:** As a script or skill running on any platform, I can resolve (1) where the vault
is and (2) which registered project the current directory belongs to — without
platform-specific files like `~/.claude.json`.

## Design (per B2, B3, B8)

- **Config:** `~/.swarmvault.json` — `{"vault": "<path>"}` (+ future keys, e.g.
  `context_budget`). Overridable by `SWARMVAULT_HOME` env var (env wins).
- **Registry:** `<vault>/registry.json` — array of `{name, path, isolation:
  "shared"|"isolated", platforms: [...], registered: "YYYY-MM-DD"}`. Written by
  `register` (FR-03) / swarm-init / swarm-migrate; hand-editable.
- **Marker:** `.swarmvault` file in each project root — JSON `{"project": "<name>"}`.
  Enables cwd→project resolution even if registry paths drift, and visibly marks a repo
  as vault-connected.

## Resolution order (cwd → project)

1. Walk up from cwd looking for `.swarmvault` → name → registry entry.
2. Fallback: deepest registry `path` that prefixes cwd.
3. No match → not a vault project (scripts degrade gracefully, no error).

## Acceptance criteria (EARS)

- WHEN both env var and config file are present, the env var shall win.
- WHEN a project directory moves and its marker is intact, resolution shall still succeed
  via the marker (registry path updated on next `register --repair` or sync).
- IF neither config nor env var exists, THEN scripts shall print a one-line pointer to
  `init` and exit 0 (hooks must never break sessions — NFR-R2).
- `register` shall be able to import existing projects from `~/.claude.json` when that file
  is present (one-time convenience for Claude Code users).
- Registry `isolation` shall be honored by query filtering (NFR-S2).

## Edge cases

- Marker names a project absent from the registry → treat as unregistered; suggest
  `register`.
- Duplicate project names → `register` rejects with a clear message; names are unique keys.
- Registry JSON corrupt → scripts report the path and continue as if empty (never crash a
  session).
