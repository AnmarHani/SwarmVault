---
name: fr-14-swarm-vault
description: swarm-vault skill — the contract every agent follows to read, write, and query the vault; embodies the token-economy doctrine
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-01-vault-structure, fr-03-query-cli]
---

# FR-14 — `swarm-vault` (vault contract)

**Story:** As any agent on any platform, one skill tells me exactly how to use the vault:
when to query instead of exploring, what to write where, in which lane, and how to stay
cheap (B6, G1).

## Behavior — the contract

- **Read path:** query first (`swarmvault.py query --search …`), descriptions before
  bodies, `show` only what's needed; repo exploration only for what the vault can't answer.
- **Write path:** which artifact goes where (memory → platform memory dir, mirrored;
  session journal → own file; specs/tickets → 30 Plans; ADRs → 50 Decisions; code-notes →
  10 Projects/<P>/code-notes/); frontmatter schema (FR-01); `[[links]]` liberally;
  own-files-only rule (FR-05).
- **Token-economy doctrine (G1):** offload-don't-carry (write state, reference by name);
  budget guidelines observed — quality wins on conflict, take more context when genuinely
  needed; handoff-by-vault — end long sessions by writing a resume note, next
  session (cheaper model, fresh context) picks it up; machine-lane compact style (G2) with
  the compact-writing guideline inline (imperative, telegraphic, no filler — quality
  content, minimal tokens).
- **Isolation etiquette:** respect isolation flags; never quote isolated-project content
  into another project's notes (NFR-S2).

## Acceptance criteria (EARS)

- The skill shall be loadable by both platforms (plain SKILL.md; referenced by the Codex
  AGENTS.md index and Claude Code skills dir — FR-06).
- An agent following the skill on a registered project shall find memory, plans, and
  sessions without one repo-wide Grep (the vault answers first).
- The compact-writing guideline shall include before/after examples and the rule "never
  compress human-lane documents" (G2).
- The skill shall document the resolution rules (FR-02) so agents can self-diagnose "why
  is the vault not finding my project".

## Influences (credited in FR-19)

The author's original Claude Vault design (CLAUDE.md contract, vault_query doctrine);
caveman plugin (compression inspiration — technique rewritten); Obsidian/Zettelkasten MOC
practice.
