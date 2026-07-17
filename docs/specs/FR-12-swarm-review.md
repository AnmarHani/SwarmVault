---
name: fr-12-swarm-review
description: swarm-review skill — strong-model milestone sweep checking requirement fulfillment, standards, security posture, and simplification; findings become tickets
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-11-swarm-implement]
---

# FR-12 — `swarm-review` (milestone sweep)

**Story:** As a project owner closing a milestone, a strong model audits everything built
since the last sweep — against the spec, not just the code — and what it finds becomes
tracked work, not a chat message that scrolls away (C7/C9).

## Behavior

- **Model gate:** expects a top-tier model (like swarm-spec); milestone-only cadence — not
  per-commit (G1 token economy).
- **Four lenses over the milestone's diff + tickets:**
  1. *Fulfillment* — every FR in the milestone: acceptance criteria actually met? tests
     actually verify them? (spec-first, the differentiator)
  2. *Standards* — coding practices, naming, error handling, comment discipline.
  3. *Simplification* — can code be simplified, generalized, deduplicated? (C9)
  4. *Risk* — security smells, missing input validation, devil's-advocate pass on the
     design assumptions (the-fool stance).
- Verifies traceability: FR → ticket → commit → test chain intact.
- **Output:** review report (vault, human-lane) + one ticket per accepted finding
  (machine-lane, FR-linked). Milestone closes only when fulfillment findings are resolved
  or explicitly waived by the user.

## Acceptance criteria (EARS)

- The sweep shall check every Must-FR of the milestone individually — no sampling.
- Findings shall each carry: severity, FR link, file:line evidence, and a concrete
  suggested fix.
- WHEN the sweep passes with no fulfillment findings, the report shall say so plainly and
  flow-state shall advance.
- IF the sweep runs on a non-top-tier model, THEN it shall warn the user before proceeding.
- The skill shall never auto-fix: it reports and tickets; fixing is swarm-implement's job
  (separation keeps the review honest).

## Influences (credited in FR-19)

Pocock's code-review (two-axis: standards + spec), Jeffallan's code-reviewer +
security-reviewer, superpowers verification-before-completion + requesting-code-review,
the-fool (pre-mortem), euxx code-simplifier.
