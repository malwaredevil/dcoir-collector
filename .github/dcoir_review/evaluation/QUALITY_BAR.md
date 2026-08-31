# DCOIR Review quality bar

This document defines the evidence required before DCOIR Review may be described as approaching GitHub Copilot-level usefulness for this repository. It does **not** authorize autonomous branch mutation. Issue #293 remains separately blocked until the operator explicitly authorizes that stage.

## Publication architecture

DCOIR Review uses layered evidence rather than a confidence threshold alone:

1. changed-diff and full-file context are collected from the exact reviewed PR head;
2. deterministic risk sentinels identify rule-backed changed-line signals;
3. broad model review and independent semantic challenge generate hypotheses; the semantic adjudicator collapses duplicate variants, rejects unsupported speculation, and keeps a Pareto-small set of demonstrable root causes;
4. the v21 finding verifier checks publication evidence before ordinary model findings may proceed;
   - deterministic core sentinels are revalidated against the exact head-file line and cannot be vetoed by a model;
   - ordinary candidates receive a bounded independent judge pass using the exact line and full head-file context;
   - unsupported candidates are suppressed;
   - malformed, ambiguous, provider-failed, or overflow verifier states fail closed rather than publish unverified findings;
5. applyable GitHub repairs are stricter than ordinary findings. Detector-authored replacement text is stripped. Only verifier-supported findings inside the bounded repair budget enter the v36 repair-set pipeline:
   - a frontier repair-author AI proposes the smallest complete coordinated repair as one or more exact edit blocks;
   - every edit names an exact repository path, inclusive head-file line range, exact original block, replacement block, and purpose;
   - deterministic prechecks require the original blocks to match the exact reviewed head, reject overlapping or stale ranges, enforce edit/size bounds, and syntax-check supported structured formats;
   - an independent frontier model from a different model family critiques the **whole repair set**, including completeness and whether each edit is necessary for the verified root cause;
   - the entire set is deterministically reapplied and revalidated after critic acceptance;
   - a contiguous edit whose full range is commentable on the PR's right-side diff may render as a native ranged `suggestion` fence;
   - non-contiguous or cross-file repairs may render as several linked native suggestions when each edit is independently diff-commentable;
   - a necessary edit outside the commentable PR diff remains explicit coordinated guidance rather than being silently omitted or presented as an invalid clickable suggestion.

The verifier, repair author, repair critic, and deterministic validators have separate responsibilities. Repair-set acceptance is all-or-nothing: DCOIR must not knowingly publish a partial subset of a repair that requires companion edits. A repair-stage failure must not erase a verified finding; it withholds applyable repair blocks and leaves honest repair guidance instead. Deterministic sentinel findings retain canonical rule-backed wording even when a repair set is available. No stage in this architecture writes to the PR branch.

## Measured evidence

The versioned precision and semantic-recall corpora must report their governed regression results with zero fixture regressions, including:

- known false-positive fixtures and how many were suppressed;
- known true-positive fixtures and how many were retained;
- false-positive suppression rate;
- true-positive retention rate;
- context-priority regression results;
- generalized semantic-recall classes covering accepted naturalistic misses such as polarity/rejection, scope binding, representation variants, duplicate forms, mode eligibility, and positive-token leakage, plus clean controls that must remain suppressed.

Production verifier readback additionally records:

- candidate findings;
- published findings;
- deterministic evidence-verified findings;
- model-judged findings;
- unsupported findings suppressed.

Live reviewer evidence must record the reviewed head SHA, DCOIR workflow run, context mode, finding anchors, and any native repair/guidance outcome. Verified-repair evidence must additionally record the repair-set ID, every edit path/range, exact original and replacement blocks, repair-author model and confidence, repair-critic model and confidence, critic disposition, native-vs-guidance eligibility for each edit, and final deterministic repair-set outcome.

## "Approaching Copilot-level usefulness" gate

All conditions below are required before that phrase may be used without qualification:

- **Corpus:** 100% known false-positive suppression and 100% known true-positive retention across the current governed precision corpus, with zero fixture-level regressions; generalized semantic-recall regressions must also remain green.
- **Anchoring:** 100% of published findings are anchored to changed lines on the exact reviewed head; ambiguity or unanchored findings fail closed.
- **Verifier:** every ordinary model-generated published finding has concrete verifier evidence from the exact changed line plus full head-file context. Deterministic core-sentinel findings must independently re-match the exact head-file line.
- **Live precision:** across a rolling sample of at least 20 operator-dispositioned naturalistic findings, confirmed precision is at least 95%, with zero confirmed false-positive Critical/High findings. Suppressed candidates are not counted as published findings.
- **Repair safety:** across at least 10 live applyable-repair opportunities, 100% of rendered native suggestion blocks are exact-head validated, diff-range anchored, independently critic-accepted, and semantically safe under operator disposition, with zero detector-authored or speculative replacements rendered as applyable suggestions. The live sample must include at least one repair whose smallest correct fix spans more than one source line or more than one edit block before coordinated repair capability is treated as proven in production.
- **Coordinated completeness:** when a verified repair requires multiple edit blocks, the published repair set must be complete under operator disposition; DCOIR must not present a known partial subset as the full fix. Necessary off-diff edits may be guidance-only but must remain visibly linked to the same repair set.
- **Regression durability:** every confirmed false positive or missed high-signal true positive is captured as a permanent regression fixture before the corresponding hardening issue is closed.
- **No autonomy implication:** meeting this quality bar only establishes reviewer usefulness. Autonomous branch writes remain disabled until #293 is separately reviewed and the operator explicitly authorizes that capability.

## Current evidence boundary

The controlled `TEST ONLY — NEVER MERGE` PR #436 proves a live known true positive can survive final selection and render as GitHub's native suggested-change component without mutating the PR branch. That established the original GitHub-native rendering mechanism.

The separate controlled `TEST ONLY — NEVER MERGE` PR #437 proves the earlier strict ordinary semantic path end to end for a one-line repair. On unchanged probe head `f59f8da397276718b64cc9fa034b2a4228cc86da`, DCOIR Review run `33244004569` used deep full-file context with zero risk-sentinel anchors, published one ordinary model-judged finding at the exact changed line, passed it through the independent finding verifier, invoked a dedicated repair author, invoked a separate repair critic, passed deterministic exact-line validation, and rendered a native GitHub suggestion. The repair author proposed `return age_minutes >= 0 and age_minutes <= 60` at confidence 1.00; the served repair critic accepted that exact repair at confidence 0.97; and the final repair metric recorded one verified finding, one native suggestion, and zero fallback/declined suggestions. The PR branch remained unchanged.

Issue #456 adds two newer controlled evidence layers. Blind DCOIR run `33372955952` on unchanged PR #448 independently rediscovered the same rejected-proposition polarity defect previously identified by GitHub Copilot Balanced, demonstrating materially improved semantic recall without hard-coding the PR answer. The v36 active-chain regression then proves the current production synthesis wrapper can carry a synthetic verifier-supported finding through a two-line repair set, fixed independent frontier repair critic, exact-head validation, and ranged GitHub suggestion payload without network-dependent model calls. These are controlled quality data points; a live multi-line or multi-block v36 suggestion is still required by the repair-safety gate above before coordinated repair capability is treated as production-proven.

These controls do not by themselves satisfy the rolling naturalistic precision or repair-safety sample requirements. In particular, #293 remains blocked and autonomous branch writes remain unauthorized.
