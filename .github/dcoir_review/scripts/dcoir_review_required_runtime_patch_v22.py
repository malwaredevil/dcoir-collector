"""DCOIR Review v22 summary-only semantic-problem recovery overlay.

The detector can sometimes describe a real problem in the review summary while
returning an empty structured findings array. The existing recovery classifier
already recognizes issue/problem/error language, but it did not recognize
bug/defect/vulnerability wording or typed finding phrases such as
"correctness finding". This overlay adds that vocabulary without treating
explicitly negated or zero-count statements as actionable problems.

Several historical compatibility layers can replace lower-level quality
helpers. v22 therefore also wraps the production hybrid first-pass boundary:
a semantic summary-only result that has not already retried receives the same
bounded whole-PR quality-retry flow before normalization/publication.
"""

from __future__ import annotations

import re
from typing import Any


VERSION = "v22"
TYPED_FINDING = r"(?:(?:correctness|logic|semantic|security|functional|behavioral)\s+findings?)"
PROBLEM_NOUN = rf"(?:bugs?|defects?|vulnerabilit(?:y|ies)|{TYPED_FINDING})"
DISCOVERY_VERB = r"(?:found|identified|detected|observed)"
ZERO_OR_NEGATIVE_COUNT = r"(?:no|zero|0)"
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
    re.compile(rf"\b{ZERO_OR_NEGATIVE_COUNT}\b(?:\s+[a-z0-9_-]+){{0,4}}\s+\b{PROBLEM_NOUN}\b", re.IGNORECASE),
    re.compile(rf"\b(?:not|without)\b(?:\s+(?:a|an|any|the))?(?:\s+[a-z0-9_-]+){{0,3}}\s+\b{PROBLEM_NOUN}\b", re.IGNORECASE),
    re.compile(rf"\b{DISCOVERY_VERB}\b\s+{ZERO_OR_NEGATIVE_COUNT}\b(?:\s+[a-z0-9_-]+){{0,4}}\s+\b{PROBLEM_NOUN}\b", re.IGNORECASE),
    re.compile(
        rf"\b{PROBLEM_NOUN}\b(?:\s+[a-z0-9_-]+){{0,3}}\s+(?:(?:was|were|is|are)\s+)?not\s+\b{DISCOVERY_VERB}\b",
        re.IGNORECASE,
    ),
)
NEUTRAL_META_FINDING_REFERENCE_PATTERNS = (
    re.compile(
        r"\b(?:mentions?|references?|documents?|describes?|includes?|uses?)\b"
        r"(?:\s+(?:a|an|the|this|that|its))?(?:\s+[a-z0-9_-]+){0,3}"
        r"\s+findings?\s+(?:schema|array|format|contract|field|key|object|payload|response)\b",
        re.IGNORECASE,
    ),
)


def _semantic_clauses(summary: str) -> list[str]:
    text = str(summary or "").lower()
    return [re.sub(r"[^a-z0-9_-]+", " ", part).strip() for part in re.split(r"[.;:!?\n]+", text) if part.strip()]


def _scrub_explicit_semantic_negations(summary: str) -> str:
    """Remove explicit negative/zero and neutral schema-only finding phrases.

    The lower-level classifier predates typed-finding/zero-count semantics and
    can otherwise turn ``Found 0 correctness findings`` back into a positive
    signal simply because the word ``finding`` remains. It can likewise treat
    neutral metadata prose such as ``mentions a finding schema`` as substantive
    review output. Scrubbing only those bounded phrases before delegating keeps
    the older issue/problem/error vocabulary while honoring v22's precision
    contract.
    """

    scrubbed_clauses: list[str] = []
    for clause in _semantic_clauses(summary):
        scrubbed = clause
        for pattern in DIRECT_NEGATION_PATTERNS:
            scrubbed = pattern.sub(" ", scrubbed)
        for pattern in NEUTRAL_META_FINDING_REFERENCE_PATTERNS:
            scrubbed = pattern.sub(" ", scrubbed)
        scrubbed = re.sub(r"\s+", " ", scrubbed).strip()
        if scrubbed:
            scrubbed_clauses.append(scrubbed)
    return ". ".join(scrubbed_clauses)


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


