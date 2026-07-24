---
name: fr-24-smart-orchestration-observability
description: Capability- and budget-aware task assignment across platforms/models, plus a cross-platform observability board (usage/limits, tokens, per-agent progress) viewable from any single CLI
project: SwarmVault
type: spec
status: draft-for-validation
priority: should
requires: [fr-05-concurrency-claims, fr-11-swarm-implement, fr-22-optional-orchestration-supervisor]
---

# FR-24 — Smart orchestration & observability

**Story:** As a developer running agents — one or many, one platform or several — the
orchestrator assigns each task to the platform and model that best fit its size and kind and
the platform's remaining usage budget, and I can watch the whole swarm (every agent's platform,
model, effort, task, progress, prompt, and changes, plus per-platform usage/limits) from
whatever single CLI I happen to be in.

## Budget signals

Platforms report remaining usage with `signal --event budget --platform X --budget 0..1`,
optionally `--used/--limit/--unit` (absolute usage, e.g. tokens) and `--weekly/--weekly-reset`
for a weekly cap. Unreported budget is **unknown**, never assumed or invented. A budget report
is platform telemetry and shall not overwrite a worker's work-status.

## Assignment (`plan_assignments`, pure and testable)

Biggest tasks first. For each runnable, unclaimed ticket:

1. **Skip** platforms without capacity (`max_workers`) or with empty/quota budget.
2. **Big tasks (`tier` top/mid) → the most remaining budget**, but **capability first**: a
   platform with a model configured for the task's `kind` is preferred over a higher-budget one
   without it.
3. **Small tasks / supervision → the least remaining budget**, preserving high-budget platforms
   for big work.
4. **Model = strength for the kind**: `models[kind]` → `models[tier]` → the platform's default
   `--model`. Flagship models only where size/kind warrant (token economy, FR-21).
5. A task with no eligible platform is **deferred** (and, near a limit, feeds usage-limit
   continuation, FR-23).

This holds for a single platform too (self-orchestration): it still routes the model by kind
and paces against its own budget. The kind→strength method and the reference to
[artificialanalysis.ai](https://artificialanalysis.ai) live in the skill's
`references/model-routing.md`; SwarmVault names no specific model (rankings move).

## Observability board (`board`)

`board --project P` renders, **from shared vault files only** (so cross-platform agents appear
as if local in any CLI):

- a ticket-progress bar (done / open / claimed / blocked);
- per-platform **usage/limits**: percent left, `used/limit unit`, reset time, and a weekly-cap
  bar that flags "near weekly limit";
- one row per agent — `platform · model · effort · task — latest progress`, live (●) or idle
  (○);
- a recent-changes feed from workers' `progress`/`done` signals.

`--verbose` adds each worker's dispatched prompt and recent log lines; `--watch N` redraws for a
real terminal.

## Acceptance criteria (EARS)

- WHEN multiple runnable tickets and eligible platforms exist, THEN each ticket shall be
  assigned to a platform with capacity and non-empty budget — big tasks preferring the most
  remaining budget, small tasks the least.
- WHEN a platform has a model configured for a task's kind, THEN a big task of that kind shall
  prefer that platform over a higher-budget platform lacking it.
- IF a platform's budget is empty or quota-waiting, THEN it shall not be assigned and the task
  shall be deferred.
- The model for a task shall be selected by kind, then tier, then the platform default.
- WHEN `board` runs in any platform's CLI, THEN it shall show every registered agent's platform,
  model, effort, task, and latest progress, plus per-platform usage/limits, from shared files
  alone and with no network call.
- Budget/usage a platform does not report shall be shown as unknown, never fabricated, and a
  budget report shall not overwrite an agent's work-status row.

## Edge cases

- No budgets reported → assignment falls back to size ordering (unknown ≈ medium).
- Weekly cap near its limit → surfaced with a warning; assignment still respects the
  daily/session budget.
- One platform → still routes the model per kind and paces by budget.
- Manual/cooperative and launched workers appear side by side once they signal.

## Influences (credited in FR-19)

SwarmVault's existing signal/claim/adapter contracts; model-strength data from
artificialanalysis.ai (method, not a pinned leaderboard).
