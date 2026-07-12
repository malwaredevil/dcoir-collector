"""Final apply shim for the DCOIR Review v5 runtime patch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v5 as v5


def _call_bool(func: Any, default: bool, *args: Any) -> bool:
    if callable(func):
        return bool(func(*args))
    return default


def _call_dict(func: Any, *args: Any) -> dict[str, Any]:
    if callable(func):
        result = func(*args)
        return result if isinstance(result, dict) else {}
    return {}


def _sentinel_line(value: Any) -> int:
    try:
        return int(getattr(value, "line", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _dedupe_sentinels(sentinels: list[Any]) -> list[Any]:
    seen: set[tuple[str, int, str]] = set()
    result: list[Any] = []
    for sentinel in sentinels:
        key = (str(getattr(sentinel, "path", "") or ""), _sentinel_line(sentinel), v5._sentinel_kind(sentinel))
        if key in seen:
            continue
        seen.add(key)
        result.append(sentinel)
    return result


def _make_env_token_sentinels(hardened: Any, diff: str) -> list[Any]:
    iter_added = getattr(hardened, "iter_added_diff_lines", None)
    risk_sentinel_type = getattr(hardened, "RiskSentinel", None)
    if not callable(iter_added) or risk_sentinel_type is None:
        return []
    by_path: dict[str, list[Any]] = {}
    for changed_line in iter_added(diff):
        path = str(getattr(changed_line, "path", "") or "")
        text = str(getattr(changed_line, "text", "") or "")
        if callable(getattr(hardened, "is_comment_only_added_line", None)) and hardened.is_comment_only_added_line(path, text):
            continue
        by_path.setdefault(path, []).append(changed_line)

    sentinels: list[Any] = []
    for path, lines in by_path.items():
        suffix = Path(path.lower()).suffix
        if suffix == ".py":
            env_lines = [line for line in lines if v5.PY_ENV_RE.search(str(getattr(line, "text", "") or ""))]
            if not env_lines:
                continue
            for candidate in lines:
                candidate_text = str(getattr(candidate, "text", "") or "")
                if not v5.OUTBOUND_RE.search(candidate_text):
                    continue
                nearby_env = next((env for env in env_lines if 0 <= _sentinel_line(candidate) - _sentinel_line(env) <= 8), None)
                if nearby_env is None:
                    continue
                combined_text = f"{getattr(nearby_env, 'text', '')} {candidate_text}"
                sentinels.append(
                    risk_sentinel_type(
                        path=path,
                        line=_sentinel_line(candidate),
                        label="DCOIR Python environment token callback",
                        detail="environment token read from env and forwarded to request-controlled callback",
                        text=combined_text,
                    )
                )
                break
        elif suffix in {".ps1", ".psm1", ".psd1"}:
            env_lines = [line for line in lines if v5.PS_ENV_RE.search(str(getattr(line, "text", "") or ""))]
            if not env_lines:
                continue
            for candidate in lines:
                candidate_text = str(getattr(candidate, "text", "") or "")
                if not v5.OUTBOUND_RE.search(candidate_text):
                    continue
                nearby_env = next((env for env in env_lines if 0 <= _sentinel_line(candidate) - _sentinel_line(env) <= 4), None)
                if nearby_env is None:
                    continue
                combined_text = f"{getattr(nearby_env, 'text', '')} {candidate_text}"
                sentinels.append(
                    risk_sentinel_type(
                        path=path,
                        line=_sentinel_line(candidate),
                        label="DCOIR PowerShell environment token callback",
                        detail="environment token read from env and forwarded to request-controlled callback",
                        text=combined_text,
                    )
                )
                break
    return _dedupe_sentinels(sentinels)


def _select_required_first(hardened: Any, sentinels: list[Any], max_anchors: int | None) -> list[Any]:
    deduped = _dedupe_sentinels(sentinels)
    if max_anchors is None or len(deduped) <= max_anchors:
        return deduped
    selected: list[Any] = []
    seen: set[tuple[str, int, str]] = set()

    def add(sentinel: Any) -> None:
        key = (str(getattr(sentinel, "path", "") or ""), _sentinel_line(sentinel), v5._sentinel_kind(sentinel))
        if key not in seen and len(selected) < max_anchors:
            seen.add(key)
            selected.append(sentinel)

    for kind in v5.REQUIRED_KIND_ORDER:
        for sentinel in deduped:
            if v5._sentinel_kind(sentinel) == kind:
                add(sentinel)
                break
    for sentinel in deduped:
        add(sentinel)
    return selected


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    original_detect = getattr(module, "_dcoir_required_v5_original_detect_risk_sentinels", None)
    if original_detect is None:
        original_detect = getattr(module, "detect_risk_sentinels", getattr(hardened, "detect_risk_sentinels", None))
        module._dcoir_required_v5_original_detect_risk_sentinels = original_detect

    original_required = getattr(hardened, "_dcoir_required_v5_original_required_risk_sentinels", None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        hardened._dcoir_required_v5_original_required_risk_sentinels = original_required

    original_is_required = getattr(hardened, "_dcoir_required_v5_original_is_required_risk_sentinel", None)
    if original_is_required is None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)
        hardened._dcoir_required_v5_original_is_required_risk_sentinel = original_is_required

    original_covers = getattr(hardened, "_dcoir_required_v5_original_finding_covers_risk_sentinel", None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        hardened._dcoir_required_v5_original_finding_covers_risk_sentinel = original_covers

    original_fallback = getattr(hardened, "_dcoir_required_v5_original_risk_sentinel_fallback_finding", None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        hardened._dcoir_required_v5_original_risk_sentinel_fallback_finding = original_fallback

    original_rank = getattr(module, "_dcoir_required_v5_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_v5_original_rank_findings_for_required_budget = original_rank

    original_synthesize = getattr(module, "_dcoir_required_v5_original_synthesize_fix_for_finding", None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        module._dcoir_required_v5_original_synthesize_fix_for_finding = original_synthesize

    original_build = None
    if base is not None and callable(getattr(base, "build_inline_comment", None)):
        original_build = getattr(base, "_dcoir_required_v5_original_build_inline_comment", None)
        if original_build is None:
            original_build = base.build_inline_comment
            base._dcoir_required_v5_original_build_inline_comment = original_build

    if callable(original_detect):
        def required_v5_detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[Any]:
            try:
                existing = original_detect(diff, None)
            except TypeError:
                existing = original_detect(diff)
            return _select_required_first(hardened, [*existing, *_make_env_token_sentinels(hardened, diff)], max_anchors)

        module.detect_risk_sentinels = required_v5_detect_risk_sentinels
        hardened.detect_risk_sentinels = required_v5_detect_risk_sentinels
        hardened.select_risk_sentinels = lambda sentinels, max_anchors=None: _select_required_first(hardened, sentinels, max_anchors)

    hardened.required_risk_sentinels = lambda sentinels: v5._required_sentinels(original_required, sentinels)
    hardened.is_required_risk_sentinel = lambda sentinel: v5._sentinel_kind(sentinel) in v5.REQUIRED_KIND_TITLES or _call_bool(original_is_required, False, sentinel)
    hardened.finding_covers_risk_sentinel = lambda finding, sentinel: v5.finding_covers_sentinel(finding, sentinel, original_covers)
    hardened.risk_sentinel_fallback_finding = lambda sentinel, config: v5._fallback_finding(sentinel, config, original_fallback)
    hardened.add_risk_sentinel_fallback_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: v5.add_risk_sentinel_fallback_findings(hardened, original_rank, original_covers, original_fallback, findings, risk_sentinels, config, unanchored_findings)

    review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)

    def required_v5_enforce_risk_sentinel_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = hardened.add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        uncovered = [sentinel for sentinel in hardened.required_risk_sentinels(risk_sentinels) if not any(v5.finding_covers_sentinel(finding, sentinel, original_covers) for finding in findings)]
        if uncovered:
            digest = "; ".join(f"{getattr(sentinel, 'path', '')}:{getattr(sentinel, 'line', '')} {v5._sentinel_kind(sentinel)}" for sentinel in uncovered)
            raise review_quality_error(f"DCOIR Review quality failure: required changed-line signals remain uncovered after v5 refill: {digest}.")

    hardened.enforce_risk_sentinel_findings = required_v5_enforce_risk_sentinel_findings
    hardened.finding_merge_key = lambda finding: (str(finding.get("path", "") or ""), v5._finding_line(finding), v5._semantic_kind(finding) or "unknown")
    module.finding_dedupe_key = v5._dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: v5._dedupe_findings(hardened, findings)
    module.rank_findings_for_required_budget = lambda findings, config: v5._rank_findings(module, hardened, original_rank, findings, config)

    for name in ("findings_from_result", "extract_findings_from_result", "normalized_findings_from_result"):
        if hasattr(module, name):
            setattr(module, name, v5.findings_from_result)
    module.dcoir_required_v5_findings_from_result = v5.findings_from_result

    if callable(original_synthesize):
        module.synthesize_fix_for_finding = lambda index, finding, file_text, schema, config: v5._normalize_comment_finding(original_synthesize(index, finding, file_text, schema, config))

    if base is not None and callable(original_build):
        def required_v5_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            normalized = v5._normalize_comment_finding(finding)
            kind = v5._semantic_kind(normalized)
            if kind in v5.REQUIRED_KIND_TITLES:
                try:
                    if callable(getattr(base, "emit_status", None)):
                        base.emit_status("required-v5-deterministic-comment", f"{normalized.get('path')}:{normalized.get('line')} {kind}")
                except Exception:
                    pass
                return v5.final_rendered_scrub(v5.v4._render_deterministic_comment(normalized, model_used), normalized)
            return v5.final_rendered_scrub(original_build(normalized, model_used, config), normalized)

        base.build_inline_comment = required_v5_build_inline_comment
