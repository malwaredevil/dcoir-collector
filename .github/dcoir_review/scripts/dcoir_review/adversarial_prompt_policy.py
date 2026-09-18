"""Canonical adversarial semantic prompt policy for DCOIR Review."""

from __future__ import annotations

BASE_ADVERSARIAL_SEMANTIC_BLOCK = """
Adversarial semantic falsification requirements:
- For every changed validator, scorer, parser, normalizer, router, policy gate, selector, or acceptance helper, state the intended accept/reject invariant from the supplied code, tests, PR description, and repository guidance, then actively try to falsify it.
- Construct minimal counterexamples that should be rejected but might pass, and valid examples that should pass but might be rejected. Report only counterexamples you can validate against the supplied implementation.
- Probe semantic scope binding: a required token/action in the wrong clause, lane, object, branch, phase, or namespace must not satisfy the intended requirement.
- Probe assertion polarity and discourse: negation, rejection of a quoted/mentioned claim, postposed prohibition/unavailability, disclaimers, and statements such as 'wrong to say X' must not be mistaken for affirmative evidence of X.
- Probe representation variants when matching text or structure: numbered/inline headings, punctuation, normalization, snake_case versus spaced keys, serialization/JSON forms, quoting, repeated blocks, and duplicate procedures.
- Probe helper consistency: if one path uses stronger negation/scope/rejection handling than a sibling path for the same semantic concept, attempt the weaker-path bypass.
- Treat passing tests as evidence, not proof. Inspect whether the negative controls actually isolate the changed invariant and whether an untested neighboring variant can bypass it.
- Prefer a concrete reproducible counterexample over a general warning. If no counterexample or other actionable defect survives inspection, return a clean result.
""".strip()

PREDICATE_AUDIT_BLOCK = """
Predicate and call-site audit requirements:
- For each changed boolean acceptance/rejection helper, enumerate every positive-evidence branch or disjunct before deciding the helper is sound. Audit the actual call-site arguments and omitted defaults, not only the helper definition.
- When a contextual matcher exposes polarity, quotation, rejection, scope, or boundary options, compare those options across sibling call sites. An omitted option is executable behavior and must be tested as deliberately as an explicitly enabled option.
- For every changed positive textual signal, test four semantic placements when applicable: direct affirmative use, direct negation, quotation/mention-only use, and a rejected proposition such as saying that the signal would be wrong/false/misleading. A phrase that is itself worded as a prohibition is not automatically affirmative evidence when the whole proposition containing it is rejected or merely mentioned.
- Audit each OR branch independently. A strong polarity check on one positive-evidence path does not protect a sibling path that calls the same matcher with weaker/default filtering.
- Prefer root-cause defects in executable changed code over speculative fixture/loader concerns. For fixture-only findings, report only when the supplied consuming implementation or test wiring demonstrates the mis-score or evidence loss; do not hypothesize unseen loader behavior.
- Keep the finding set Pareto-small: when several counterexamples share one root cause, report the root cause once with the strongest minimal counterexample instead of emitting neighboring variants as separate findings.
""".strip()

ADVERSARIAL_SEMANTIC_BLOCK = f"{BASE_ADVERSARIAL_SEMANTIC_BLOCK}\n\n{PREDICATE_AUDIT_BLOCK}".strip()

INDEPENDENT_CONFIRMATION_INTRO = """

Independent adversarial confirmation pass:
The preceding detector pass is untrusted evidence, not a conclusion. Review the supplied PR independently and try to disprove its changed correctness/validation contracts before accepting a clean result. In particular, apply the adversarial semantic falsification requirements below. Do not merely restate tests or the PR description, and do not assume an existing detector would have caught the defect.
""".strip()

INDEPENDENT_CONFIRMATION_BLOCK = f"{INDEPENDENT_CONFIRMATION_INTRO}\n\n{ADVERSARIAL_SEMANTIC_BLOCK}".strip()

ADVERSARIAL_PROMPT_TRUNCATED_MARKER = "\n\n[adversarial semantic prompt truncated by reviewer]"

def append_adversarial_semantic_block(prompt: str, max_chars: int) -> str:
    """Append the canonical semantic policy using the historical bounded contract."""
    combined = f"{str(prompt)}\n\n{ADVERSARIAL_SEMANTIC_BLOCK}"
    maximum = max(0, int(max_chars))
    if len(combined) <= maximum:
        return combined
    if maximum <= len(ADVERSARIAL_PROMPT_TRUNCATED_MARKER):
        return ADVERSARIAL_PROMPT_TRUNCATED_MARKER[:maximum]
    keep = maximum - len(ADVERSARIAL_PROMPT_TRUNCATED_MARKER)
    return combined[:keep] + ADVERSARIAL_PROMPT_TRUNCATED_MARKER

__all__ = [
    "BASE_ADVERSARIAL_SEMANTIC_BLOCK",
    "PREDICATE_AUDIT_BLOCK",
    "ADVERSARIAL_SEMANTIC_BLOCK",
    "INDEPENDENT_CONFIRMATION_INTRO",
    "INDEPENDENT_CONFIRMATION_BLOCK",
    "ADVERSARIAL_PROMPT_TRUNCATED_MARKER",
    "append_adversarial_semantic_block",
]
