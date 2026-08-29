"""DCOIR Review v22 summary-only semantic-problem recovery overlay.

The detector can sometimes describe a real bug in the review summary while
returning an empty structured findings array. The existing recovery classifier
already recognizes issue/problem/error language, but it did not recognize
bug/defect/vulnerability discovery wording. This overlay adds that vocabulary
without treating explicitly negated statements as actionable problems.
"""

from __future__ import annotations

import re
from typing import Any


VERSION = "v22"
PROBLEM_NOUN = r"(?:bugs?|defects?|vulnerabilit(?:y|ies))"
DISCOVERY_VERB = r"(?:found|identified|detected|observed)"

ACTIVE_DISCOVERY_RE = re.compile(
    rf"\b{DISCOVERY_VERB}\b(?:\s+[a-z0-9_-]+){{0,7}}\s+\b{PROBLEM_NOUN}\b",
    re.IGNORECASE,
)
PASSIVE_DISCOVERY_RE = re.compile(
    rf"\b{PROBLEM_NOUN}\b(?:\s+[a-z0-9_-]+){{0,4}}\s+(?:(?:was|were|is|are)\s+)?\b{DISCOVERY_VERB}\b",
    re.IGNORECASE,
)
DIRECT_NEGATION_PATTERNS = (
    re.compile(rf"\bno\b(?:\s+[a-z0-9_-]+){{0,4}}\s+\b{PROBLEM_NOUN}\b", re.IGNORECASE),
    re.compile(rf"\b(?:not|without)\b(?:\s+(?:a|an|any|the))?(?:\s+[a-z0-9_-]+){{0,3}}\s+\b{PROBLEM_NOUN}\b", re.IGNORECASE),
    re.compile(rf"\b{DISCOVERY_VERB}\b\s+no\b(?:\s+[a-z0-9_-]+){{0,4}}\s+\b{PROBLEM_NOUN}\b", re.IGNORECASE),
    re.compile(
        rf"\b{PROBLEM_NOUN}\b(?:\s+[a-z0-9_-]+){{0,3}}\s+(?:(?:was|were|is|are)\s+)?not\s+\b{DISCOVERY_VERB}\b",
        re.IGNORECASE,
    ),
)


def _semantic_clauses(summary: str) -> list[str]:
    text = str(summary or "").lower()
    # Keep conjunctions inside a clause because they frequently belong to the
    # evidence statement; punctuation gives a safer boundary for negation.
    return [re.sub(r"[^a-z0-9_-]+", " ", part).strip() for part in re.split(r"[.;:!?\n]+", text) if part.strip()]


def _explicit_semantic_problem_discovery(summary: str) -> bool:
    for clause in _semantic_clauses(summary):
        if not clause:
            continue
        scrubbed = clause
        for pattern in DIRECT_NEGATION_PATTERNS:
            scrubbed = pattern.sub(" ", scrubbed)
        if ACTIVE_DISCOVERY_RE.search(scrubbed) or PASSIVE_DISCOVERY_RE.search(scrubbed):
            return True
    return False


def apply_pareto_context_module(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return
    storage = "_dcoir_required_v22_original_summary_suggests_problem"
    original = getattr(hardened, storage, None)
    if original is None:
        original = getattr(hardened, "summary_suggests_problem", None)
        if callable(original):
            setattr(hardened, storage, original)
    if not callable(original):
        return

    def summary_suggests_problem(summary: str) -> bool:
        return bool(original(summary) or _explicit_semantic_problem_discovery(summary))

    hardened.summary_suggests_problem = summary_suggests_problem
