---
name: fr-09-swarm-design
description: swarm-design skill — system architecture from the validated SRS; tech-stack options with recommendation, module boundaries, mermaid diagrams, ADRs
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-08-swarm-spec]
---

# FR-09 — `swarm-design` (system design phase)

**Story:** As a project owner with a validated SRS, I get an architecture that satisfies
every FR and NFR — with the significant choices put to me as options + recommendation, and
every decision recorded as an ADR I can revisit (C3).

## Behavior

- Input gate: validated SRS (else routes back to swarm-spec).
- Proposes: tech stack (options with trade-offs vs the NFRs, recommendation first),
  system decomposition (modules/services, boundaries, data flow — mermaid diagrams),
  data model, API contracts where relevant, error-handling and testing strategy fit for
  the stack.
- Design values: deep modules / simple interfaces; simplicity doctrine (NFR-M2) —
  the design must justify every moving part; known patterns referenced (refactoring.guru)
  rather than invented.
- Each significant decision → `50 Decisions/<P>/ADR-NNN-<slug>.md` (context, options,
  decision, consequences, FR/NFR links). Design doc → `docs/design.md`, mirrored to vault.
- Ends with user validation gate; updates flow-state (FR-07).

## Acceptance criteria (EARS)

- Every Must-priority FR shall map to at least one module/component in the design doc
  (traceability table included).
- Every NFR shall have a "how the design satisfies it" line — none silently dropped.
- WHEN a decision meaningfully affects cost, lock-in, or complexity, it shall be put to the
  user as options + recommendation, never silently taken (NFR-U3).
- ADRs shall be numbered sequentially per project and linked from the design doc.
- The design doc shall declare the milestone/ticket breakdown boundaries that
  swarm-implement will turn into tickets.

## Influences (credited in FR-19)

Jeffallan's architecture-designer + api-designer, Pocock's codebase-design (deep modules)
+ domain-modeling, refactoring.guru design patterns, ADR practice (Nygard).
