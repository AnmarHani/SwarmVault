---
name: fr-13-swarm-debug
description: swarm-debug skill — systematic root-cause debugging discipline; findings and fixes recorded to the vault so the same bug never costs twice
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-14-swarm-vault]
---

# FR-13 — `swarm-debug` (debugging)

**Story:** As a developer with a real bug, the agent follows a systematic method — evidence
before hypotheses, hypotheses before fixes — instead of shotgun-patching, and the diagnosis
lands in the vault as memory.

## Behavior

- Phases: reproduce → gather evidence (errors, logs, traces — read them fully) → locate
  (binary-search the causal chain, instrument if needed) → hypothesize (ranked, cheapest
  test first) → verify hypothesis with a targeted experiment → fix root cause (not symptom)
  → regression test proving the fix → record.
- Hard rules: never claim a fix without a reproduced-then-passing test; never patch around
  a symptom when the root cause is reachable; if three hypotheses die, step back and
  re-examine assumptions (question the spec/design too).
- **Vault memory:** non-trivial diagnoses → memory note (footgun/gotcha) + code-note link
  on the affected file (C8), so future sessions inherit the knowledge (G1).

## Acceptance criteria (EARS)

- WHEN invoked on a bug, the skill shall demand a reproduction (or explicitly record why
  one is impossible) before any fix is proposed.
- Every fix shall ship with a regression test that fails on the pre-fix code.
- WHEN a diagnosis reveals a spec or design gap, the skill shall route the gap to the
  question queue / change log (FR-08 management step) rather than silently patching.
- Diagnosis summaries shall be written machine-lane; ≤ 15 lines in the memory note (G2).

## Influences (credited in FR-19)

superpowers systematic-debugging (the method), Pocock's diagnosing-bugs (diagnosis loop),
Jeffallan's debugging-wizard (log/stack correlation).
