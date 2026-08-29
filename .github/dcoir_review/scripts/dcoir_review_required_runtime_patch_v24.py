"""DCOIR Review v24 verifier-aware ordinary-finding renderer.

Legacy required-coverage renderers intentionally canonicalize sentinel-backed
findings to deterministic security templates. That is correct for deterministic
sentinels, but it can corrupt an independently verified ordinary semantic
finding by inferring a sentinel kind from rendered prose.

v24 keeps the existing renderer for deterministic/sentinel findings. For a v21
``model-judge`` finding with no explicit sentinel provenance, it renders the
verified detector title/body plus independently synthesized repair guidance
through the same GitHub-safe base helpers. Native suggestions still require the
v20 independent-synthesis marker.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v20 as v20
import dcoir_review_required_runtime_patch_v21 as v21


VERSION = "v24"


def _is_verified_ordinary_finding(finding: Any) -> bool:
    if not isinstance(finding, dict):
        return False
    verifier = finding.get(v21.VERIFIER_MARKER)
    if not isinstance(verifier, dict) or verifier.get("mode") != "model-judge" or verifier.get("supported") is not True:
        return False
    if str(finding.get("_risk_sentinel_kind", "") or "").strip():
        return False
    raw_key = finding.get("_risk_sentinel_key")
    if isinstance(raw_key, (list, tuple)) and len(raw_key) == 3 and str(raw_key[2] or "").strip():
        return False
    return True


def _render_verified_ordinary(base: Any, finding: dict[str, Any], config: Any) -> str:
    title = base.markdown_emphasis_safe_text(
        base.sanitize_github_output(str(finding.get("title", "Finding") or "Finding").strip(), config)
    )
    severity = base.markdown_emphasis_safe_text(str(finding.get("severity", "medium") or "medium").upper())
    try:
        confidence = float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    body = base.strip_model_validation_section(
        base.sanitize_github_output(str(finding.get("body", "") or "").strip(), config)
    )
    validation = base.sanitize_github_output(base.validation_text_for_finding(finding), config)
    fix_guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    path = str(finding.get("path", "") or "")
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    language = base.language_for_fix_guidance(fix_guidance, finding) if fix_guidance else base.language_hint_for_path(path)

    parts = [f"**{severity}: {title}**", "", body]
    if getattr(config, "include_confidence", False):
        parts.extend(["", f"Confidence: `{confidence:.2f}`"])

    suggestion = v20._safe_single_line_suggestion(base, finding)
    if suggestion:
        safe_suggestion = base.sanitize_github_output(suggestion, config, neutralize_mentions=False)
        parts.extend(["", "Suggested fix:", "", "```suggestion", safe_suggestion, "```"])

    if fix_guidance:
        for label, key in (("Remove", "remove"), ("Replace", "replace"), ("Add", "add")):
            value = base.fix_guidance_value_text(fix_guidance.get(key, ""), config, neutralize_mentions=False)
            if value:
                base.append_guidance_value(parts, label, key, value, line, language)
        notes = base.fix_guidance_value_text(fix_guidance.get("notes", ""), config)
        if notes:
            parts.extend(["", "**Notes:**", "", notes])

    if validation:
        parts.extend(["", "**Validation expected after fix:**"])
        base.append_language_fence(parts, "bash", validation)
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME}</sub>"])
    return base.github_safe_body("\n".join(parts), limit=12000)


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    if base is None:
        return
    storage = "_dcoir_required_v24_original_build_inline_comment"
    original = getattr(base, storage, None)
    if original is None:
        original = getattr(base, "build_inline_comment", None)
        if callable(original):
            setattr(base, storage, original)
    if not callable(original):
        return

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        if _is_verified_ordinary_finding(finding):
            return _render_verified_ordinary(base, finding, config)
        return original(finding, model_used, config)

    base.build_inline_comment = build_inline_comment
