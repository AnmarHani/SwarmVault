---
name: fr-08-swarm-spec
description: swarm-spec skill — best-model requirements interview with persistent question queue, producing master SRS + per-feature specs with EARS criteria and ISO 25010 NFRs
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-01-vault-structure]
---

# FR-08 — `swarm-spec` (requirements phase)

**Story:** As a project owner, a relentless-but-organized interview extracts my full
requirements — functional and non-functional — into a validated, traceable specification
before any design or code exists (C1/C2; the SDLC's steps 1–4: gather, analyze, specify,
validate).

## Behavior

- **Model gate:** the skill states it expects the strongest available model and warns if
  the session is running a lesser tier (P1: "best model as planner").
- **Interview protocol** (from grilling, upgraded per the user's drift complaint):
  - Walk the decision tree branch by branch; every question carries a recommendation +
    assumptions + alternatives; free-text answers always accepted (NFR-U3).
  - **Persistent question queue** (`30 Plans/<P>/question-queue.md`, machine-lane): every
    question gets an ID + status (OPEN/ASKED/ANSWERED/PARTIAL/PARKED). Answers that resolve
    other questions are cross-marked; topic changes APPEND new branches — the main track is
    never dropped. The queue survives sessions and context compaction.
  - Facts are looked up (codebase, vault, web); only *decisions* go to the user.
- **Brownfield mode (H1):** on a project with existing code/docs, mine first, ask second
  (spec-miner stance): reverse-engineer requirements from README/docs/tests/code into
  `mined-draft` specs with per-statement provenance, present them for batch validation,
  and interview only on gaps and conflicts. The repo is treated as a stakeholder whose
  answers are already written down.
- **Outputs:** master SRS (vision, stakeholders, scope, constraints, FR index w/ MoSCoW
  priorities, ISO 25010 NFRs in EARS notation, traceability scheme, milestones, glossary)
  + one spec per feature (FR-ID, story, acceptance criteria, edge cases, dependencies)
  — in repo `docs/`, mirrored to vault `30 Plans/` by sync.
- **Validation gate:** ends by walking the user through the SRS for explicit approval;
  status flips draft → validated; flow-state updated.
- **Mode question (I1):** at validation, asks how the build should run — gated (user
  verifies each milestone as stakeholder) or auto (self-verifying sweeps, no stops) —
  and records the answer in flow-state for FR-07 to enforce.

## Acceptance criteria (EARS)

- Every functional requirement shall have: unique FR-ID, priority, ≥1 EARS acceptance
  criterion, and edge cases considered.
- NFRs shall cover, at minimum, the ISO 25010 characteristics relevant to the project, and
  the skill shall explicitly probe performance, security, usability, and reliability even
  when the user doesn't raise them.
- WHEN the user changes topic mid-interview, previously open questions shall remain in the
  queue and be returned to before the phase can complete.
- WHEN a requirement changes later (management step 5), the skill shall version the change
  in the SRS changelog and flag impacted downstream artifacts via FR-ID references.
- The SRS shall be written human-lane (full prose); the question queue machine-lane (G2).

## Influences (credited in FR-19)

Pocock's grilling (interview stance), superpowers brainstorming (intent exploration),
Jeffallan's feature-forge (EARS, workshops) + spec-miner (mining existing code on
brownfield projects), to-spec (conversation→spec), ISO 25010, EARS papers,
workingsoftware.dev NFR guide, geeksforgeeks SDLC references.
