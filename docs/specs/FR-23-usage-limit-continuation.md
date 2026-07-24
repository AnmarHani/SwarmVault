---
name: fr-23-usage-limit-continuation
description: Consent-gated continuation across provider usage limits — schedule a "continue project X" wake at reset, record it durably in the vault so any session sees it, and self-clear when done
project: SwarmVault
type: spec
status: draft-for-validation
priority: should
requires: [fr-03-query-cli, fr-07-swarm-flow, fr-11-swarm-implement]
---

# FR-23 — Usage-limit continuation

**Story:** As a developer on a project longer than one usage window, when an agent approaches
its provider usage limit it asks my consent and — if I agree — schedules a "continue project X"
wake for when the limit resets, records the intent durably in the vault so any later session
(on any platform) sees it, and self-clears when the project (or a point I name) is finished.
The vault holds all state, so the resumed session picks up cold without the prior transcript.

## Boundary

Works **with or without** the optional supervisor (FR-22) — a solo agent must offer it too. It
schedules nothing without explicit in-session consent, and never fabricates a reset time.

## Behavior

- **Watch the budget:** as usage approaches the provider limit (~90%+), the agent stops at a
  safe point rather than dying mid-ticket, and raises the choice.
- **Consent, once:** it asks whether to continue automatically after reset — **scope**
  `until-finish` or a user-named point (e.g. "until M3") — or to stop. No consent → clean,
  checkpointed stop.
- **Real reset time:** it uses the actual datetime the limit resets. IF that is unknown, THEN
  it schedules nothing and leaves a note instead.
- **Schedule + record:** on consent it (a) creates a platform-native wake (Claude Code
  scheduled task / cron / equivalent) that fires the prompt `continue project <P>` at the reset
  time, and (b) records a durable continuation via the CLI:
  `plan-continue set --project <P> --resume-at <ISO> --scope <…> [--platforms …] [--reason …]`.
- **Durable, visible record:** a single active continuation per project lives at
  `30 Plans/<P>/continuation.json` with a queryable `.md` mirror; it surfaces in injected
  session context (`⏳ Scheduled continuation`) so any session sees it and does not
  double-schedule.
- **Self-clear:** when the project or the named scope is finished, both the native task and the
  record are cleared (`plan-continue clear --project <P>`). A resumed session that finds the
  work already complete clears it rather than looping.
- **Supervisor path:** a worker that hits a limit emits `quota-wait --retry-at <ISO>`; the
  supervisor persists the wait, avoids relaunch loops, and retries only at/after that time.

## Acceptance criteria (EARS)

- WHEN an agent approaches its provider usage limit, THEN it shall ask the user whether to
  continue after reset (and at what scope) before scheduling anything.
- IF the reset time is unknown, THEN the agent shall schedule no wake and record a note instead
  of inventing a time.
- WHEN the user consents, THEN a durable continuation record shall be written that includes the
  resume time, scope, target platform(s), and reason.
- WHILE a continuation is scheduled, the injected session context and a queryable note shall
  surface it so any session on any platform sees the pending continuation.
- WHEN the project or the named scope is finished, THEN the scheduled task and the record shall
  both be cleared.
- WHEN a fresh session resumes via a continuation, THEN it shall reconstruct all state from the
  vault (memory, tickets, flow-state) without requiring the prior session's transcript (J1).

## Edge cases

- Unknown/opaque reset time → no wake; visible manual note.
- Project already complete on resume → clear the record, don't relaunch.
- Concurrent sessions → the single active record prevents double-scheduling; last write wins.
- User declines → stop cleanly with state checkpointed; no record written.
- Record present but native task lost (or vice versa) → the resumed session reconciles: if past
  the resume time it continues; when done it clears the record.

## Influences (credited in FR-19)

SwarmVault's own resume contract (J1) and context-injection (FR-03); the optional supervisor's
`quota-wait` handling (FR-22).
