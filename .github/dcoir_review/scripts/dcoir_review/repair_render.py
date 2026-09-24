"""Stable rendering for verified DCOIR repair findings."""

from __future__ import annotations

from typing import Any

from dcoir_review import repair_support as support


# Preserve the historical display/provenance fallback while the numbered patch is retired.
DEFAULT_PIPELINE_VERSION = "v28"
DEFAULT_REPAIR_MARKER = "_dcoir_repair"


def safe_repair_disposition(marker: dict[str, Any]) -> str:
    """Return operator-facing repair status without model/provider rationale."""

    outcome = str(marker.get("outcome", "") or "").strip()
    if outcome == "repair-stage-failed-closed" or marker.get("critic_failed_closed") is True:
        return "Repair synthesis failed closed before a publishable repair set was produced."
    if outcome in {"verified-repair-budget-deferred"}:
        return "Repair synthesis was not attempted because the configured repair budget was exhausted."
    if outcome in {"verified-repair-confidence-deferred"}:
        return "Repair synthesis was not attempted because the finding was below the configured repair-confidence floor."
    if outcome in {"deterministic-final-declined"}:
        return "Repair synthesis passed the independent critic, but final exact-head revalidation declined the candidate; no publishable repair set was produced."
    if outcome in {"critic-declined"}:
        return "Repair synthesis produced a critic-eligible candidate, but the independent repair critic rejected it; no publishable repair set was produced."
    if outcome in {"author-declined", "deterministic-precheck-declined"}:
        return "Repair synthesis did not produce a critic-eligible complete repair set; no publishable repair set was produced."
    if outcome in {"verified-no-safe-repair-set", "no-safe-single-line-fix"}:
        if marker.get("critic_accepted") is True:
            return "Repair synthesis passed the independent critic, but final exact-head revalidation declined the candidate; no publishable repair set was produced."
        if str(marker.get("critic_model", "") or "").strip():
            return "Repair synthesis produced a critic-eligible candidate, but the independent repair critic rejected it; no publishable repair set was produced."
        return "Repair synthesis did not produce a critic-eligible complete repair set; no publishable repair set was produced."
    if outcome and outcome not in {"native-suggestion", "verified-repair-set"}:
        return "Repair synthesis did not publish an applyable repair set for this verified finding."
    return ""


def render_repair(
    module: Any,
    finding: dict[str, Any],
    config: Any,
    *,
    repair_marker: str = DEFAULT_REPAIR_MARKER,
) -> str:
    base = module.base
    marker = finding.get(repair_marker) if isinstance(finding.get(repair_marker), dict) else {}
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
        path, line = support._path_line(finding)
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
    notes = safe_repair_disposition(marker)
    if not notes and marker.get("outcome") in {"native-suggestion", "verified-repair-set"} and guidance:
        notes = base.fix_guidance_value_text(guidance.get("notes", ""), config)
    if notes:
        parts.extend(["", "**Repair status:**", "", notes])

    validation = base.sanitize_github_output(base.validation_text_for_finding(finding), config)
    if validation:
        parts.extend(["", "**Validation expected after fix:**"])
        base.append_language_fence(parts, "bash", validation)
    pipeline_version = str(marker.get("version", DEFAULT_PIPELINE_VERSION) or DEFAULT_PIPELINE_VERSION)
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME} · verified repair pipeline {pipeline_version}</sub>"])
    return base.github_safe_body("\n".join(parts), limit=12000)
