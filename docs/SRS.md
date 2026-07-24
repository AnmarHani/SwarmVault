---
name: swarmvault-srs
description: Software Requirements Specification for SwarmVault v1 — central agent knowledge vault + minimal SDLC skill catalog for Claude Code and Codex
project: SwarmVault
type: spec
status: draft-for-validation
version: 0.1.8
date: 2026-07-24
---

# SwarmVault — Software Requirements Specification (v1)

> Status: **draft for stakeholder validation**. Every requirement below traces to a decision
> in [requirements-tracker.md](requirements-tracker.md) (IDs A1–G2). Per-feature detail lives
> in [specs/](specs/) — this document is the master index and the contract.

## 1. Vision

SwarmVault is a free, open-source (MIT) framework for agentic coding platforms — Claude Code
and Codex first-class — built on two pillars:

1. **The Vault** — one central, Obsidian-compatible markdown knowledge base that every agent
   session reads from and writes to. Run 10 Claude Code agents and 10 Codex agents in
   parallel: they synchronize through the vault (shared memory, plans, tickets, decisions,
   session journals), not through fragile context handoffs. Obsidian is an optional viewer
   that adds the graph, backlinks, and a pleasant human reading experience — never a
   dependency.

2. **The Catalog** — eleven core skills (plus an optional orchestration add-on, FR-22), as
   minimal as possible and as high-quality as possible, that walk a project through the full
   software development lifecycle: requirements → design → implementation → testing → review —
   with a router that resumes any project from wherever it left off, on any platform.

The install story is the differentiator: *paste the repo URL into your agent, and the agent
integrates the framework itself.*

## 2. Stakeholders

| Stakeholder | Interest |
|---|---|
| Developers using coding agents | Persistent cross-session, cross-platform project knowledge; a disciplined SDLC their agents follow |
| The agents themselves | Primary *readers* of every artifact — docs must be written to be consumed by LLMs cheaply (token economy) |
| Framework maintainer (repo owner) | Simplicity: plain files, zero dependencies, no services to operate |
| Upstream skill authors | Correct attribution (CREDITS.md) — techniques learned from their work, never copied verbatim |
| Humans reading the vault in Obsidian | Full-prose, well-linked human-lane documents |

## 3. Scope

**In scope (v1):** vault structure + note schema; config/registry/marker resolution; query
CLI (BM25 search, filters, context injection, hooks) with `init`/`register`; sync engine;
write-isolation concurrency + ticket claim protocol; Claude Code + Codex adapters; the
eleven-skill core catalog (+ optional orchestration add-on) with budget/model-fit task
assignment, a cross-platform observability board, consent-gated usage-limit continuation, and
safe-state compaction; three-door install; CREDITS, README, Obsidian guide, security
disclaimer; token-economy doctrine.

**Out of scope (core):** security *enforcement* (isolation is cooperative); vector/embedding
search; a required background daemon or cron service; *automated launch/control* of platforms
beyond Claude Code and Codex (a broad roster is **recognized** as cooperative workers, but
only these two headless CLIs are spawned/controlled by the optional supervisor; the
plain-markdown core keeps others cheap to add later); non-markdown storage; contacting upstream
authors as a release gate. **In scope but optional:** a local orchestration supervisor (FR-22,
disabled and not installed by default) and consent-gated usage-limit continuation (FR-23,
works with or without the supervisor) — neither is ever required for vault, skills, or normal
parallel ticket work.

## 4. Constraints

- **C-1** Scripts run on stock Python ≥ 3.9 with **zero pip dependencies** (hand-rolled
  minimal frontmatter parser; no PyYAML). *(E4)*
- **C-2** The core is plain markdown + JSON config with no databases or required services.
  The optional supervisor persists only plain files and runs locally when the user enables
  it. *(B1, B4, K1)*
- **C-3** MIT license; no verbatim copying from upstreams; all influences credited. *(A4, D2)*
- **C-4** Scripts make **no network calls**. *(NFR-S)*
- **C-5** Primary OS targets: Linux, macOS, WSL. Native Windows best-effort. *(E4)*
- **C-6** Obsidian must never be required for any functionality. *(B1)*

