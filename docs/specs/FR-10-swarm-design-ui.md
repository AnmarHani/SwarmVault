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
- Interviews for: brand/identity direction (with variations), audience, platform
  conventions; then produces a **design-system doc**: color (accessible palettes),
  typography scale, spacing/box-model system, grid + auto-layout containers, atomic
  component inventory (atoms → components → templates → pages), responsive rules +
  distinct mobile design where relevant, interaction/motion notes.
- **Per-interface guidance** lives in `references/` loaded on demand (token economy):
  web, mobile, desktop, TUI, CLI (help text, flags, exit codes and error style are design
  too).
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
- Brand direction shall be offered as ≥2 distinct variations before locking one.

## Influences (credited in FR-19)

Laws of UX (Yablonski), roadmap.sh/design-system, Frost's Atomic Design, Figma typography
resource, Anthropic frontend-design skill (taste stance), snyk top-UI-skills survey,
user-supplied design principles list.
