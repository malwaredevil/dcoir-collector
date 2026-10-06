"""Stable hard-required coverage policy for DCOIR Review.

This owner preserves the remaining production semantics historically installed by
runtime patch v2: deterministic PowerShell ACL sentinels, hard-required sentinel
classification/coverage, required fallback rendering, semantic merge/dedupe keys,
and post-synthesis finding normalization. Historical v2 remains importable as a
helper-definition layer for older compatibility modules, but it is no longer a
production runtime root.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v2 as v2


APPLIED_MARKER = "_dcoir_review_required_coverage_policy_applied"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    detect_storage = "_dcoir_required_coverage_policy_original_detect_risk_sentinels"
    original_detect = getattr(module, detect_storage, None)
    if original_detect is None:
        original_detect = getattr(
            module,
            "detect_risk_sentinels",
            getattr(hardened, "detect_risk_sentinels", None),
        )
        if callable(original_detect):
            setattr(module, detect_storage, original_detect)
    if callable(original_detect):
        def detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[Any]:
            try:
                existing = list(original_detect(diff, None))
            except TypeError:
                existing = list(original_detect(diff))
            ps_acl = v2._make_ps_acl_sentinels(hardened, diff)
            return v2._select_sentinels(hardened, [*existing, *ps_acl], max_anchors)

        module.detect_risk_sentinels = detect_risk_sentinels
        hardened.detect_risk_sentinels = detect_risk_sentinels

    required_storage = "_dcoir_required_coverage_policy_original_required_risk_sentinels"
    original_required = getattr(hardened, required_storage, None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        if callable(original_required):
            setattr(hardened, required_storage, original_required)
    hardened.required_risk_sentinels = lambda sentinels: v2._required_sentinels(original_required, sentinels)

    is_required_storage = "_dcoir_required_coverage_policy_original_is_required_risk_sentinel"
    original_is_required = getattr(hardened, is_required_storage, None)
    if original_is_required is None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)
        if callable(original_is_required):
            setattr(hardened, is_required_storage, original_is_required)

    def is_required_risk_sentinel(sentinel: Any) -> bool:
        if v2._sentinel_kind(sentinel) in v2.HARD_REQUIRED_KIND_TITLES:
            return True
        return bool(original_is_required(sentinel)) if callable(original_is_required) else False

    hardened.is_required_risk_sentinel = is_required_risk_sentinel

    covers_storage = "_dcoir_required_coverage_policy_original_finding_covers_risk_sentinel"
    original_covers = getattr(hardened, covers_storage, None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        if callable(original_covers):
            setattr(hardened, covers_storage, original_covers)

    def finding_covers_risk_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
        if v2._sentinel_kind(sentinel) in v2.HARD_REQUIRED_KIND_TITLES:
            return v2._finding_covers_sentinel(finding, sentinel)
        return bool(original_covers(finding, sentinel)) if callable(original_covers) else False

    hardened.finding_covers_risk_sentinel = finding_covers_risk_sentinel

    fallback_storage = "_dcoir_required_coverage_policy_original_risk_sentinel_fallback_finding"
    original_fallback = getattr(hardened, fallback_storage, None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        if callable(original_fallback):
            setattr(hardened, fallback_storage, original_fallback)
    hardened.risk_sentinel_fallback_finding = lambda sentinel, config: v2._risk_sentinel_fallback_finding(
        hardened,
        original_fallback,
        sentinel,
        config,
    )

    merge_storage = "_dcoir_required_coverage_policy_original_finding_merge_key"
    original_merge_key = getattr(hardened, merge_storage, None)
    if original_merge_key is None:
        original_merge_key = getattr(hardened, "finding_merge_key", None)
        if callable(original_merge_key):
            setattr(hardened, merge_storage, original_merge_key)

    def finding_merge_key(finding: dict[str, Any]) -> tuple[str, int, str]:
        kind = v2._semantic_kind(finding)
        if kind:
            line = 0 if kind in {"python_ssrf", v2.PS_ACL_KIND} else v2._finding_line(finding)
            return str(finding.get("path", "") or ""), line, kind
        if callable(original_merge_key):
            return original_merge_key(finding)
        return str(finding.get("path", "") or ""), v2._finding_line(finding), "unknown"

    hardened.finding_merge_key = finding_merge_key
    module.finding_dedupe_key = v2._dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: v2._dedupe_findings(hardened, findings)

    synth_storage = "_dcoir_required_coverage_policy_original_synthesize_fix_for_finding"
    original_synthesize = getattr(module, synth_storage, None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        if callable(original_synthesize):
            setattr(module, synth_storage, original_synthesize)
    if callable(original_synthesize):
        def synthesize_fix_for_finding(
            index: int,
            finding: dict[str, Any],
            file_text: str,
            schema: dict[str, Any],
            config: Any,
        ) -> dict[str, Any]:
            enriched = original_synthesize(index, finding, file_text, schema, config)
            return v2._normalize_comment_finding(enriched)

        module.synthesize_fix_for_finding = synthesize_fix_for_finding

    setattr(module, APPLIED_MARKER, True)
