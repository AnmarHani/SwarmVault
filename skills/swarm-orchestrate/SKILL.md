---
name: swarm-orchestrate
description: Optional autonomy control plane — configure, start, monitor, recover, or stop local Codex and Claude Code workers through SwarmVault's durable supervisor. Use when the user asks to orchestrate agents, dispatch work across Codex/Claude, enable a supervisor, recover idle work, or schedule continuation after limits.
---

# swarm-orchestrate — optional local autonomy

**Gate:** this add-on is disabled by default. Do not enable it, configure write access, or
start workers unless the user explicitly asks. Tickets and atomic claims remain the source of
truth; signals and controls never override a healthy claim.

## Enable

1. Confirm the project is registered and has dependency-ready tickets.
2. Choose each platform's worker limit, model, and whether that platform may edit code.
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

## Recovery and quota limits

Workers signal `quota-wait --retry-at <ISO-8601>` rather than retrying blindly. The supervisor
records the state and status. A stopped worker is surfaced as blocked with its log path; inspect
the ticket and log before reassigning. Reassignment always goes through the normal stale-claim
protocol.

---
*Influences: SwarmVault's existing claim, checkpoint, and adapter contracts.*
