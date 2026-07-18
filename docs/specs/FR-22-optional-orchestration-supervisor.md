---
name: fr-22-optional-orchestration-supervisor
description: Optional local supervisor that coordinates Claude Code and Codex workers through durable signals, safe dispatch, recovery, and quota-aware scheduling
project: SwarmVault
type: spec
status: draft-for-validation
priority: should
requires: [fr-05-concurrency-claims, fr-06-platform-adapters, fr-07-swarm-flow, fr-11-swarm-implement]
---

# FR-22 — Optional orchestration supervisor

**Story:** As a developer choosing fully autonomous execution, I can explicitly enable one
local supervisor that assigns eligible Claude Code and Codex workers to dependency-ready
tickets at the right effort/model tier, notices durable completion or blockage, recovers
abandoned work safely, and waits through usage limits without turning the core vault into a
service.

## Boundary: optional means optional

The supervisor is an add-on, not a prerequisite.

1. It shall be **disabled and not auto-started by default**. The standard vault, skills,
   claims, sync, and manual parallel-worker workflow shall remain fully functional without it.
2. Enabling it shall require an explicit local command/configuration. Status output and docs
   shall state whether it is disabled, running, paused, or stopped and how to change that.
3. It shall use stock Python and local plain markdown/JSON files only; it shall need no
   database, remote service, API key, or always-on hosted component.
4. `swarm-orchestrate` shall be a skill for planning and operating the protocol. The local
   supervisor process performs wakeups, polling, timers, and recovery; a skill alone cannot
   guarantee those behaviors after an agent session ends.

## Durable control plane

The vault remains the searchable system of record. Tickets remain the authority for work
ownership and completion. The supervisor adds a project-scoped, append-only signal log and a
generated human-readable status summary.

| Artifact | Writer | Purpose |
|---|---|---|
| Ticket + claim | existing worker protocol | authoritative work state and exclusive ownership |
| `signals/<agent-id>/…` | that agent or its adapter | atomic events: registered, heartbeat, progress, done, blocked, quota-wait, stopped |
| `control/<agent-id>/…` | leader/supervisor | requested start, stop, wake, or retry action; each command receives an acknowledgement event |
| `status.md` | supervisor only | generated view of leader, workers, runnable tickets, waits, and next recovery time |

No worker shall edit another worker's signal files. Signals include agent identity, platform,
ticket ID where applicable, event time, model/tier, and a compact reason. Events are retained
for audit/search; the summary is derived and may be regenerated at any time.

## Supervisor responsibilities

1. **Elect a leader:** obtain a renewable leader lease before planning, dispatching, or
   reassigning. A second supervisor may observe but shall not act while the lease is healthy.
2. **Plan and route:** use the existing dependency graph and model tiers. Select only an
   unblocked, unclaimed ticket whose required capabilities, platform preference, effort
   budget, and allowed provider/model match a registered worker.
3. **Dispatch safely:** ask the relevant configured adapter to start or wake a worker, then
   wait for its registered/claimed acknowledgement. A dispatch request is not proof of work.
   A ticket is owned only by the existing atomic claim protocol.
4. **Track health:** consume heartbeats and ticket checkpoints. Before treating a worker as
   stale, check its configured lease expiry and, when an adapter supports it, probe whether
   the registered process/session is still alive.
5. **Recover:** when a worker lease expires, record the reason, leave useful partial state
   intact, then use the existing stale-claim protocol before reassigning. It shall never
   revoke a healthy claim or create two owners.
6. **Handle limits:** a worker that receives a provider usage limit emits `quota-wait` with a
   configured or user-confirmed `retry_at`. The supervisor shall persist that wait, avoid
   relaunch loops, and retry only at/after that time. It may choose another eligible provider
   only if the ticket policy permits it.
7. **Sleep efficiently:** when nothing is runnable, exit or sleep until the earliest of a
   scheduled retry, lease expiry, or configured polling interval. It shall not busy-poll.
8. **Stop conservatively:** stop requests apply only to a worker launched by that supervisor
   or explicitly registered by its adapter. The framework shall not kill arbitrary user
   processes. A stop is a request until acknowledged; unacknowledged workers are handled by
   lease expiry, not force.
9. **Report:** write compact, searchable status and signal records sufficient for a cold
   agent or human to answer: who is leader, what is running, what completed, what is blocked,
   what is waiting for quota, and when the next action will occur.

## Platform adapters

Adapters are capability declarations, not promises that every vendor can be controlled.
Each adapter states independently whether it can `launch`, `observe`, `send-control`, and
`stop` a worker. The supervisor shall use only declared capabilities and degrade to a visible
manual-action request when one is absent. It shall not assume Claude Code can command Codex,
or vice versa.

## Acceptance criteria (EARS)

- WHEN the add-on is not explicitly enabled, THEN no supervisor process shall start and the
  normal claim-based workflow shall work unchanged.
- WHEN two supervisors start for one project, THEN exactly one healthy leader lease shall
  permit dispatch or reassignment.
- WHEN an eligible worker acknowledges dispatch and wins a ticket claim, THEN the status
  summary shall show its platform, assigned ticket, tier/model, and last heartbeat.
- IF a worker stops heartbeating past its lease and is not confirmed alive, THEN the
  supervisor shall log recovery and may reassign only after safely breaking the stale claim.
- WHEN a worker reports a usage limit, THEN the supervisor shall persist the retry time and
  shall not repeatedly restart that worker before it.
- WHEN an adapter lacks a control capability, THEN the supervisor shall record the required
  manual action instead of pretending it completed it.
- WHEN the supervisor restarts, THEN it shall reconstruct state from tickets, signals,
  leases, and scheduled waits without requiring an earlier process's memory.

## Edge cases

- Long-running commands: adapters may renew a worker lease without claiming progress; the
  supervisor must not mistake legitimate activity for abandonment.
- Unknown quota reset: remain `quota-wait` and surface a manual retry action; never invent a
  provider reset time.
- Provider/model unavailable: emit a blocked reason and consider only explicitly allowed
  fallback models/providers.
- Machine reboot: all timers are recomputed from persisted timestamps on the next start.
- A human starts a worker outside the supervisor: it may register and signal work, but the
  supervisor may stop it only after explicit adapter registration grants that authority.

---
*Influences: existing SwarmVault claim, checkpoint, and adapter contracts; no external
orchestration service is required.*
