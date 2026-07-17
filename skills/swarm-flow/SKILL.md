---
name: swarm-flow
description: The SDLC router — figures out where a project stands and runs the right phase. Use when asked to continue/resume a project, start the development flow, or when unsure which phase (requirements, design, implementation, review) comes next. Resume-from-anywhere on any platform.
---

# swarm-flow — the SDLC router

Thin by design: this skill decides *which* phase runs; all expertise lives in the phase
skills. Load the chosen skill before proceeding.

**The resume promise:** routing needs ONLY vault state — flow-state, ticket statuses, the
question queue, memory. "Continue project X" works from a cold session; never ask the
user what happened last time, and never require a previous transcript. A session that
died mid-work still lands correctly: stale claims surface via TTL, half-done phases
surface via their artifacts.

## Route

1. Resolve the project (`swarmvault.py context .`; `doctor` if that fails).
2. Read `30 Plans/<P>/flow-state.md` — but **artifacts on disk win** over stale state;
   correct the note with a logged line if they disagree.
3. Decide by the first matching row:

| Observed state | Phase → skill |
|---|---|
| No SRS, no specs | requirements → **swarm-spec** |
| SRS/specs `draft` or `mined-draft` | validation pass → **swarm-spec** |
| SRS validated; no design doc | design → **swarm-design** (+ **swarm-design-ui** if the SRS declares any user interface) |
| Designs validated; no tickets | ticket planning → **swarm-implement** |
| Open/claimed tickets | work the next unblocked ticket → **swarm-implement** |
| Milestone's tickets all done, no sweep report | milestone gate → **swarm-review** |
| Sweep findings open | fix tickets → **swarm-implement** |
| All milestones done | maintenance: bugs → **swarm-debug**; new asks → **swarm-spec** (change mgmt) |

4. Announce phase + evidence in one line ("SRS validated, 3 open tickets in M2 →
   implementing"), then proceed.

## Modes (recorded in flow-state as `mode: gated|auto`)

- **gated** — stop at every phase/milestone boundary for the user's stakeholder
  verification before continuing.
- **auto** — chain phases without stopping; the swarm-review sweep is the milestone gate;
  append non-blocking questions to the question queue; stop only when truly blocked
  (credentials, contradictory requirements, destructive/irreversible actions).

The mode is asked once at SRS validation (swarm-spec) and the user may change it anytime.

## Rules

- Never silently skip a user-validated gate; user-requested phase jumps are allowed with
  a one-line warning about what's being skipped.
- On phase completion, the finishing skill updates flow-state
  (`phase:`, `mode:`, `description:` compact status); offer — don't force — the next phase
  in gated mode.
- Monorepos: the nearest `.swarmvault` marker wins.

flow-state format:

```markdown
---
name: flow-state
description: "phase: implement — M2, 3/9 tickets open, next TK-014"
project: MyApp
type: plan
phase: implement
mode: auto
---
```

---
*Influences: Pocock's ask-matt (routing stance) — see CREDITS.md.*
