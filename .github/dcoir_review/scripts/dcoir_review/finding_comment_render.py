"""Canonical owner for final DCOIR inline finding/comment rendering.

Historical runtime layers repeatedly replaced ``base.build_inline_comment``. The
production-observable chain is now composed directly here: deterministic sentinel
canonicalization, repair rendering, verified ordinary rendering, safe native
suggestions, and the v16 deterministic base renderer. Earlier renderer generations
were superseded by v16 and no longer install runtime wrappers.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import finding_comment_policy
from dcoir_review import repair_pipeline
from dcoir_review import verified_finding_render


APPLIED_MARKER = "_dcoir_finding_comment_render_applied"


def _deterministic_repair_disposition(finding: dict[str, Any]) -> str:
    marker = (
        finding.get(repair_pipeline.REPAIR_MARKER)
        if isinstance(finding.get(repair_pipeline.REPAIR_MARKER), dict)
        else {}
    )
    outcome = str(marker.get("outcome", "") or "").strip()
    if outcome in {"verified-no-safe-repair-set", "no-safe-single-line-fix"}:
        return (
            "Repair synthesis was attempted, but no independently accepted complete "
            "repair set was available."
        )
    if outcome == "repair-stage-failed-closed":
        return "Repair synthesis was attempted and failed closed before an applyable repair was published."
    if outcome == "verified-repair-budget-deferred":
        return "Repair synthesis was not attempted because the configured repair budget was exhausted."
    if outcome == "verified-repair-confidence-deferred":
        return "Repair synthesis was not attempted because the finding was below the configured repair-confidence floor."
    return ""


def _canonicalize_deterministic_sentinel(finding: dict[str, Any]) -> dict[str, Any]:
    kind = finding_comment_policy.deterministic_sentinel_kind(finding)
    if not kind:
        return finding
    item = dict(finding)
    title, body, notes = finding_comment_policy.template_for_kind(kind)
    item["title"] = str(title or item.get("title", "") or "DCOIR Review finding").strip()
    item["body"] = str(body or item.get("body", "") or "").strip()
    guidance = dict(item.get("fix_guidance")) if isinstance(item.get("fix_guidance"), dict) else {}
    canonical_notes = str(notes or "").strip()
    disposition = _deterministic_repair_disposition(item)
    guidance["notes"] = "\n\n".join(part for part in (canonical_notes, disposition) if part)
    item["fix_guidance"] = guidance
    return item


def _sanitize_github_output(base: Any, text: str, config: Any, *, neutralize_mentions: bool = True) -> str:
    sanitizer = getattr(base, "sanitize_github_output", None)
    if not callable(sanitizer):
        return str(text or "")
    try:
        return sanitizer(str(text or ""), config, neutralize_mentions=neutralize_mentions)
    except TypeError:
        return sanitizer(str(text or ""), config)


def _bounded_comment_body(base: Any, rendered: str) -> str:
    bound = getattr(base, "github_safe_body", None)
    if callable(bound):
        return str(bound(rendered, limit=12000) or "")
    return str(rendered or "")[:12000]


def _with_deterministic_validation(base: Any, finding: dict[str, Any]) -> dict[str, Any]:
    if not finding_comment_policy.deterministic_sentinel_kind(finding):
        return finding
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if str(finding.get("validation", "") or guidance.get("validation", "") or "").strip():
        return finding
    validator = getattr(base, "validation_text_for_finding", None)
    if not callable(validator):
        return finding
    validation = str(validator(finding) or "").strip()
    if not validation:
        return finding
    item = dict(finding)
    item["validation"] = validation
    return item


def _render_legacy_base_with_safe_suggestion(base: Any, finding: dict[str, Any], config: Any) -> str:
    item = _with_deterministic_validation(base, finding)
    rendered = _sanitize_github_output(base, finding_comment_policy.render_base_comment(item), config).rstrip()
    if "```suggestion" in rendered:
        return _bounded_comment_body(base, rendered)
    suggestion = finding_comment_policy.safe_single_line_suggestion(base, item)
    if not suggestion:
        return _bounded_comment_body(base, rendered)
    safe_suggestion = _sanitize_github_output(
        base,
        suggestion,
        config,
        neutralize_mentions=False,
    ).rstrip()
    return _bounded_comment_body(
        base,
        f"{rendered}\n\n```suggestion\n{safe_suggestion}\n```".strip(),
    )


def render_inline_comment(module: Any, finding: dict[str, Any], model_used: str, config: Any) -> str:
    del model_used
    base = module.base
    item = _canonicalize_deterministic_sentinel(finding)
    if isinstance(item.get(repair_pipeline.REPAIR_MARKER), dict):
        return repair_pipeline._render_repair(module, item, config)
    if verified_finding_render._is_verified_ordinary_finding(item):
        return verified_finding_render._render_verified_ordinary(base, item, config)
    return _render_legacy_base_with_safe_suggestion(base, item, config)


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    base = getattr(module, "base", None)
    if base is None:
        raise RuntimeError("DCOIR canonical finding-comment renderer requires the base review module")

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        return render_inline_comment(module, finding, model_used, config)

    base.build_inline_comment = build_inline_comment
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "apply_pareto_context_module", "render_inline_comment"]