def _structured_findings(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    findings = result.get("findings", [])
    if not isinstance(findings, list):
        return []
    return [item for item in findings if isinstance(item, dict)]


def _has_no_structured_findings(result: Any) -> bool:
    return not _structured_findings(result)


def _structured_finding_digest(result: Any) -> str:
    findings = _structured_findings(result)
    anchors: list[str] = []
    for finding in findings[:3]:
        path = str(finding.get("path", "") or "").strip() or "<missing-path>"
        try:
            line = int(finding.get("line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        try:
            confidence = float(finding.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        anchors.append(f"{path}:{line}@{confidence:.2f}")
    return ", ".join(anchors) if anchors else "none"


def semantic_recovery_reason(result: Any, config: Any) -> str:
    if not isinstance(result, dict) or result.get("_quality_retry_attempted"):
        return ""
    if not getattr(config, "review_quality_retry_on_rejected_output", True):
        return ""
    if not getattr(config, "fail_on_summary_only_problem", True):
        return ""
    if not _has_no_structured_findings(result):
        return ""
    summary = str(result.get("summary", "") or "")
    return SEMANTIC_RETRY_REASON if _explicit_semantic_problem_discovery(summary) else ""


def _patch_hardened_helpers(hardened: Any) -> None:
    summary_storage = "_dcoir_required_v22_original_summary_suggests_problem"
    original_summary = getattr(hardened, summary_storage, None)
    if original_summary is None:
        original_summary = getattr(hardened, "summary_suggests_problem", None)
        if callable(original_summary):
            setattr(hardened, summary_storage, original_summary)
    if callable(original_summary):
        def summary_suggests_problem(summary: str) -> bool:
            if _explicit_semantic_problem_discovery(summary):
                return True
            return bool(original_summary(_scrub_explicit_semantic_negations(summary)))

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
        return semantic_recovery_reason(result, config)

    hardened.review_quality_retry_reason = review_quality_retry_reason


def _patch_hybrid_boundary(module: Any, hardened: Any) -> None:
    storage = "_dcoir_required_v22_original_hybrid_first_pass"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        return

    def openrouter_review_with_hybrid_first_pass(
        pr: dict[str, Any],
        files: list[dict[str, Any]],
        diff: str,
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
        risk_sentinels: list[Any],
        line_index: dict[tuple[str, int], int],
        deep_context_block: str,
        review_mode: str,
        context_summary: str,
        gh: Any,
    ) -> tuple[dict[str, Any], str, str]:
        result, model_used, service_tier = original(
            pr,
            files,
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
        )
        summary = str(result.get("summary", "") or "") if isinstance(result, dict) else ""
        semantic_signal = _explicit_semantic_problem_discovery(summary)
        diagnostic = (
            f"v22 active; structured_findings={len(_structured_findings(result))}; "
            f"semantic_signal={str(semantic_signal).lower()}; "
            f"retry_attempted={str(bool(isinstance(result, dict) and result.get('_quality_retry_attempted'))).lower()}; "
            f"anchors={_structured_finding_digest(result)}"
        )
        reporter.update("semantic-recovery", hardened.sanitize_github_output(diagnostic, config))

        retry_reason = semantic_recovery_reason(result, config)
        if not retry_reason:
            return result, model_used, service_tier

        safe_reason = hardened.sanitize_github_output(retry_reason, config)
        reporter.update("quality-retry", f"{safe_reason}; retrying with whole-PR repair prompt")
        aggregate_prompt = module.build_prompt(
            pr,
            files,
            diff,
            config,
            risk_sentinels,
            deep_context_block,
            review_mode,
            context_summary,
        )
        retry_sentinels = hardened.required_risk_sentinels(risk_sentinels) or risk_sentinels
        retry_prompt = hardened.build_quality_retry_prompt(
            aggregate_prompt,
            result,
            retry_sentinels,
            config,
            retry_reason,
        )
        hardened.write_debug_text_artifact_safely(config, "prompts/02-v22-semantic-quality-retry-prompt.txt", retry_prompt)
        retry_result, retry_model_used, retry_service_tier = hardened.openrouter_review(
            retry_prompt,
            schema,
            config,
            reporter,
        )
        hardened.write_debug_json_artifact_safely(
            config,
            "responses/02-v22-semantic-quality-retry-result.json",
            {"model_used": retry_model_used, "service_tier": retry_service_tier, "result": retry_result},
        )
        initial_summary = str(result.get("summary", "") or "").strip()
        retry_summary = str(retry_result.get("summary", "") or "").strip()
        merged_result = hardened.merge_review_results(result, retry_result)
        merged_result["_quality_retry_attempted"] = True
        merged_result["_quality_retry_reason"] = retry_reason
        merged_result["_quality_retry_initial_summary"] = initial_summary
        merged_result["_quality_retry_retry_summary"] = retry_summary
        hardened.write_debug_json_artifact_safely(
            config,
            "responses/03-v22-semantic-quality-retry-merged-result.json",
            {"model_used": retry_model_used, "service_tier": retry_service_tier, "result": merged_result},
        )
        return merged_result, retry_model_used, retry_service_tier

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def apply_pareto_context_module(module: Any) -> None:
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return
    _patch_hardened_helpers(hardened)
    _patch_hybrid_boundary(module, hardened)
