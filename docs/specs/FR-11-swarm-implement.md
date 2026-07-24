---
name: fr-11-swarm-implement
description: swarm-implement skill — turns the design into dependency-ordered tickets, coordinates parallel workers via claims, enforces model tiering and tests-in-ticket DoD
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-05-concurrency-claims, fr-09-swarm-design]
---

# FR-11 — `swarm-implement` (implementation phase)

**Story:** As a project owner, any number of agents across platforms implement my validated
design in parallel without stepping on each other, at the right model tier per task, and
nothing is "done" until it fulfills its requirement with tests (C5/C6).

## Behavior

**Planning step (lead agent, strong model):** reads design doc → emits tickets
(`30 Plans/<P>/tickets/`, machine-lane): FR-ID trace, description, `requires:` edges,
suggested model `tier` (size) and `kind` (design/planning/coding/review/docs — lets FR-24
route the strongest model for the work), DoD checklist. Asks the user once: parallelism
appetite (default ON) and test-environment availability (browser for UI tests?).

**Worker loop (any agent):** claim next unblocked ticket (FR-05) → implement →
**Definition of Done**: requirement's acceptance criteria demonstrably met; unit tests per
function (happy + edge + exception paths); UI work verified in browser (Playwright) when
env available; code simplified (no needless complexity — euxx code-simplifier stance);
light comments/docstrings only; Conventional Commit `type(FR-ID): …` (C8); deep reasoning
→ vault code-note with one-line pointer in the file header (C8); ticket updated with
commit + test refs; claim released.

**Model tiering (C5, G1):** ticket carries suggested tier — top: architecture-touching or
complex logic; mid: standard features; small: boilerplate, docs, simple UI. Workers honor
it; the skill documents how to spawn tiered subagents on Claude Code and pick models on
Codex.

## Acceptance criteria (EARS)

- No ticket shall close without its DoD checklist fully checked (enforced by ticket
  template; verified again by FR-12 sweep).
- WHEN a worker's change would cross another ticket's files, it shall note the ticket link
  rather than expanding scope (scope discipline).
- WHEN all tickets of a milestone are done, the skill shall trigger the swarm-review gate
  before the next milestone opens.
- Workers shall read only the context a ticket names (spec, design section, code-notes) —
  not the whole vault (NFR-P3).
- WHILE parallelism is ON, two workers shall never hold the same claim (NFR-R4).
- Workers shall checkpoint state continuously (J1): claim on start, ticket frontmatter
  progress notes at significant steps, `done` + commit/test refs on completion — so a
  killed session's work is resumable from the vault alone, transcript never needed.

## Influences (credited in FR-19)

superpowers subagent-driven-development + executing-plans + dispatching-parallel-agents,
Pocock's implement + to-tickets (tracer-bullet tickets, blocking edges), euxx
code-simplifier, Conventional Commits, devcom coding-standards guide.
