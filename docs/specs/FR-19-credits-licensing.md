---
name: fr-19-credits-licensing
description: CREDITS.md and licensing hygiene — every upstream influence named with author, repo, and what was learned; MIT for the whole repo; no verbatim copying
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: []
---

# FR-19 — Credits & licensing

**Story:** As an upstream author whose ideas shaped SwarmVault, I find my name, my repo,
and an honest description of what was learned from my work — and as a user, I get a clean
MIT license with no provenance landmines (A4, D2).

## Content of CREDITS.md

One entry per influence: author, link, license (as found / "none published"), and
specifically what SwarmVault learned. Known roster (from the inventory; verify links at
publish):

- **Jesse Vincent (obra) — superpowers** (MIT expected; verify): systematic-debugging,
  writing-plans/executing-plans, subagent-driven-development, test-driven-development,
  verification-before-completion, writing-skills, brainstorming → shaped swarm-spec,
  swarm-implement, swarm-debug, swarm-review, swarm-skill-forge.
- **Matt Pocock — skills / aihero.dev** (no license found): grilling/grill-me, to-spec,
  to-tickets, implement, code-review, codebase-design, domain-modeling,
  writing-great-skills → shaped swarm-spec (interview stance), swarm-implement (tickets),
  swarm-review, swarm-design, swarm-skill-forge.
- **Jeffallan — skills collection** (MIT inline): feature-forge, spec-miner,
  architecture-designer, api-designer, code-reviewer, security-reviewer, the-fool,
  debugging-wizard, test-master → shaped swarm-spec, swarm-design, swarm-review,
  swarm-debug.
- **caveman plugin** (author unidentified; note honestly): token-compression inspiration →
  compact-writing guideline in swarm-vault.
- **euxx — claude-skills-for-copilot code-simplifier**: simplification stance in
  swarm-implement/swarm-review.
- **References:** ISO 25010; EARS; Laws of UX (Jon Yablonski); Atomic Design (Brad Frost);
  roadmap.sh/design-system; refactoring.guru; workingsoftware.dev NFR guide;
  geeksforgeeks SE articles; Figma typography guide; Conventional Commits; ADRs (Michael
  Nygard); the author's original Claude Vault design.

## Acceptance criteria (EARS)

- Every SwarmVault skill's SKILL.md shall name its influences in one footer line pointing
  at CREDITS.md.
- The repo shall contain LICENSE (MIT) and no file copied verbatim from an upstream
  (D2 — spot-checked at the M4 review sweep).
- WHEN an upstream's license cannot be confirmed at publish time, CREDITS.md shall say so
  plainly rather than guessing.
