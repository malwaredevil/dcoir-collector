"""DCOIR Review v22 summary-only semantic-problem recovery overlay.

The detector can sometimes describe a real bug in the review summary while
returning an empty structured findings array. The existing recovery classifier
already recognizes issue/problem/error language, but it did not recognize
bug/defect/vulnerability discovery wording. This overlay adds that vocabulary
without treating explicitly negated statements as actionable problems.

The production per-file path calls ``hardened.review_quality_retry_reason``
directly, so v22 wraps that callable as the authoritative recovery seam instead
of depending on an older function's module-global symbol lookup.
"""

from __future__ import annotations

import re
from typing import Any


VERSION = "v22"
PROBLEM_NOUN = r"(?:bugs?|defects?|vulnerabilit(?:y|ies))"
DISCOVERY_VERB = r"(?:found|identified|detected|observed)"
SEMANTIC_RETRY_REASON = "model summary indicated a possible issue while the structured findings array was empty"

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


def _has_no_structured_findings(result: Any) -> bool:
    if not isinstance(result, dict):
        return True
    findings = result.get("findings", [])
    return not isinstance(findings, list) or not findings


def apply_pareto_context_module(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    summary_storage = "_dcoir_required_v22_original_summary_suggests_problem"
    original_summary = getattr(hardened, summary_storage, None)
    if original_summary is None:
        original_summary = getattr(hardened, "summary_suggests_problem", None)
        if callable(original_summary):
            setattr(hardened, summary_storage, original_summary)
    if callable(original_summary):
        def summary_suggests_problem(summary: str) -> bool:
            return bool(original_summary(summary) or _explicit_semantic_problem_discovery(summary))

        hardened.summary_suggests_problem = summary_suggests_problem

    retry_storage = "_dcoir_required_v22_original_review_quality_retry_reason"
    original_retry = getattr(hardened, retry_storage, None)
    if original_retry is None:
        original_retry = getattr(hardened, "review_quality_retry_reason", None)
        if callable(original_retry):
            setattr(hardened, retry_storage, original_retry)
    if not callable(original_retry):
        return

    def review_quality_retry_reason(
        result: dict[str, Any],
        config: Any,
        risk_sentinels: list[Any],
        line_index: dict[tuple[str, int], int] | None = None,
    ) -> str:
        existing_reason = str(original_retry(result, config, risk_sentinels, line_index) or "")
        if existing_reason:
            return existing_reason
        if not getattr(config, "review_quality_retry_on_rejected_output", True):
            return ""
        if not getattr(config, "fail_on_summary_only_problem", True):
            return ""
        if not _has_no_structured_findings(result):
            return ""
        summary = str(result.get("summary", "") or "") if isinstance(result, dict) else ""
        return SEMANTIC_RETRY_REASON if _explicit_semantic_problem_discovery(summary) else ""

    hardened.review_quality_retry_reason = review_quality_retry_reason
