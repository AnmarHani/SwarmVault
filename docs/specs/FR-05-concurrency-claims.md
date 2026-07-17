---
name: fr-05-concurrency-claims
description: Write-isolation rules and the atomic ticket-claim protocol that let N parallel agents cooperate through the vault without conflicts
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-01-vault-structure, fr-04-sync-engine]
---

# FR-05 — Concurrency: write-isolation + ticket claims

**Story:** As one of many parallel agents (any mix of Claude Code and Codex), I can pick up
work and record results without ever corrupting or duplicating another agent's work.

## Rules (per B4 — no daemons, no merge conflicts by construction)

1. **Own-files-only:** an agent writes only files it owns — its session journal, its memory
   notes, its claimed tickets' notes. Shared notes (MOCs, Home, indexes) are regenerated
   only by sync (lock-serialized, FR-04).
2. **Claim protocol:** tickets live in `30 Plans/<P>/tickets/TK-NNN-<slug>.md`
   (`status: open|claimed|done|blocked`, `fr:` trace link, `requires:` edges). To claim,
   an agent atomically creates `TK-NNN.claim` (O_CREAT|O_EXCL) containing
   `{agent, platform, started}`. Creation succeeded = claim won; file exists = someone
   else's — move on (NFR-R4). On completion the agent sets ticket `status: done` and
   deletes the claim.
3. **Stale claims:** claims older than a configurable TTL (default 2 h) with ticket not
   `done` may be broken by swarm-implement after logging a note to the ticket.

## Acceptance criteria (EARS)

- WHEN two processes attempt the same claim simultaneously, exactly one shall succeed
  (verified by a race test spawning concurrent claimers).
- A worker shall only start a ticket whose `requires:` tickets are all `done`.
- WHEN a worker finishes, ticket frontmatter shall record commit ref(s) and test file(s)
  for traceability (SRS §7).
- Claim/release operations shall be plain filesystem ops — no locks held while working.

## Edge cases

- Agent dies mid-ticket → stale-claim TTL frees it; partial work noted on the ticket by
  whoever re-claims (git history shows the rest).
- Two agents create tickets concurrently → ticket IDs allocated by filename (next free
  TK-NNN via atomic create loop), so no central counter needed.
