---
name: fr-16-swarm-migrate
description: swarm-migrate skill — bring existing projects into the vault; register + MOC + doc mirror immediately, deeper analysis offered as optional step
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-15-swarm-init, fr-04-sync-engine]
---

# FR-16 — `swarm-migrate` (existing-project migration)

**Story:** As a user with pre-vault projects, I pick which ones join the vault and each
gets immediate value (registered, indexed, docs mirrored) — with the token-costing deep
analysis as my explicit choice, not a surprise bill (E2).

## Behavior

1. **Discover:** lists candidate projects (from `~/.claude.json` if present, or user-named
   paths) and asks which to migrate (multi-select, per the user's "ask what projects need
   to be migrated").
2. **Per project — immediate (cheap):** register + marker + isolation question + MOC
   skeleton + first sync (mirrors existing CLAUDE.md/AGENTS.md/docs + any existing platform
   memory) + adapter wiring offer (FR-06).
3. **Offer (token-costing, per-project opt-in):** deep pass — architecture digest note +
   seed memories mined from the repo (structure, conventions, footguns found in code
   comments/README). Estimated cost stated before running.
4. **SDLC adoption (H1, opt-in per project):** place the project in the flow, not just
   the vault. Mine what already exists — README/docs requirements, plan files, TODOs,
   issue exports, test suites, the code itself (spec-miner stance via FR-08's brownfield
   mode) — into draft artifacts: SRS + feature specs marked `status: mined-draft`, each
   mined statement carrying provenance (file/line it came from). Detect the de-facto
   phase ("14 of 20 mined features implemented, no design doc") and write flow-state
   accordingly. Then interview the user ONLY on gaps, conflicts, and confidence-flagged
   items — never re-ask what the repo already answers. Remaining work becomes tickets;
   the project resumes mid-phase via swarm-flow (FR-07).
5. Asks once at the end: make vault the default for new projects? (shared with FR-15).

## Acceptance criteria (EARS)

- WHEN migration of a project completes (immediate tier), a session started in it shall
  receive vault context (hook path verified).
- The deep pass shall never run without per-project explicit consent (G1: no unordered
  token spend); the SDLC-adoption pass likewise (it is the most token-costing tier).
- WHEN adoption runs, every mined requirement shall carry provenance (source file
  reference) and `status: mined-draft` until the user validates it; the gap interview
  shall use the question-queue mechanism (FR-08) and shall not ask anything the mined
  sources already answer.
- WHEN adoption completes, flow-state shall reflect the detected phase and `swarm-flow`
  shall resume the project mid-phase (verified on a fixture project with existing code
  and partial docs).
- Migration shall be idempotent: re-running on a migrated project repairs, never
  duplicates.
- Existing repo files shall never be modified except the marker + adapter fences (FR-06
  rules).

## Edge cases

- Project with existing non-SwarmVault Obsidian vault inside → excluded from doc
  mirroring; noted in MOC (no vault-in-vault recursion).
- Huge monorepo → deep pass scopes to user-chosen subpaths.
