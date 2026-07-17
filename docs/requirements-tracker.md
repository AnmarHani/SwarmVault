# Agentic Framework — Requirements Interview Tracker

> Protocol: grilling skill (one branch at a time, recommendation per question).
> Statuses: OPEN / ASKED / ANSWERED / PARTIAL / PARKED. Answers that resolve other
> questions get cross-referenced. New topics are APPENDED — the main track is never dropped.
> This file moves into the repo once A2 (location) is answered.

## Branch A — Project identity & scope
- **A1** [ANSWERED] Name: **SwarmVault**
- **A2** [ANSWERED] Location: `~/claude_only/SwarmVault` (git initialized)
- **A3** [ANSWERED] v1 platforms: **Claude Code + Codex** first-class; core kept platform-agnostic (plain markdown + scripts) so others come nearly free later
- **A4** [ANSWERED] License: **MIT**; attribution via CREDITS.md (merged-skill licenses verified under D2)

## Branch B — Vault core (the centerpiece)
- **B1** [ANSWERED] Plain Obsidian-compatible markdown; Obsidian optional viewer (graph/backlinks)
- **B2** [ANSWERED] One central vault, default path (e.g. `~/SwarmVault`), overridable via small config file
- **B3** [ANSWERED] Registry file inside the vault (name → path → isolation flags) + `.swarmvault` marker in each project root; can import from `~/.claude.json` when present
- **B4** [ANSWERED] Write-isolation by design: agents write only own files; shared notes (MOCs/indexes) regenerated idempotently; atomic writes (os.replace) + single flock around sync
- **B5** [ANSWERED] Claude Code: SessionStart/SessionEnd hooks. Codex: AGENTS.md instructs query-at-start / sync-at-end. One code path, two triggers
- **B6** [ANSWERED] Keep schema + layout as-is; ship as documented standard w/ templates in 90 Templates. Specs/tickets live under 30 Plans, ADRs under 50 Decisions (no new top-level folders)
- **B7** [ANSWERED] Same CLI (--search/--project/--type/--tag/--show/--context/--hook/--format) reading config, plus `init` + `register` subcommands. No new query features v1
- **B8** [ANSWERED] Registry flag (shared|isolated), enforced by query script filtering; documented as cooperative isolation, NOT a security boundary (user-responsibility stance)

## Branch C — SDLC pipeline skills
- **C1/C2** [ANSWERED] Master SRS (vision, stakeholders, constraints, ISO 25010 NFRs, stack decision record) + per-feature spec files (FR-ID, user story, EARS acceptance criteria, priority, edge cases) + persistent question-queue file. Lives in repo docs/, mirrored to vault 30 Plans
- **C3/C4** [ANSWERED] Two skills: design-system (arch, stack options w/ recommendation, mermaid, ADRs → 50 Decisions) + design-ui (brand/design system, atomic design, box model/spacing, UX laws, per-interface TUI/CLI/Web/Mobile/Desktop guidance)
- **C5** [ANSWERED] Lead agent → dependency-ordered tickets in vault; workers claim via claim files (cross-platform double-work prevention); tiering: top=architecture/complex, mid=standard features, small=boilerplate/docs; parallel default ON, token-saver documented
- **C6/C7** [ANSWERED] Tests-in-ticket DoD (unit per function: happy+edge+exception; UI via Playwright/browser when env available — ask user once). No separate test phase. Milestone: strong-model sweep skill (standards+simplification+req fulfillment) → vault report → findings become tickets
- **C8** [ANSWERED] Local git per project (init offers git init). Conventional Commits w/ FR-ID scope: `feat(FR-12): ...`. Deep reasoning for hot files → vault code-note, file gets one header pointer line. Traceability req→ticket→commit→test
- **C9** [ANSWERED] Simplification folded into swarm-review (milestone sweep includes simplify pass, per euxx code-simplifier techniques); implement skill carries "simplify before done" in DoD

## Branch D — Skill curation & format
- **D1** [ANSWERED] 10-skill catalog: swarm-spec, swarm-design, swarm-design-ui, swarm-implement, swarm-review, swarm-debug, swarm-vault, swarm-init, swarm-migrate, swarm-skill-forge. Language-expert packs, caveman, personal/writing sets DROPPED. (Inventory: 122 skills, 4 upstreams — Jeffallan 66 [MIT inline], Pocock ~34 [no license], obra/superpowers 15 [verify], caveman 7 [unattributed])
- **D2** [ANSWERED] All skills REWRITTEN fresh (techniques learned, no verbatim copying); every influence credited in CREDITS.md (author, repo, what we learned). Clean under MIT
- **D3** [ANSWERED] Canonical skills/ of plain SKILL.md. Claude Code: installer copies/symlinks → .claude/skills/. Codex: installer writes AGENTS.md index (name+description+when-to-use+path) instructing agent to read skill files. No conversion step
- **D4** [ASKED] Flow routing: proposing an 11th thin skill swarm-flow (knows phase order, checks vault state, loads right phase skill) — in Round 6

