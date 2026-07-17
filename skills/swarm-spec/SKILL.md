---
name: swarm-spec
description: Requirements phase — relentless, organized stakeholder interview producing a validated SRS + per-feature specs with EARS acceptance criteria and ISO 25010 NFRs. Use to start a new project's requirements, gather/analyze/specify/validate requirements, stress-test a plan, or mine requirements from an existing codebase (brownfield). Also handles requirement changes after validation.
---

# swarm-spec — requirements phase

Quality here is leverage: every later phase builds on this document. Expect the strongest
available model — if this session runs a lesser tier, say so and let the user decide.

## The interview

Walk the decision tree branch by branch. For every question: give a **recommendation
first**, state your assumptions, list alternatives — and accept any free-text answer.
Facts are looked up (codebase, vault, web); only *decisions* go to the user.

**The question queue** — `30 Plans/<P>/question-queue.md` (machine lane) — is what keeps
a long interview honest:

- Every question gets an ID + status: `OPEN / ASKED / ANSWERED / PARTIAL / PARKED`.
- An answer that resolves other questions: cross-mark them with the answer's ID.
- The user changes topic or adds a requirement mid-stream: APPEND a new branch; the main
  track is never dropped. Return to open questions before the phase can complete.
- The queue survives sessions and context compaction — re-read it on resume.

Probe explicitly, even unprompted: performance, security, usability, reliability
(ISO 25010: functional suitability, performance efficiency, compatibility, usability,
reliability, security, maintainability, portability). Ask about interfaces (Web/Mobile/
Desktop/TUI/CLI/none), stakeholders, constraints (budget, stack, compliance), and what is
explicitly OUT of scope.

## Brownfield mode (existing code)

Mine first, ask second — the repo is a stakeholder whose answers are already written down.
Reverse-engineer requirements from README/docs/tests/code into specs marked
`status: mined-draft`, each statement carrying provenance (`file:line`). Present for batch
validation; interview only gaps, conflicts, and low-confidence items. Never re-ask what
the sources answer.

## Outputs (human lane, in repo `docs/`, mirrored to vault `30 Plans/`)

- **`docs/SRS.md`** — vision, stakeholders, scope in/out, constraints, FR index with
  MoSCoW priorities, NFRs in EARS notation, traceability scheme, build milestones,
  changelog, glossary.
- **`docs/specs/FR-XX-<slug>.md`** per feature — story, details, acceptance criteria
  (EARS), edge cases, `requires:` dependencies. Template: `90 Templates/spec.md`.

EARS patterns: ubiquitous ("The X shall…"), event ("WHEN … shall…"), state ("WHILE …"),
unwanted ("IF … THEN …"), optional ("WHERE …"). Every FR: unique ID, priority, ≥1
testable criterion, edge cases considered.

## Validation gate (ends the phase)

Walk the user through the SRS; on approval flip `status: draft → validated`. Then ask the
**mode question**: gated (user verifies each milestone) or auto (sweeps self-verify, no
stops) — record in flow-state along with `phase: design`.

## Changes after validation (requirements management)

New/changed requirement → tracker entry + SRS changelog + version bump + propagate to
every artifact that mentions it (specs, design, tickets) via FR-ID references. Flag
impacted downstream work; never edit silently.

---
*Influences: Pocock's grilling & to-spec; superpowers brainstorming; Jeffallan's
feature-forge & spec-miner; ISO 25010; EARS; workingsoftware.dev NFR guide — see
CREDITS.md.*
