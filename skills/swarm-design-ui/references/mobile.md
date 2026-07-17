# Mobile interface guidance (native & cross-platform)

**Platform conventions win** (Jakob's law): iOS — HIG navigation (tab bar, back-swipe,
SF-adjacent type); Android — Material (nav drawer/bottom nav, predictive back). A
cross-platform framework still adapts per platform: navigation patterns, ripple vs
highlight, system fonts.

**Ergonomics.** Thumb zone: primary actions bottom-center/right; destructive actions out
of casual reach; touch targets ≥ 44 pt (iOS) / 48 dp (Android) with ≥ 8 spacing; one-hand
use is the default assumption for phones.

**Structure.** One primary task per screen; progressive disclosure over dense screens;
system back must never lose user work; state restoration after backgrounding.

**Feedback.** Haptics sparingly and semantically; optimistic UI with rollback for slow
networks; offline states designed, not accidental (queue + retry visible).

**Type & spacing.** Dynamic Type / font scaling respected — layouts must survive 130%
text; spacing tokens; safe-area insets everywhere (notches, home indicator).

**A11y.** VoiceOver/TalkBack labels on all controls; contrast AA; motion reduced when
requested; never color-only signaling.