## Branch E — Setup, migration, distribution
- **E1** [ANSWERED] Three doors: README bootstrap prompt (paste URL to agent → agent follows INSTALL.md written FOR agents) + install.sh for humans + documented manual copy of .claude/
- **E2** [ANSWERED] swarm-migrate: register + marker + MOC skeleton + mirror existing docs; OFFERS deep pass (digest + seed memories) as optional token-costing step. Asks: which projects, isolation flag, vault-default-for-new?
- **E3** [DECIDED-BY-ME] Obsidian setup guide in docs/; security-responsibility disclaimer (user audits env/packages/data; framework author not responsible) in README + surfaced by swarm-init. Wording per user's original statement
- **E4** [ANSWERED] Python 3 ZERO pip deps (hand-rolled minimal frontmatter parser replaces PyYAML). Linux/macOS/WSL primary, Windows best-effort
- **D4** [ANSWERED] Yes: 11th skill swarm-flow — thin router; reads vault state to find current phase, loads right phase skill; /swarm-flow resumes any project anywhere

## Branch G — Token economy (added mid-interview by user: "offload context to vault, save tokens caveman-style where quality isn't sacrificed")
- **G1** [ANSWERED, AMENDED 2026-07-17] Full offload doctrine, mandated in skills: (1) char budget on injected context — **guideline, not hard cap: quality wins, take more when genuinely needed** (user amendment during SRS validation), descriptions-first; (2) offload-don't-carry — write state to vault, reference by name; (3) model tiering; (4) milestone-only sweeps; (5) handoff-by-vault — fresh cheap session resumes from vault notes
- **G2** [ANSWERED] Compact/terse style MACHINE-LANE ONLY: tickets, claims, question-queue, session notes, memory descriptions. Human-facing (SRS, design docs, ADRs, README) = full prose. Caveman credited as inspiration, technique rewritten

## Branch F — README & marketing
- **F1** [DRAFT-FOR-REVIEW] Tagline/hooks/feature list drafted in FR-20 spec; user reviews wording at README writing time
- **F2** [DECIDED-BY-ME] Graph screenshot + terminal demo as placeholders in v1; real assets when vault has content

## Branch H — Brownfield SDLC adoption (added by user 2026-07-17 during M1)
- **H1** [ANSWERED] Migration must also place existing projects INTO the SDLC flow, not just the vault: mine existing requirements/plans/docs/tests/code state → draft artifacts (`status: mined-draft`, with provenance) → interview user ONLY on gaps/conflicts → set flow-state to detected phase → resume from there. Extends FR-16 (adoption step), FR-08 (brownfield mining mode), FR-07 (routes mined-drafts to validation). SRS 0.1.2.

## Branch I — Execution modes (added by user 2026-07-17 during M2)
- **I1** [ANSWERED] The flow offers two modes, chosen by asking the user (per project, recorded in flow-state): **gated** — user verifies as stakeholder at each milestone/phase gate; **auto** — pipeline proceeds without stopping, review sweeps self-verify as the gate, user questions get queued unless truly blocking. Extends FR-07 (mode in flow-state, gate enforcement), FR-08 (asks the mode at SRS validation), FR-12 (sweep = the gate in auto mode). SRS 0.1.3.

## Branch J — Stateless resumability (added by user 2026-07-17 during M2)
- **J1** [ANSWERED] "Continue project X" must work from a cold session using vault state ALONE — flow-state + open tickets + question queue + memory — never requiring the previous session's transcript. Therefore: state is checkpointed CONTINUOUSLY (after each significant step: ticket claimed/done, question answered, phase advanced), not only at session end. Session notes remain as journal/history, not as required state. Extends FR-07 (resume contract), FR-11 (workers checkpoint ticket state as they go), FR-14 (contract rule), FR-21 (doctrine). SRS 0.1.4.

## STATUS: INTERVIEW COMPLETE → SRS v0.1.3 VALIDATED → M1 done + swept → **AUTO MODE** (user, 2026-07-17): M2→M3→M4 chained, sweeps self-verify, non-blocking questions queued below

## Queued questions for the user (non-blocking, answer anytime)
- (none yet)

## Parking lot / user promised to explain later
- P1 [ANSWERED] Phase handoff = living docs + tickets in vault: Phase 1 (best model) → SRS + master plan; each phase reads predecessor's artifact, emits its own (design doc + ADRs → tickets w/ req IDs); agents on any platform claim tickets from vault; traceability req→design→code→test; a phase can't start until its input doc exists.

## Answered
(none yet)