## 5. Functional requirements (index)

Detail per feature in `specs/FR-XX-*.md`. Priorities: **M**ust / **S**hould / **C**ould for v1.

### Core infrastructure
| ID | Feature | Pri | Decisions |
|---|---|---|---|
| FR-01 | Vault structure & note schema (folders 00–90, frontmatter standard, templates) | M | B1 B2 B6 |
| FR-02 | Config file, vault registry, `.swarmvault` project markers | M | B2 B3 B8 |
| FR-03 | Query CLI: BM25 search, structured filters, `--show`, `--context`, `--hook`, JSON; `init` + `register` | M | B7 B3 |
| FR-04 | Sync engine: mirror memory/docs/sessions, MOC generation, idempotent + atomic | M | B4 B5 |
| FR-05 | Concurrency: write-isolation rules + ticket claim protocol | M | B4 C5 |
| FR-06 | Platform adapters: Claude Code (hooks, .claude/skills) + Codex (AGENTS.md index) | M | A3 B5 D3 |

### Skill catalog
| ID | Skill | Pri | Decisions |
|---|---|---|---|
| FR-07 | `swarm-flow` — SDLC router, resume-from-anywhere | M | D4 P1 |
| FR-08 | `swarm-spec` — requirements interview → SRS + feature specs + question queue; planning modes + review summary | M | C1 C2 C10 |
| FR-09 | `swarm-design` — architecture, stack options, ADRs | M | C3 |
| FR-10 | `swarm-design-ui` — design system, atomic design, UX laws, all interface types | M | C3 C4 |
| FR-11 | `swarm-implement` — tickets, claims, parallel workers, model tiering, tests-in-ticket | M | C5 C6 |
| FR-12 | `swarm-review` — milestone sweep: standards + simplification + requirement fulfillment | M | C7 C9 |
| FR-13 | `swarm-debug` — systematic debugging | M | D1 |
| FR-14 | `swarm-vault` — vault read/write/query conventions for any agent | M | B6 G1 |
| FR-15 | `swarm-init` — new-project onboarding, vault connect, default-vault option | M | E2 |
| FR-16 | `swarm-migrate` — existing-project migration + SDLC adoption (mine existing reqs/docs/state, enter the flow mid-phase) | M | E2 H1 |
| FR-17 | `swarm-skill-forge` — author new high-quality skills | S | D1 |
| FR-22 | Optional orchestration supervisor — dispatch, signals, recovery, quota scheduling; recognized agent roster | S | K1 K3 |
| FR-23 | Usage-limit continuation — consent-gated resume across quota resets (with/without supervisor) | S | K2 |
| FR-24 | Smart orchestration — budget/model-fit task assignment + cross-platform observability board | S | K5 |

### Distribution & cross-cutting
| ID | Feature | Pri | Decisions |
|---|---|---|---|
| FR-18 | Install: README bootstrap prompt + agent-oriented INSTALL.md + install.sh + manual path | M | E1 |
| FR-19 | CREDITS.md — every upstream author, repo, and what was learned | M | D2 |
| FR-20 | README (marketing hooks, features, quickstart), Obsidian guide, security disclaimer | M | E3 F1 |
| FR-21 | Token-economy doctrine + compact-writing guideline (machine lane) | M | G1 G2 |

## 6. Non-functional requirements (ISO 25010)

EARS notation: *ubiquitous* ("The X shall…"), *event* ("WHEN … the X shall…"), *state*
("WHILE …"), *unwanted* ("IF … THEN …").

**Performance efficiency**
- NFR-P1 WHEN searching a vault of up to 5,000 notes, the query CLI shall return results in
  under 2 seconds on commodity hardware.
- NFR-P2 The context injected at session start should stay within a configurable character
  budget (default 3,500 chars). This is a **guideline, not a hard cap**: it exists to curb
  habitual bloat, and is exceeded without ceremony whenever completeness or quality
  genuinely needs more. Needed context is never dropped to satisfy the number.
- NFR-P3 *(token economy — G1)* All catalog skills shall practice offload-don't-carry:
  durable state is written to the vault and referenced by note name, not re-explained in
  conversation context.
