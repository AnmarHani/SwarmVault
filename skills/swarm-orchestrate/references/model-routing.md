# Model routing — match the model to the task kind & size

The point of smart orchestration is to spend the **right model** on each task, and the right
**budget** on each platform. This is a method + a snapshot, not a fixed leaderboard — model
rankings move monthly, so **verify current picks on [artificialanalysis.ai](https://artificialanalysis.ai)**
(Intelligence Index, Coding Index, and per-benchmark tables) and override in config.

## Task kinds → what to look for

| Kind | Optimize for | Where to check |
|---|---|---|
| `design` (UI/UX, visual) | design taste + strong reasoning; good at layout/CSS | coding + intelligence, plus your own eye |
| `planning` (architecture, specs, decomposition) | top **reasoning / Intelligence Index**; long context | Intelligence Index, long-context |
| `coding` (implementation) | top **Coding Index** (SWE-bench-style), tool use, speed | Coding Index / agentic coding |
| `review` (audit, spec-check) | strong reasoning + large context to hold spec + diff | Intelligence + context window |
| `docs` / boilerplate | cheap + fast; a small model is correct here (token economy) | price + speed / output tokens per $ |

**Provision strength on demand:** a `small`/`docs` task does **not** deserve a flagship model —
that is the token-economy doctrine. Reach for the strongest model only when task **size**
(`tier: top`) or kind (design/planning/review) actually needs it.

## Wiring it (per platform)

Give each platform the models it should use per kind; the scheduler picks
`models[kind]` → `models[tier]` → the default `--model`:

```bash
supervisor configure --project MyApp --platform claude-code --allow-write \
  --model <default> \
  --models 'design=<strong-design>,planning=<top-reasoning>,coding=<top-coding>,review=<top-reasoning>,docs=<cheap-fast>'
```

## Budget-aware assignment (what the scheduler does)

- **Big tasks → the platform with the most remaining usage budget** (it has room to finish);
  among those, prefer one that has a model configured for the task kind (capability first).
- **Small tasks / supervision → the platform with the *least* budget** — preserve the
  high-budget platforms for the big work.
- **Empty / quota-waiting platforms are skipped**; a task with nowhere to go is deferred (and,
  near a limit, triggers usage-limit continuation — see the main skill).
- Workers report budget with `signal --event budget --platform X --budget 0..1`
  (optionally `--used/--limit/--unit`, and `--weekly/--weekly-reset` for weekly caps). What
  isn't reported is treated as *unknown*, never assumed.

## Self-orchestration (one platform)

Even a single agent is "orchestrated": pick the right model **per task kind** from that
platform's models, pace against your own budget, and when it runs low use safe-state
compaction (checkpoint → clear → continue) or schedule a continuation — never grind a big task
on an empty budget.

*Snapshot note: written 2026-07-24. Re-check artificialanalysis.ai before trusting any specific
model name; this file names none on purpose.*
