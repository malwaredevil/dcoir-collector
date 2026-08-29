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
5. applyable GitHub suggestions are stricter than ordinary findings: detector-authored replacement text is stripped; a dedicated repair-author AI runs only after publication verification; the exact one-line candidate must pass deterministic prechecks; a separate repair-critic AI independently evaluates that already-verified repair; deterministic exact-head validation runs again; and only an accepted, exact, single-line repair may render a native `suggestion` fence.

The verifier, repair author, repair critic, and deterministic validators have separate responsibilities. A repair-stage failure must not erase a verified finding, but it must withhold the one-click suggestion. No stage in this architecture writes to the PR branch.

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

Live reviewer evidence must record the reviewed head SHA, DCOIR workflow run, context mode, finding anchors, and any native suggestion/fallback outcome. Verified-repair evidence must additionally record the repair-author model and confidence, repair-critic model and confidence, critic disposition, exact replacement text, and final deterministic suggestion outcome.

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

The controlled `TEST ONLY — NEVER MERGE` PR #436 proves a live known true positive can survive final selection and render as GitHub's native suggested-change component without mutating the PR branch. That established the GitHub-native rendering mechanism.

The separate controlled `TEST ONLY — NEVER MERGE` PR #437 proves the stricter ordinary semantic path end to end. On unchanged probe head `f59f8da397276718b64cc9fa034b2a4228cc86da`, DCOIR Review run `33244004569` used deep full-file context with zero risk-sentinel anchors, published one ordinary model-judged finding at the exact changed line, passed it through the independent finding verifier, invoked a dedicated repair author, invoked a separate repair critic, passed deterministic exact-line validation, and rendered a native GitHub suggestion. The repair author proposed `return age_minutes >= 0 and age_minutes <= 60` at confidence 1.00; the served repair critic accepted that exact repair at confidence 0.97; and the final repair metric recorded one verified finding, one native suggestion, and zero fallback/declined suggestions. The PR branch remained unchanged.

These are controlled quality data points, not a claim that the rolling naturalistic precision or suggestion-safety sample requirements above have been met. In particular, #293 remains blocked and autonomous branch writes remain unauthorized.
