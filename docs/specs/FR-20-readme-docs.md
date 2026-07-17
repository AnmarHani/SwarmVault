---
name: fr-20-readme-docs
description: README with marketing hooks + quickstart, Obsidian setup guide, and the security-responsibility disclaimer
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-18-install]
---

# FR-20 — README & docs

**Story:** As a visitor hitting the GitHub page, I get it in 30 seconds (what, why, wow),
can start in 5 minutes, and know exactly what's my responsibility (F1, E3).

## README structure (draft direction — wording reviewed with user at M4)

1. **Hook:** name + tagline (candidates: *"One vault. Every agent. Zero amnesia."* /
   *"Your AI agents forget everything. SwarmVault doesn't."*) + badges + graph screenshot.
2. **The pitch:** three bullets — 🧠 *Shared brain*: 10 Claude Code + 10 Codex agents, one
   synchronized knowledge vault; 📐 *Real engineering*: requirements → design → tickets →
   tests → review, enforced, traceable; 💸 *Token-frugal*: query instead of re-reading,
   offload instead of carrying, tier models to tasks.
3. **60-second install:** the three doors, Door 1 (paste-to-agent) first.
4. **How it works:** one diagram (vault ⇄ agents ⇄ skills), the 11-skill catalog table,
   the SDLC flow.
5. **Features list** (from FR index), FAQ, Obsidian section (optional viewer — graph
   screenshot), security disclaimer, CREDITS pointer, license.

Tone: fun, direct, zero enterprise-speak. Human-lane document — full prose.

## Companion docs

- `docs/obsidian-guide.md` — pointing Obsidian at the vault, recommended core plugins
  (graph, backlinks), no community-plugin requirements.
- Security disclaimer (README + surfaced by swarm-init, NFR-S3): environment, installed
  packages, and data placed in the vault are the **user's** responsibility to audit; the
  framework ships no enforcement; isolation flags are cooperative filtering. Agents may
  *suggest* audits (the user may ask for one), but responsibility stays with the user.

## Acceptance criteria (EARS)

- README top section shall fit the what/why/install within one screen of scrolling.
- Every claim in the features list shall trace to a shipped FR (no vaporware bullets).
- The disclaimer shall appear in both README and swarm-init output.
- README wording shall get explicit user review before publish (F1).
