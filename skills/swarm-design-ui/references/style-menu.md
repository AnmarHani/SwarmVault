# Style menu — categories, styles, patterns & resources

A **menu to reason from, not a cage.** Match the product to a starting point, then design for
its real needs. Load this only when designing a graphical UI (skip for TUI/CLI).

## 1. Product categories (pick the closest, borrow from neighbors)

- **Tech & SaaS** — SaaS, micro-SaaS, B2B service, developer tool / IDE, AI / chatbot,
  cybersecurity, data platform.
- **Finance** — fintech / crypto, banking, insurance, personal-finance tracker, invoicing.
- **Healthcare** — clinic, pharmacy, dental, veterinary, mental health, medication reminder.
- **E-commerce** — general, luxury, P2P marketplace, subscription box, food delivery.
- **Services** — beauty / spa, restaurant, hotel, legal, home services, booking / appointments.
- **Creative** — portfolio, agency, editorial.
- **Lifestyle** — habit tracker, recipes, meditation, weather, diary, mood tracker.
- **Emerging** — web3 / NFT, spatial computing, robotics/drones.

## 2. Style families (representative — not exhaustive; combine freely)

| Family | Feel | Best for |
|---|---|---|
| Minimal / Swiss | clean, gridded, restrained | dashboards, docs, enterprise |
| Soft UI / Neumorphism | soft shadows, calm depth | wellness, beauty, premium services |
| Glassmorphism / Aurora | translucent, gradient light | modern SaaS, fintech, hero sections |
| Flat / Material | direct, familiar | web/mobile apps, MVPs |
| Bento grid | modular cards | product pages, dashboards, portfolios |
| Neubrutalism | bold borders, raw, playful | Gen-Z brands, startups, Figma-native |
| Dark / OLED | high-contrast dark | coding, night-mode, media apps |
| Editorial / Magazine | typographic, column-driven | news, blogs, content brands |
| 3D / product preview | immersive, tactile | e-commerce, furniture, hardware |
| Organic / biophilic | natural shapes & tones | sustainability, wellness, biotech |
| Cyberpunk / HUD FUI | neon, sci-fi instrumentation | gaming, crypto, security |
| Motion / kinetic type | animated storytelling | launches, marketing, portfolios |
| Accessible / inclusive | clarity, WCAG-first | gov, healthcare, education |

## 3. Layout patterns

**Landing pages:** hero-centric · conversion-optimized · feature-rich showcase · minimal &
direct · social-proof-focused · interactive product demo · trust & authority · storytelling.
Choose by goal: emotion/brand → hero or storytelling; lead-gen → conversion; complex product →
feature showcase; B2B → trust & authority.

**Dashboards / BI:** data-dense · executive summary · real-time monitoring · drill-down ·
comparative · predictive · user-behavior · financial. Choose by the reader's job (glance vs
explore vs forecast).

## 4. Design-system proposal panel (present ≥2 filled-in directions)

```
DESIGN SYSTEM — <RECOMMENDED | ALTERNATIVE>            target: <product>
  Pattern/layout : <pattern>            why: <conversion / trust / clarity rationale>
  Style          : <style family>       best for: <fit>   perf/a11y: <note>
  Colors         : primary <#> · surface <#> · accent/CTA <#> · bg <#> · text <#>
                   semantic: success/warn/error · WCAG-AA contrast checked
  Typography     : <display> / <body>   scale: <ratio>    mood: <…>
  Effects        : shadows <…> · transitions 150–300ms · hover/focus states
  Avoid          : <domain anti-patterns, see §6>
  Sections/pages : 1.<…> 2.<…> 3.<…>
```

## 5. Resources (search these; cite what you use)

- **Components/patterns checklist:** [checklist.design](https://www.checklist.design) — per
  element/page checklists (forms, tables, modals, onboarding, empty states…).
- **Component names:** [namethatui.com](https://namethatui.com).
- **UX laws / psychology:** [lawsofux.com](https://lawsofux.com) — Fitts, Hick, Jakob, Miller,
  Doherty, von Restorff, aesthetic-usability, peak-end.
- **Color:** contrast — WebAIM contrast checker; palettes — Coolors, Adobe Color, Realtime
  Colors; check both light and dark, and color-blind safety.
- **Type pairing:** Google Fonts, Fontpair, Typescale (modular scale).
- **Accessibility:** WCAG 2.2 AA (4.5:1 text, 3:1 large/UI), focus order, reduced-motion.

## 6. Anti-patterns to avoid (unless the brief truly wants them)

Default AI purple/pink gradients · emojis used as UI icons (use SVG sets: Lucide, Heroicons) ·
harsh/instant animations · neon on white · walls of equal-weight text (no hierarchy) ·
carousels for primary content · mystery-meat navigation · color as the only signal ·
dark-pattern CTAs.

## 7. Pre-delivery checklist

- [ ] No emojis as icons (SVG icon set instead)
- [ ] `cursor: pointer` on all clickable elements; visible hover with 150–300ms transition
- [ ] Focus states visible for keyboard navigation; logical tab order
- [ ] Text contrast ≥ 4.5:1 (light and dark); UI/large ≥ 3:1
- [ ] `prefers-reduced-motion` and `prefers-color-scheme` respected
- [ ] Responsive at 375 / 768 / 1024 / 1440; no horizontal body scroll
- [ ] Loading, empty, and error states designed — not blank
- [ ] Every screen traces to an FR-ID in the component inventory