- NFR-P4 *(G2)* Machine-lane artifacts (tickets, claims, question-queue entries, session
  notes, memory descriptions) shall follow the compact-writing guideline; human-lane
  documents (SRS, design docs, ADRs, README) shall remain full prose.

**Reliability**
- NFR-R1 Running sync twice in a row shall produce zero changes on the second run
  (idempotence).
- NFR-R2 IF a SessionStart/SessionEnd hook fails for any reason, THEN it shall exit 0 and
  never break the agent session.
- NFR-R3 All writes to shared notes shall be atomic (write-temp + rename); sync runs shall
  serialize via a single lock file.
- NFR-R4 WHEN two agents attempt to claim the same ticket, exactly one claim shall win
  (first atomic claim-file creation) and the loser shall be able to detect it.

**Compatibility & portability**
- NFR-C1 The vault shall be fully functional (query, sync, all skills) without Obsidian
  installed.
- NFR-C2 Scripts shall run on stock Python ≥ 3.9 with no third-party packages.
- NFR-C3 All paths shall come from the config file — no hardcoded usernames or home
  directories anywhere.

**Usability**
- NFR-U1 An agent given the repo URL shall be able to complete installation in a single
  session, asking the user only the questions defined in INSTALL.md.
- NFR-U2 A human following README quickstart shall reach a working setup with one script
  invocation.
- NFR-U3 WHEN a skill needs a decision, it shall present options with a recommendation and
  accept free-text answers (never force a menu).

