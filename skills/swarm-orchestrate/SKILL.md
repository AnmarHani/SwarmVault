---
name: swarm-orchestrate
description: Optional autonomy control plane — configure, launch, monitor, recover, or stop local CLI-agent workers (Claude Code and Codex verified; Gemini, OpenCode, Droid, Cursor, Copilot best-effort; any other agent via a launch-command template) through SwarmVault's durable supervisor, with budget- and model-fit-aware task assignment, a cross-platform observability board (usage/limits, tokens, per-agent progress), safe-state context compaction, and usage-limit continuation so long projects survive quota resets. Use when the user asks to orchestrate agents, assign work by usage limits or model strength, view a live board of all agents, add a launch adapter, compact/continue past a usage limit, or recover idle work.
---

# swarm-orchestrate — optional local autonomy

**Gate:** this add-on is disabled by default. Do not enable it, configure write access, or
start workers unless the user explicitly asks. Tickets and atomic claims remain the source of
truth; signals and controls never override a healthy claim.

## Enable

1. Confirm the project is registered and has dependency-ready tickets.
2. Ask **how many agents of each platform** the user wants running, and for each: model tier
   and whether that platform may edit code. (Setup may have recorded this already — reuse it.)
3. Configure explicitly, then enable and start:

```bash
python3 /path/to/swarmvault.py supervisor configure --project MyApp --platform codex --max-workers 2 --model <model> --allow-write
python3 /path/to/swarmvault.py supervisor configure --project MyApp --platform claude-code --max-workers 2 --model <model> --allow-write
python3 /path/to/swarmvault.py supervisor enable --project MyApp
python3 /path/to/swarmvault.py supervisor start --project MyApp
```

`--allow-write` is deliberately per-platform and opt-in. Omit it for read-only planning or
review workers. The supervisor runs locally, does not use a shell to launch workers, and logs
every spawned process in the vault.

## Operate

- `supervisor status --project MyApp` — inspect enabled state, PID, workers, and status.
- `orchestrate --project MyApp` — perform exactly one reconciliation without a daemon.
- `signal --project MyApp --agent <id> --event heartbeat` — worker health/progress.
- `inbox --project MyApp --agent <id>` — worker reads pending controls; acknowledge with
  `--ack <id>`.
- `control --project MyApp --agent <id> --action stop|wake|retry` — durable request; it is
  not a claim revocation or arbitrary process kill.
- `supervisor stop --project MyApp` — stop only the supervisor. `disable` prevents restart.

## Smart assignment — size, budget & model fit

Orchestration is not round-robin. Match each task to the right platform **and** model:

- **Report budgets** so the scheduler can see them:
  `signal --event budget --platform X --budget 0.7 [--used 38000 --limit 60000 --unit tokens]
  [--weekly 0.2 --weekly-reset <ISO>]`. Unreported budget is treated as unknown, never assumed.
- **Big tasks → the platform with the most remaining usage**, preferring one whose configured
  model fits the task kind; **small tasks / supervision → the least-budget platform**, so the
  big-budget ones stay free for big work. Empty/quota platforms are skipped (→ continuation).
- **Provision the model to the task kind** (design / planning / coding / review / docs) and
  **size** — flagship models only where `tier: top` or a demanding kind needs them; cheap+fast
  for docs/boilerplate. Wire per-kind models with `configure --models 'design=…,coding=…'`.
