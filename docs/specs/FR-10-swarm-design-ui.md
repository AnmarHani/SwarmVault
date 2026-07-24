---
name: fr-10-swarm-design-ui
description: swarm-design-ui skill — design system and UX for any interface type (TUI, CLI, Web, Mobile, Desktop): brand, atomic design, spacing, typography, UX laws
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-08-swarm-spec]
---

# FR-10 — `swarm-design-ui` (UI/UX design phase)

**Story:** As a project owner building anything with an interface, I get an intentional,
consistent design system — not templated defaults — sized to my interface type, with the
taste decisions put to me (C3/C4).

## Behavior

- Runs alongside swarm-design when the SRS declares any user interface; skipped otherwise
  (swarm-flow decides).
- Interviews (light, options-first) for: brand/identity direction, audience, platform
  conventions, accessibility, existing assets.
- **Proposes a design system with the user (C4):** from the product's category and
  personality it synthesizes a **recommended** design system and ≥1 **distinct alternative**,
  each presented as a filled-in panel (pattern/layout, style family, color roles, typography,
  effects, domain anti-patterns), so the user chooses from something concrete. The style /
  category / pattern vocabulary is a menu to reason from, **not a cage** — the skill designs
  for the product's real needs.
- Then produces a **design-system doc**: color (accessible palettes), typography scale,
  spacing/box-model system, grid + auto-layout containers, atomic component inventory
  (atoms → components → templates → pages), **per-page layout chosen from offered options**
  (landing-page and dashboard patterns), responsive rules + distinct mobile design where
  relevant, interaction/motion notes.
- **On-demand references** loaded per need (token economy): per-interface guidance
  (`web`, `mobile`, `desktop`, `tui-cli` — for TUI/CLI, help text, flags, exit codes and
  error style are the design), plus `style-menu` (product categories, style families, layout
  patterns, the proposal-panel template, and resources: checklist.design, Laws of UX,
  color/type/psychology and accessibility tools).
- Applies UX laws (Fitts, Hick, Jakob, Miller, proximity/common-region…) as review
  checklist, not jargon dump.
- Output: `docs/design-ui.md` + component inventory; mirrored to vault; user validation
  gate; flow-state updated.

## Acceptance criteria (EARS)

- Every screen/surface implied by an FR shall appear in the component/page inventory
  (traceability to FR-IDs).
- The design system shall define color, type, and spacing as *tokens/scales* (calculated,
  consistent) — never per-screen ad-hoc values.
- WHEN the interface type is TUI or CLI, the skill shall NOT load web/mobile guidance
  (references split keeps context lean — NFR-P3).
- Accessibility shall be addressed explicitly (contrast, focus, touch targets) for
  graphical interfaces.
- Brand direction shall be offered as ≥2 distinct, fully-specified design-system directions
  (the proposal panel) before locking one.
- WHEN a screen has more than one reasonable layout, THEN the skill shall offer layout options
  (e.g. landing-page or dashboard patterns) and record the chosen one with its rationale,
  rather than defaulting silently.
- WHEN the interface is graphical, THEN the style/category menu shall be treated as guidance
  that does not constrain the design to its listed options.

## Influences (credited in FR-19)

Laws of UX (Yablonski, lawsofux.com), roadmap.sh/design-system, Frost's Atomic Design, Figma
typography resource, NameThatUI (namethatui.com — precise component vocabulary, added
2026-07-17), checklist.design (per-element/page checklists, added 2026-07-24), Anthropic
frontend-design skill (taste stance), snyk top-UI-skills survey, user-supplied design
principles list and design-system-proposal pattern.
