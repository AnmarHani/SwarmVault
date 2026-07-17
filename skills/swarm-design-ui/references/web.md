# Web interface guidance

**Layout.** Design mobile-first; define breakpoints by content breaking, not device names.
CSS grid for page structure, flexbox for components. Max content width (~65–75ch for
prose). The page never scrolls horizontally; wide content scrolls inside its own
container.

**Semantics & a11y.** Semantic HTML first (nav/main/article/button — not div soup);
one h1; visible focus rings; skip-link; forms with real labels and inline validation;
WCAG AA contrast (4.5:1 text, 3:1 large/UI); `prefers-reduced-motion` and
`prefers-color-scheme` respected.

**Type & spacing.** rem-based modular scale; line-height 1.4–1.7 body, tighter for
headings; spacing tokens only (no magic numbers); vertical rhythm consistent.

**States.** Every interactive element: hover, focus, active, disabled. Every async
surface: loading (skeleton > spinner), empty (helpful, not blank), error (recovery
action included).

**Performance is UX.** Ship the minimum JS; images sized and lazy; measurable target:
interactive < 3 s on mid-tier mobile; no layout shift on load.

**Distinct mobile design** where the SRS calls for it: thumb-reachable primary actions,
bottom navigation over hamburger where task-frequency justifies it, touch targets
≥ 44×44 px.