- Keep the picks current from [artificialanalysis.ai](https://artificialanalysis.ai). Full
  method and the kind→strength table: `references/model-routing.md`.

This applies to a single platform too — see *Self-management* below.

## Observability — one board for the whole swarm

`board --project MyApp` renders every agent, **any platform, in the current CLI** — so a Claude
Code session sees the Codex (and other) workers as if local:

```
board --project MyApp            # snapshot; re-run to refresh
board --project MyApp --verbose  # + each worker's dispatched prompt and recent log lines
board --project MyApp --watch 5  # live redraw every 5s in a real terminal
```

It shows: a ticket-progress bar; per-platform **usage/limits** (percent left, tokens
used/limit, reset time, and a weekly-cap bar that flags "near weekly limit"); and one row per
worker — `platform · model · effort · task — latest progress`, live (●) or idle (○) — plus a
recent-changes feed built from workers' `progress`/`done` signals. Workers make it rich by
signalling meaningfully: `signal --event progress --reason "auth wired, tests green"`.

## Agent roster & launch adapters

Any agent can be a **cooperative worker** — run the swarm-implement worker loop
(claim → build → test → release) against the shared vault; claims are the referee. The
supervisor can also **launch** workers headlessly, via a declarative adapter registry with
three tiers:

- **Verified** — `claude-code`, `codex`. Spawned without a shell, exact flags known,
  ownership verified by the atomic claim. Both a `write` and a real read-only mode.
- **Best-effort** — `gemini`, `opencode`, `droid`, `cursor`, `copilot`. Sensible default
  invocations for fast-moving CLIs. **Confirm the flags for your installed version**, or
  override. These launch **only with `--allow-write`**: read-only headless launch is offered
  only where a genuine read/plan mode is known, so a read-only request can never accidentally
  start a writing agent. A wrong flag fails visibly (the exited process is logged as blocked),
  never silently.
- **Any other agent** (Windsurf, Kiro, Trae, Continue, Augment, Warp, …) — wire it with a
  command template you vouch for:

  ```bash
  supervisor configure --project MyApp --platform kiro --allow-write \
    --launch-cmd 'kiro run --dir {cwd} {prompt}'      # tokens: {cwd} {model} {prompt}
  ```

  With no adapter and no `--launch-cmd`, the supervisor records a **manual-action** request
  (start that agent yourself) rather than guessing a command.

Never assume one platform can command another (Claude Code cannot drive Codex, or vice versa);
each adapter only declares what it can do.

## Usage limits & continuation (FR-23)

Long projects outlast a single provider usage window. This works **with or without the
supervisor** — even a solo agent should offer it.

1. **Watch your own budget.** As you approach the provider usage limit (~90%+), stop and raise
   it rather than dying mid-ticket.
2. **Get consent, once, in-session.** Ask: *"You're near your usage limit. Continue
   automatically after it resets — until the whole project is finished, or until a point you
   name (e.g. end of M3)? Or stop here?"* Do not schedule anything without an explicit yes.
3. **Read the reset time.** Use the real datetime the limit resets — never invent one. If it
   is unknown, say so and schedule nothing; leave a note instead.
4. **Schedule the wake with your platform's native scheduler** (Claude Code scheduled task /
   cron / equivalent) to fire the prompt `continue project <P>` at the reset time. The vault
   holds all state, so a cold session resumes from memory + tickets + flow-state alone.
5. **Record it durably so every agent sees it:**

   ```bash
   python3 /path/to/swarmvault.py plan-continue set --project MyApp \
     --resume-at 2026-07-25T09:00:00Z --scope until-finish \
     --platforms claude-code,codex --reason "usage ~92%"
   ```

   This surfaces in session context (`⏳ Scheduled continuation`) and as a queryable note, so a
   fresh session — on any platform — knows a continuation is pending and won't double-schedule.
6. **Clean up when done.** When the project (or the named `--scope`) is finished, delete the
   native scheduled task **and** clear the record: `plan-continue clear --project MyApp`. A
   resumed session that finds the work already complete clears it instead of looping.

For the supervisor path, a worker that hits a limit emits `quota-wait --retry-at <ISO>`; the
supervisor persists the wait, avoids relaunch loops, and retries only at/after that time, and
may choose another eligible provider only if the ticket policy permits.

## Self-management — safe-state compaction

Even one agent orchestrates itself. On a long task, when your context grows large **and you are
at a safe, resumable point** (ticket done, phase boundary, a planning milestone recorded):

1. `checkpoint --project MyApp --did "…" --next "…"` — records a safe-state session note.
2. Make sure flow-state, tickets, and memory are current (they are your real state, J1).
3. Compact/clear your context (your platform's mechanism), then continue — the SessionStart
   context rebuilds from the vault.

**Quality outranks token-saving.** Never compact mid-reasoning, mid-edit, or when continuity is
carrying the task — if the work needs the tokens, keep them and finish well. Compaction is for
*safe* boundaries only.

## Recovery and quota limits

Workers signal `quota-wait --retry-at <ISO-8601>` rather than retrying blindly. The supervisor
records the state and status. A stopped worker is surfaced as blocked with its log path; inspect
the ticket and log before reassigning. Reassignment always goes through the normal stale-claim
protocol.

---
*Influences: SwarmVault's existing claim, checkpoint, and adapter contracts.*
