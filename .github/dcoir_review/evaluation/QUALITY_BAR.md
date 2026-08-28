# DCOIR Review quality bar

This document defines the evidence required before DCOIR Review may be described as approaching GitHub Copilot-level usefulness for this repository. It does **not** authorize autonomous branch mutation. Issue #293 remains separately blocked until the operator explicitly authorizes that stage.

## Publication architecture

DCOIR Review uses layered evidence rather than a confidence threshold alone:

1. changed-diff and full-file context are collected from the exact reviewed PR head;
2. deterministic risk sentinels identify rule-backed changed-line signals;
3. model candidates are normalized to added diff lines and contradiction/speculation filters run;
4. the v21 finding verifier checks publication evidence before ordinary model findings may proceed;
   - deterministic core sentinels are revalidated against the exact head-file line and cannot be vetoed by a model;
   - ordinary candidates receive a bounded independent judge pass using the exact line and full head-file context;
   - unsupported candidates are suppressed;
   - malformed, ambiguous, provider-failed, or overflow verifier states fail closed rather than publish unverified findings;
5. applyable GitHub suggestions are stricter than ordinary findings: detector-authored replacement text is stripped, independent fix synthesis runs after publication verification, exact single-line safety checks run, and only verified synthesis output may render a native `suggestion` fence.

## Measured evidence

The versioned precision corpus must report all of the following with zero fixture regressions:

- known false-positive fixtures and how many were suppressed;
- known true-positive fixtures and how many were retained;
- false-positive suppression rate;
- true-positive retention rate;
- context-priority regression results.

Production verifier readback additionally records:

- candidate findings;
- published findings;
- deterministic evidence-verified findings;
- model-judged findings;
- unsupported findings suppressed.

Live reviewer evidence must record the reviewed head SHA, DCOIR workflow run, context mode, finding anchors, and any native suggestion/fallback outcome.

## "Approaching Copilot-level usefulness" gate

All conditions below are required before that phrase may be used without qualification:

- **Corpus:** 100% known false-positive suppression and 100% known true-positive retention across the current versioned corpus, with zero fixture-level regressions.
- **Anchoring:** 100% of published findings are anchored to changed lines on the exact reviewed head; ambiguity or unanchored findings fail closed.
- **Verifier:** every ordinary model-generated published finding has concrete verifier evidence from the exact changed line plus full head-file context. Deterministic core-sentinel findings must independently re-match the exact head-file line.
- **Live precision:** across a rolling sample of at least 20 operator-dispositioned naturalistic findings, confirmed precision is at least 95%, with zero confirmed false-positive Critical/High findings. Suppressed candidates are not counted as published findings.
- **Suggestion safety:** across at least 10 live applyable-suggestion opportunities, 100% of rendered native suggestions are exact, single-line, diff-anchored, semantically safe repairs under operator disposition, with zero detector-authored or speculative replacements rendered as applyable suggestions.
- **Regression durability:** every confirmed false positive or missed high-signal true positive is captured as a permanent regression fixture before the corresponding hardening issue is closed.
- **No autonomy implication:** meeting this quality bar only establishes reviewer usefulness. Autonomous branch writes remain disabled until #293 is separately reviewed and the operator explicitly authorizes that capability.

## Current evidence boundary

The controlled `TEST ONLY — NEVER MERGE` PR #436 proves a live known true positive can survive final selection, pass the independent fix-synthesis path, and render as GitHub's native suggested-change component without mutating the PR branch. That is one controlled data point, not enough by itself to claim the rolling naturalistic precision or suggestion-safety sample requirements above.
