---
name: fr-17-swarm-skill-forge
description: swarm-skill-forge skill — author new high-quality skills with correct triggering descriptions, tested against the writing-quality bar
project: SwarmVault
type: spec
status: draft-for-validation
priority: should
requires: []
---

# FR-17 — `swarm-skill-forge` (skill authoring)

**Story:** As a user extending SwarmVault (or building my own skills), the framework
teaches the craft: when a skill is warranted, how to write a description that triggers
reliably, how to keep it lean, and how to verify it works (D1: "load skills creation skill
to do high quality skills for auto loading and knowing when to use each").

## Behavior

- Gate: is a skill the right tool? (vs a memory note, a CLAUDE.md line, or nothing).
- Structure: frontmatter (`name`, `description` with rich trigger phrasing — the
  description IS the router), body imperative and testable; heavy reference material split
  into `references/` loaded on demand (token economy); thin-wrapper pattern for
  user-invoked aliases.
- Quality bar: single job; no overlap with an existing catalog skill (extend it instead);
  examples included; platform-agnostic markdown (works via FR-06 adapters).
- Verification: dry-run the trigger (paraphrased user asks — does the description fire?);
  walk the skill on a toy case before shipping.
- New skills land in the project's own `.claude/skills/` (or the canonical dir if
  contributing to SwarmVault itself) and get an AGENTS.md index line for Codex.

## Acceptance criteria (EARS)

- A skill authored by following the skill shall carry: unique name, trigger-rich
  description, when-to-use, and at least one worked example.
- The skill shall require an overlap check against the installed catalog before creating a
  new skill.
- WHEN reference content exceeds ~150 lines, the skill shall direct it into `references/`
  files (NFR-M1).

## Influences (credited in FR-19)

superpowers writing-skills (TDD-for-docs rigor), Pocock's writing-great-skills (vocabulary
and predictability principles), Anthropic skill-authoring guidance.
