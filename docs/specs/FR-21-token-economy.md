---
name: fr-21-token-economy
description: Cross-cutting token-economy doctrine — offload-don't-carry, budgets, tiering, milestone-only sweeps, handoff-by-vault, machine-lane compact writing
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-14-swarm-vault]
---

# FR-21 — Token-economy doctrine (cross-cutting)

**Story:** As a user paying per token, the framework saves wherever quality is not
sacrificed — by design, not by hoping agents are frugal (G1/G2, added mid-interview).

## The doctrine (mandated across all skills; canonical text lives in swarm-vault, FR-14)

1. **Offload-don't-carry** — durable state goes to the vault, referenced by note name;
   agents never re-explain what a note already says.
2. **Budgets (guidelines, not caps)** — injected context targets a configurable budget
   (default 3,500 chars); descriptions-first querying; bodies opened only when needed.
   The budget curbs habit, not necessity: when quality or completeness needs more
   context, take more — going in a wall to save characters is the failure mode, not the
   goal.
3. **Tiering** — model matched to task (FR-11); top models reserved for spec, design,
   review sweeps, complex logic.
4. **Milestone-only sweeps** — heavyweight review at milestones, not per commit (FR-12).
5. **Handoff-by-vault** — long sessions end with a resume note; fresh (cheaper) sessions
   continue from it instead of dragging a giant context.
6. **Machine-lane compact writing** — tickets, claims, queue entries, session notes,
   memory descriptions in terse telegraphic style (guideline with before/after examples in
   swarm-vault); human-lane docs (SRS, design, ADRs, README) stay full prose. Compression
   never applies where it would cost precision or human readability.

## Acceptance criteria (EARS)

- Every catalog skill's SKILL.md shall carry the doctrine lines relevant to its phase
  (verified in the M2 review sweep).
- Machine-lane templates (ticket, claim, queue entry, session note) shall demonstrate the
  compact style so agents copy it by example.
- WHEN an agent needs prior findings, the expected cost shall be one query + selective
  shows — the skills shall never instruct a full-vault or full-repo read.
- The doctrine shall state the quality floor explicitly, covering budgets AND
  compression: these are guidelines — if applying one would lose information a future
  agent needs, lower output quality, or block progress, take the tokens (user: "if
  quality needs it, then nah, take more").

## Influences (credited in FR-19)

caveman plugin (compression inspiration; technique rewritten), the author's original
CONTEXT_BUDGET design in vault_query.py.
