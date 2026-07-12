"""Final apply shim for the DCOIR Review v4 runtime patch.

The v4 definitions live in ``dcoir_review_required_runtime_patch_v4``. This shim
applies those definitions after every earlier runtime layer while preserving the
previous hooks before replacing them.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4


def _call_bool(func: Any, default: bool, *args: Any) -> bool:
    if callable(func):
        return bool(func(*args))
    return default


def _call_dict(func: Any, *args: Any) -> dict[str, Any]:
    if callable(func):
        result = func(*args)
        return result if isinstance(result, dict) else {}
    return {}


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    original_required = getattr(hardened, "_dcoir_required_v4_apply_original_required_risk_sentinels", None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        hardened._dcoir_required_v4_apply_original_required_risk_sentinels = original_required

    original_is_required = getattr(hardened, "_dcoir_required_v4_apply_original_is_required_risk_sentinel", None)
    if original_is_required is None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)
        hardened._dcoir_required_v4_apply_original_is_required_risk_sentinel = original_is_required

    original_covers = getattr(hardened, "_dcoir_required_v4_apply_original_finding_covers_risk_sentinel", None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        hardened._dcoir_required_v4_apply_original_finding_covers_risk_sentinel = original_covers

    original_fallback = getattr(hardened, "_dcoir_required_v4_apply_original_risk_sentinel_fallback_finding", None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        hardened._dcoir_required_v4_apply_original_risk_sentinel_fallback_finding = original_fallback

    original_rank = getattr(module, "_dcoir_required_v4_apply_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_v4_apply_original_rank_findings_for_required_budget = original_rank

    original_synthesize = getattr(module, "_dcoir_required_v4_apply_original_synthesize_fix_for_finding", None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        module._dcoir_required_v4_apply_original_synthesize_fix_for_finding = original_synthesize

    original_build = None
    if base is not None and callable(getattr(base, "build_inline_comment", None)):
        original_build = getattr(base, "_dcoir_required_v4_apply_original_build_inline_comment", None)
        if original_build is None:
            original_build = base.build_inline_comment
            base._dcoir_required_v4_apply_original_build_inline_comment = original_build

    hardened.required_risk_sentinels = lambda sentinels: v4._required_sentinels(original_required, sentinels)

    def required_v4_is_required_risk_sentinel(sentinel: Any) -> bool:
        return v4._sentinel_kind(sentinel) in v4.HARD_REQUIRED_KIND_TITLES or _call_bool(original_is_required, False, sentinel)

    hardened.is_required_risk_sentinel = required_v4_is_required_risk_sentinel

    def required_v4_finding_covers_risk_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
        if v4._sentinel_kind(sentinel) in v4.HARD_REQUIRED_KIND_TITLES:
            return v4._finding_covers_sentinel(finding, sentinel)
        return _call_bool(original_covers, False, finding, sentinel)

    hardened.finding_covers_risk_sentinel = required_v4_finding_covers_risk_sentinel

    def required_v4_risk_sentinel_fallback_finding(sentinel: Any, config: Any) -> dict[str, Any]:
        return v4._fallback_finding(sentinel, config) or _call_dict(original_fallback, sentinel, config)

    hardened.risk_sentinel_fallback_finding = required_v4_risk_sentinel_fallback_finding
    hardened.add_risk_sentinel_fallback_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: v4._add_risk_sentinel_fallback_findings(hardened, original_rank, findings, risk_sentinels, config, unanchored_findings)

    review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)

    def required_v4_enforce_risk_sentinel_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = hardened.add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        uncovered = [sentinel for sentinel in hardened.required_risk_sentinels(risk_sentinels) if not any(v4._finding_covers_sentinel(finding, sentinel) for finding in findings)]
        if uncovered:
            digest = "; ".join(f"{getattr(sentinel, 'path', '')}:{getattr(sentinel, 'line', '')} {v4._sentinel_kind(sentinel)}" for sentinel in uncovered)
            raise review_quality_error(f"DCOIR Review quality failure: required changed-line signals remain uncovered after v4 refill: {digest}.")

    hardened.enforce_risk_sentinel_findings = required_v4_enforce_risk_sentinel_findings
    hardened.finding_merge_key = lambda finding: (str(finding.get("path", "") or ""), v4._finding_line(finding), v4._semantic_kind(finding) or "unknown")
    module.finding_dedupe_key = v4._dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: v4._dedupe_findings(hardened, findings)
    module.rank_findings_for_required_budget = lambda findings, config: v4._rank_findings(module, hardened, original_rank, findings, config)

    if callable(original_synthesize):
        module.synthesize_fix_for_finding = lambda index, finding, file_text, schema, config: v4._normalize_comment_finding(original_synthesize(index, finding, file_text, schema, config))

    if base is not None and callable(original_build):
        def required_v4_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            normalized = v4._normalize_comment_finding(finding)
            kind = v4._semantic_kind(normalized)
            if kind in v4.HARD_REQUIRED_KIND_TITLES or kind == v4.YAML_METADATA_SHELL or v4._is_env_token_callback(normalized):
                try:
                    if callable(getattr(base, "emit_status", None)):
                        base.emit_status("required-v4-deterministic-comment", f"{normalized.get('path')}:{normalized.get('line')} {kind}")
                except Exception:
                    pass
                return v4._render_deterministic_comment(normalized, model_used)
            return v4._final_rendered_scrub(original_build(normalized, model_used, config), normalized)

        base.build_inline_comment = required_v4_build_inline_comment
