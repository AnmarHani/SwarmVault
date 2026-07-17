---
name: swarm-design-ui
description: UI/UX design phase — intentional design system (brand, color, typography, spacing, atomic components) and UX for any interface type: Web, Mobile, Desktop, TUI, or CLI. Use when the SRS declares a user interface, when defining a design system or visual identity, or when reviewing UI work against UX laws.
---

# swarm-design-ui — UI/UX design phase

**Gate:** validated SRS declaring a user interface. Runs alongside swarm-design.
The goal is intentional, consistent design — not templated defaults.

**Load only the reference for the interface type at hand** (token economy):
`references/web.md`, `references/mobile.md`, `references/desktop.md`,
`references/tui-cli.md`.

## Interview first

Audience and context of use; brand personality (offer **≥2 distinct direction
variations** — e.g. "clinical precision" vs "warm craft" — before locking one); platform
conventions to honor; accessibility requirements; existing brand assets.

## Produce: the design-system doc (`docs/design-ui.md`)

Everything as **tokens and scales**, never per-screen ad-hoc values:

1. **Color** — palette with roles (background/surface/primary/accent/semantic), light +
   dark, WCAG-AA contrast checked.
2. **Typography** — 1–2 families, a modular size scale, line-height and weight rules.
3. **Spacing & box model** — one spacing scale (e.g. 4px base), consistent
   margin/border/padding discipline, grid + auto-layout container rules.
4. **Atomic inventory** — atoms → components → templates → pages; every screen implied by
   an FR appears here, traced to its FR-ID. Use the *correct component names*
   ([namethatui.com](https://namethatui.com) is the dictionary): "drawer", "segmented
   control", "combobox" — not "that sliding panel". Precise names in specs and tickets
   mean every agent builds the same thing; when the user describes a component vaguely,
   resolve it to its proper name and confirm.
5. **Responsive rules** — breakpoints, and a genuinely distinct mobile design where the
   SRS calls for mobile (not a shrunken desktop).
6. **Motion & interaction** — states (hover/focus/active/disabled/loading/error), timing.

## UX-laws checklist (apply as review, not jargon)

Fitts (targets big and near) · Hick (fewer choices at decision points) · Jakob (follow
platform conventions) · Miller (chunk information) · proximity/common-region (group
related things) · Doherty (feedback < 400 ms) · error prevention over error messages.

## Rules

- Accessibility is explicit for graphical UIs: contrast ratios, focus order, touch
  targets, reduced-motion.
- TUI/CLI projects: skip all graphical guidance; help text, flags, exit codes, and error
  style ARE the design (see `references/tui-cli.md`).
- End with user validation (gated) or FR-coverage self-check (auto); update flow-state.

---
*Influences: Laws of UX (Yablonski); Atomic Design (Frost); roadmap.sh/design-system;
Figma typography guide; NameThatUI (component vocabulary); Anthropic frontend-design
skill — see CREDITS.md.*
