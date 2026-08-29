"""DCOIR Review v22 summary-only semantic-problem recovery overlay.

The detector can sometimes describe a real bug in the review summary while
returning an empty structured findings array. The existing recovery classifier
already recognizes issue/problem/error language, but it did not recognize
bug/defect/vulnerability discovery wording. This overlay adds that vocabulary
without treating explicitly negated statements such as "no bugs were found"
as actionable problems.
"""

from __future__ import annotations

import re
from typing import Any


VERSION = "v22"
PROBLEM_NOUN_RE = re.compile(r"\b(?:bugs?|defects?|vulnerabilit(?:y|ies))\b", re.IGNORECASE)
DISCOVERY_VERB_RE = re.compile(r"\b(?:found|identified|detected|observed)\b", re.IGNORECASE)
NEGATION_RE = re.compile(r"\b(?:no|not|without)\b", re.IGNORECASE)


def _explicit_semantic_problem_discovery(summary: str) -> bool:
    text = re.sub(r"[^a-z0-9-]+", " ", str(summary or "").lower()).strip()
    if not text:
        return False
    for noun_match in PROBLEM_NOUN_RE.finditer(text):
        prefix = text[max(0, noun_match.start() - 140) : noun_match.start()].strip()
        # A nearby explicit negation owns the noun: "no bugs", "found no defects",
        # "not a vulnerability", etc. These must remain clean summaries.
        nearby = prefix.split()[-8:]
        if NEGATION_RE.search(" ".join(nearby)):
            continue
        verb_matches = list(DISCOVERY_VERB_RE.finditer(prefix))
        if not verb_matches:
            continue
        verb = verb_matches[-1]
        words_after_verb = prefix[verb.end() :].split()
        if len(words_after_verb) <= 7:
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
