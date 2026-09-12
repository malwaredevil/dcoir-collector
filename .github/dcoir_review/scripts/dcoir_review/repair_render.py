"""Stable rendering for verified DCOIR repair findings."""

from __future__ import annotations

from typing import Any

from dcoir_review import repair_pipeline as repair


# Preserve the historical display/provenance fallback while the numbered patch is retired.
DEFAULT_PIPELINE_VERSION = "v28"


def render_repair(module: Any, finding: dict[str, Any], config: Any) -> str:
    base = module.base
    marker = finding.get(repair.REPAIR_MARKER) if isinstance(finding.get(repair.REPAIR_MARKER), dict) else {}
    title = base.markdown_emphasis_safe_text(
        base.sanitize_github_output(str(finding.get("title", "Finding") or "Finding").strip(), config)
    )
    severity = base.markdown_emphasis_safe_text(str(finding.get("severity", "medium") or "medium").upper())
    body = base.strip_model_validation_section(
        base.sanitize_github_output(str(finding.get("body", "") or "").strip(), config)
    )
    parts = [f"**{severity}: {title}**", "", body]

    suggestion = str(finding.get("suggested_replacement", "") or "")
    if marker.get("outcome") == "native-suggestion" and suggestion:
        path, line = repair._path_line(finding)
        if (
            path
            and line > 0
            and not any(token in suggestion for token in ("\n", "\r", "```", "~~~"))
            and len(suggestion) <= 1000
            and base.is_safe_suggestion(suggestion)
        ):
            safe = base.sanitize_github_output(suggestion, config, neutralize_mentions=False)
            parts.extend(["", "**Suggested change:**", "", "```suggestion", safe, "```"])

    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    notes = base.fix_guidance_value_text(guidance.get("notes", ""), config) if guidance else ""
    if notes:
        parts.extend(["", "**Repair status:**", "", notes])

    validation = base.sanitize_github_output(base.validation_text_for_finding(finding), config)
    if validation:
        parts.extend(["", "**Validation expected after fix:**"])
        base.append_language_fence(parts, "bash", validation)
    pipeline_version = str(marker.get("version", DEFAULT_PIPELINE_VERSION) or DEFAULT_PIPELINE_VERSION)
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME} · verified repair pipeline {pipeline_version}</sub>"])
    return base.github_safe_body("\n".join(parts), limit=12000)