**Security** *(cooperative model — B8, E3)*
- NFR-S1 Scripts shall make no network calls.
- NFR-S2 Isolation flags shall be honored by the query CLI (isolated projects excluded from
  cross-project results and other projects' context), and documentation shall state plainly
  that this is cooperative filtering, not a security boundary.
- NFR-S3 README and swarm-init shall carry the responsibility disclaimer: auditing the
  environment, packages, and data placed in the vault is the user's responsibility, not the
  framework author's.

**Maintainability**
- NFR-M1 Each skill is one SKILL.md (+ optional references/ loaded on demand); each script
  stays single-file.
- NFR-M2 The simplicity doctrine applies to the framework itself: prefer deleting features
  to adding them; every addition must justify itself against the copy-paste-simple install
  story.

## 7. Traceability scheme

`FR-ID → ticket → commit → test → review`: tickets carry their FR-ID; commits use
Conventional Commits with the FR-ID in scope (`feat(FR-11): …`); tests name the FR they
verify; the milestone sweep (FR-12) checks every Must requirement has a fulfilled,
tested implementation before a milestone closes. *(C8)*

## 8. Build milestones (the plan this SRS drives)

- **M1 — Vault core**: FR-01…FR-05 (structure, config/registry, query CLI, sync, claims).
  Exit: NFR-R1/R2/R3 verified by tests; scripts pass on a fresh fixture vault.
- **M2 — Skill catalog**: FR-07…FR-17, FR-21. Exit: every skill reviewed against
  writing-quality bar; flow router walks a toy project end-to-end.
- **M3 — Adapters & install**: FR-06, FR-18. Exit: clean-machine install via all three
  doors; Claude Code hooks fire; Codex AGENTS.md path exercised.
- **M4 — Docs & release**: FR-19, FR-20. Exit: README review with user; CREDITS complete;
  license check on superpowers upstream done; publish to GitHub.
- **M5 — Optional autonomy add-on**: FR-22, FR-23, FR-24. Exit: disabled-default install
  verified; simulated Claude/Codex adapters prove dispatch, heartbeat recovery, and quota
  wait/resume without duplicate ticket ownership; usage-limit continuation records a
  consent-gated resume that surfaces in context and self-clears on completion; the scheduler
  routes tasks by budget/model-fit and the board renders the swarm cross-platform.

Each milestone ends with a strong-model review sweep (the framework eating its own food).

## 9. Changelog

- **0.1.8** (2026-07-24, user follow-up) — **Smart orchestration & observability (K5) +
  safe-state compaction (K6):** FR-24 adds capability- and budget-aware task assignment
  (biggest tasks → most-budget platform, capability first; small tasks → least-budget;
  per-kind model provisioning; empty/quota platforms skipped) and a cross-platform
  observability `board` (ticket + usage/limit bars incl. weekly caps and tokens used/limit,
  per-agent platform·model·effort·task·progress, prompts, recent changes) viewable from any
  single CLI. FR-21 gains safe-state `checkpoint`/compaction — compact to save tokens only at
  resumable boundaries, quality first. Model strengths are a method keyed to
  artificialanalysis.ai, not a pinned leaderboard.

- **0.1.7** (2026-07-24, user follow-up) — **Real launch adapters (K4):** FR-22 gains a
  declarative, user-overridable launch-adapter registry — verified (Claude Code, Codex),
  best-effort defaults (Gemini, OpenCode, Droid, Cursor, Copilot; write-only, flags to verify),
  and a `--launch-cmd` template to wire any other CLI agent. Safety invariant: a read-only
  request never launches a writing agent; an unknown platform/mode records a manual-action
  request instead of guessing. Per-platform worker counts are respected on dispatch.

- **0.1.6** (2026-07-24, user feedback pass) — Four additions: (C10) swarm-spec gains
  **planning modes** (ask-each / recommend-all / hybrid) framed as clarify-not-grill, and a
  **skimmable SRS review summary** before the approval gate — FR-08 updated. (C4+) swarm-design-ui
  gains a **design-system-proposal** flow (≥2 filled directions, per-page layout options) and a
  compact on-demand `style-menu` reference (categories, styles, patterns, checklist.design, UX
  laws, color/type/psychology tools) — FR-10 updated. (K2) **usage-limit continuation** —
  consent-gated resume across quota resets via a durable `plan-continue` record that surfaces in
  context and self-clears — FR-23 added. (K3) **recognized agent roster** (broad set as
  cooperative workers; control stays with Claude Code + Codex) + a per-platform worker-count
  setup question — FR-22 and install updated. swarm-implement craft guidance sharpened
  (simplicity/reuse/readability/maintainability, comment discipline).

- **0.1.5** (2026-07-18, user addition) — Optional orchestration supervisor (K1): add a
  local, explicit opt-in control plane for role/model-aware dispatch, per-agent signals,
  stale-worker recovery, and scheduled continuation after quota waits. Core SwarmVault
  remains daemon-free and fully functional without it. FR-22 added.

- **0.1.4** (2026-07-17, user addition during M2) — Stateless resumability (J1):
  "continue project X" works from a cold session on vault state alone; skills checkpoint
  state continuously (ticket claimed/done, question answered, phase advanced), never
  relying on session transcripts. FR-07, FR-11, FR-14, FR-21 updated.

- **0.1.3** (2026-07-17, user addition during M2) — Execution modes (I1): the flow asks
  once per project whether milestones are user-gated or fully autonomous (sweeps
  self-verify, questions queued unless blocking). FR-07, FR-08, FR-12 updated.

- **0.1.2** (2026-07-17, user addition during M1) — Brownfield SDLC adoption (H1):
  swarm-migrate gains an adoption step that mines existing requirements/plans/docs/code
  state into `mined-draft` artifacts, interviews only on gaps, and enters the flow
  mid-phase. FR-16, FR-08, FR-07 updated.

- **0.1.1** (2026-07-17, validation feedback) — NFR-P2 softened: the context budget is a
  guideline, not a hard cap; quality wins when they conflict. Propagated to FR-03, FR-14,
  FR-21.
- **0.1.0** (2026-07-17) — initial draft from the requirements interview
  (requirements-tracker.md rounds 1–7).

## 10. Glossary

- **Vault** — the central markdown knowledge base (Obsidian-compatible).
- **Machine lane / human lane** — artifacts written primarily for agents (compact) vs for
  humans (full prose).
- **MOC** — Map of Content; a project's index note.
- **Claim file** — atomic marker a worker writes to take ownership of a ticket.
- **Three doors** — the install paths: agent bootstrap, install.sh, manual copy.
- **EARS** — Easy Approach to Requirements Syntax (acceptance-criteria patterns).
