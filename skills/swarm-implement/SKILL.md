---
name: swarm-implement
description: Implementation phase — turn a validated design into dependency-ordered tickets, then work them as one of N parallel agents with atomic claims, model tiering, and tests-in-ticket definition of done. Use to plan tickets from a design, pick up/continue implementation work, coordinate parallel agents, or check what to build next.
---

# swarm-implement — implementation phase

Two roles. Check flow-state: no tickets yet → you're the **planner**; tickets exist →
you're a **worker**.

## Planner (strong model, once per milestone batch)

**Gate:** validated design. Read `docs/design.md` and the milestone's FR specs.

1. Emit tickets to `30 Plans/<P>/tickets/TK-NNN-<slug>.md` (template:
   `90 Templates/ticket.md`, machine lane): FR-ID trace, `requires:` edges (tracer-bullet
   order: thinnest end-to-end slice first), suggested `tier` (size) and `kind`
   (`design`/`planning`/`coding`/`review`/`docs` — lets orchestration route the right model),
   DoD checklist, and CONTEXT — the exact notes/design sections a worker needs (nothing more).
2. Ask the user ONCE (skip in auto mode if already answered at SRS validation):
   parallelism appetite, and is a browser/test environment available for UI verification?
3. Update flow-state (`phase: implement`, ticket count) — J1: state first, work second.

**Model tiers:** `top` — architecture-touching, complex logic, tricky concurrency;
`mid` — standard features, refactors; `small` — boilerplate, docs, simple UI. Workers on
the wrong tier for a ticket should say so rather than proceed on hard tickets.

## Worker loop (any agent, any platform, N in parallel)

1. **Pick:** next `status: open` ticket whose `requires:` are all `done`
   (`swarmvault.py query --project P --type ticket`).
2. **Claim:** `swarmvault.py claim TK-NNN --project P --agent <you>` — claim won = yours;
   lost = pick another. Claims stale past the TTL: `--break-stale` (it logs the takeover).
3. **Read only the ticket's CONTEXT** — not the whole vault (token economy).
4. **Implement** to the DoD:
   - Acceptance criteria of the FR demonstrably met — no feature is complete until it
     fulfills its requirement.
   - Unit tests per function: happy path + edge cases + exception paths.
   - UI work: verify in the real browser/app when the env allows (Playwright); else mark
     the ticket `needs-ui-verify` honestly.
   - **Craft — write it for the next human** (a future teammate or agent):
     - *Simple:* the least code that does the job; delete before you add; no speculative
       generality.
     - *Reusable:* search first — call an existing function instead of a near-duplicate;
       factor a shared helper only once a second real caller exists (not preemptively).
     - *Readable:* intention-revealing names, small single-purpose functions, early returns
       over deep nesting, match the file's existing idiom and style.
     - *Maintainable:* obvious data flow, no hidden globals/side effects, errors handled where
       they happen.
     - *Comment sparingly:* the code shows *what*; comments/docstrings only capture *why* —
       a constraint, a tradeoff, a non-obvious edge — never narrate lines. Delete
       commented-out code.
   - Deep reasoning that would bloat comments → code-note in
     `10 Projects/<P>/code-notes/` + one pointer line in the file header.
   - Commit: Conventional Commits with the FR in scope — `feat(FR-12): …`.
5. **Checkpoint as you go (J1):** significant progress or a blocker → one compact line
   appended to the ticket. A killed session must be resumable from the ticket alone.
6. **Close:** `swarmvault.py release TK-NNN --project P --done`; record commit + test
   refs in the ticket frontmatter; journal a session note (DID/NEXT/BLOCKED).

**Scope discipline:** your change wants to cross into another ticket's files → note the
ticket link and stop; never expand scope silently.

**Milestone boundary:** last ticket of a milestone done → trigger swarm-review (auto
mode) or offer it (gated).

---
*Influences: superpowers subagent-driven-development, executing-plans &
dispatching-parallel-agents; Pocock's implement & to-tickets; euxx code-simplifier;
Conventional Commits — see CREDITS.md.*
