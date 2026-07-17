---
name: fr-07-swarm-flow
description: swarm-flow skill — thin SDLC router that reads vault state, announces the current phase, and loads the right phase skill; resume-from-anywhere
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-08-swarm-spec, fr-14-swarm-vault]
---

# FR-07 — `swarm-flow` (SDLC router)

**Story:** As a user on any platform, I type one thing (`/swarm-flow` or "continue the
project") and the agent figures out where the project stands and does the next right thing
— even if the last session was another agent on another platform (P1, D4).

## Behavior

1. Resolve project (FR-02); read its phase-state note
   (`30 Plans/<P>/flow-state.md` — machine-lane, written by each phase skill on completion).
2. Determine phase by state + artifact existence:
   no SRS → **spec**; SRS approved but no design doc → **design** (+ **design-ui** if the
   SRS declares a user interface); design approved but no tickets → ticket generation
   (swarm-implement's planning step); open tickets → **implement**; milestone boundary
   reached → **review**; all milestones done → maintenance (debug/change requests re-enter
   spec for new features).
3. Announce phase + evidence ("SRS exists, 3 open tickets in M2 → implementing"), load the
   phase skill, proceed. Never silently skip a phase gate the SRS marks as user-validated.
4. Brownfield (H1): artifacts with `status: mined-draft` count as "phase in progress,
   pending validation" — the router offers the validation pass before building on them.
5. **Resume contract (J1):** routing shall need ONLY vault state — flow-state, ticket
   statuses, question queue, memory. WHEN a session died mid-work, the router shall
   still land correctly (a claimed-but-stale ticket surfaces via the TTL; a half-done
   phase surfaces via its artifacts) without reading any transcript.
6. **Execution mode (I1):** flow-state records `mode: gated|auto` (asked once, at SRS
   validation — FR-08; changeable any time by the user). Gated: every phase/milestone
   boundary stops for stakeholder verification. Auto: phases chain without stopping;
   the swarm-review sweep is the milestone gate (FR-12); non-blocking questions are
   appended to the question queue and batched; the flow stops only when truly blocked
   (missing credentials, contradictory requirements, destructive actions).

## Acceptance criteria (EARS)

- WHEN invoked on a project with no vault artifacts, swarm-flow shall route to swarm-spec.
- WHEN invoked mid-implementation, it shall route to the highest-priority open, unclaimed,
  unblocked ticket.
- IF the phase-state note contradicts artifacts on disk (e.g. state says design but an SRS
  is missing), THEN artifacts win and the state note is corrected with a logged line.
- The SKILL.md shall stay thin (router only — target < 80 lines): all phase expertise
  lives in the phase skills.
- WHEN a phase completes, the completing skill shall update flow-state and swarm-flow shall
  offer (not force) continuing to the next phase.

## Edge cases

- Multiple projects in one repo (monorepo) → nearest `.swarmvault` marker wins.
- User asks for a specific phase out of order → allowed with a one-line warning about the
  skipped gate (user overrides are always permitted).
