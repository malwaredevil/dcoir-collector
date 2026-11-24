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
from dcoir_review import repair_render
from dcoir_review import repair_set_contract
from dcoir_review import verified_finding_render


APPLIED_MARKER = "_dcoir_finding_comment_render_applied"


def _deterministic_repair_disposition(finding: dict[str, Any]) -> str:
    marker = (
        finding.get(repair_pipeline.REPAIR_MARKER)
        if isinstance(finding.get(repair_pipeline.REPAIR_MARKER), dict)
        else {}
    )
    return repair_render.safe_repair_disposition(marker)


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



def _render_repair_set_primary_body(module: Any, finding: dict[str, Any], config: Any, marker: dict[str, Any]) -> str:
    base = module.base
    raw_title = str(finding.get("title", "Finding") or "Finding").strip()
    raw_body = str(finding.get("body", "") or "").strip()
    deterministic_kind = finding_comment_policy.deterministic_sentinel_kind(finding)
    if deterministic_kind:
        canonical_title, canonical_body, _notes = finding_comment_policy.template_for_kind(deterministic_kind)
        raw_title = str(canonical_title or raw_title).strip()
        raw_body = str(canonical_body or raw_body).strip()
    title = base.markdown_emphasis_safe_text(base.sanitize_github_output(raw_title, config))
    severity = base.markdown_emphasis_safe_text(str(finding.get("severity", "medium") or "medium").upper())
    body = base.strip_model_validation_section(base.sanitize_github_output(raw_body, config))
    repair_set_id = str(marker.get("repair_set_id", "") or "repair")
    edits = marker.get("edits") if isinstance(marker.get("edits"), list) else []
    native = sum(1 for edit in edits if isinstance(edit, dict) and edit.get("native_suggestion"))
    guidance = len(edits) - native
    parts = [
        f"**{severity}: {title}**",
        "",
        body,
        "",
        f"**Coordinated repair set `{repair_set_id}`:** {len(edits)} edit block(s); {native} native GitHub suggestion(s); {guidance} guidance-only block(s).",
    ]
    validation = base.sanitize_github_output(base.validation_text_for_finding(finding), config)
    if validation:
        parts.extend(["", "**Validation expected after applying the full repair set:**"])
        base.append_language_fence(parts, "bash", validation)
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME} · verified repair pipeline {repair_set_contract.MARKER_VERSION}</sub>"])
    return base.github_safe_body("\n".join(parts), limit=12000)


def _render_repair_set_edit_body(
    module: Any,
    finding: dict[str, Any],
    edit: dict[str, Any],
    marker: dict[str, Any],
    config: Any,
    *,
    primary: bool,
) -> str:
    base = module.base
    repair_set_id = str(marker.get("repair_set_id", "") or "repair")
    ordinal = int(edit.get("edit_ordinal", 0) or 0)
    purpose = base.sanitize_github_output(str(edit.get("purpose", "") or "Coordinated repair edit").strip(), config)
    replacement = str(edit.get("replacement", "") or "")
    total = len(marker.get("edits", [])) if isinstance(marker.get("edits"), list) else 0
    parts: list[str] = []
    if primary:
        parts.append(_render_repair_set_primary_body(module, finding, config, marker))
        parts.extend(["", f"**Edit {ordinal} of {total}:** {purpose}"])
    else:
        parts.extend([f"**Coordinated repair `{repair_set_id}` · edit {ordinal} of {total}**", "", purpose])
    if edit.get("native_suggestion"):
        safe = base.sanitize_github_output(replacement, config, neutralize_mentions=False)
        parts.extend(["", "```suggestion", safe, "```"])
    else:
        language = base.language_hint_for_path(str(edit.get("path", "") or ""))
        parts.extend(["", "**Required coordinated edit (not natively anchorable on this PR diff):**"])
        base.append_language_fence(parts, language, replacement)
        reason = base.sanitize_github_output(str(edit.get("native_reason", "") or "").strip(), config)
        if reason:
            parts.extend(["", reason])
    return base.github_safe_body("\n".join(parts), limit=12000)


def build_review_comments_for_finding(
    module: Any,
    finding: dict[str, Any],
    model_used: str,
    config: Any,
) -> list[dict[str, Any]]:
    """Expand one logical finding into bounded GitHub review comments."""

    marker = (
        finding.get(repair_pipeline.REPAIR_MARKER)
        if isinstance(finding.get(repair_pipeline.REPAIR_MARKER), dict)
        else {}
    )
    if (
        marker.get("version") != repair_set_contract.MARKER_VERSION
        or marker.get("outcome") != repair_set_contract.REPAIR_SET_OUTCOME
    ):
        path, line = repair_pipeline._path_line(finding)
        return [
            {
                "path": path,
                "line": line,
                "side": "RIGHT",
                "body": module.base.build_inline_comment(finding, model_used, config),
            }
        ]

    edits = marker.get("edits") if isinstance(marker.get("edits"), list) else []
    native_edits = [edit for edit in edits if isinstance(edit, dict) and edit.get("native_suggestion")]
    guidance_edits = [edit for edit in edits if isinstance(edit, dict) and not edit.get("native_suggestion")]
    comments: list[dict[str, Any]] = []

    primary_edit = native_edits[0] if native_edits else None
    if primary_edit is not None:
        payload: dict[str, Any] = {
            "path": primary_edit["path"],
            "line": primary_edit["end_line"],
            "side": "RIGHT",
            "body": _render_repair_set_edit_body(module, finding, primary_edit, marker, config, primary=True),
        }
        if primary_edit["start_line"] < primary_edit["end_line"]:
            payload["start_line"] = primary_edit["start_line"]
            payload["start_side"] = "RIGHT"
        comments.append(payload)
        for edit in native_edits[1:]:
            payload = {
                "path": edit["path"],
                "line": edit["end_line"],
                "side": "RIGHT",
                "body": _render_repair_set_edit_body(module, finding, edit, marker, config, primary=False),
            }
            if edit["start_line"] < edit["end_line"]:
                payload["start_line"] = edit["start_line"]
                payload["start_side"] = "RIGHT"
            comments.append(payload)
    else:
        path, line = repair_pipeline._path_line(finding)
        comments.append(
            {
                "path": path,
                "line": line,
                "side": "RIGHT",
                "body": _render_repair_set_primary_body(module, finding, config, marker),
            }
        )

    if guidance_edits:
        guidance_lines = ["", f"**Additional coordinated edits for `{marker.get('repair_set_id', 'repair')}`:**"]
        for edit in guidance_edits:
            purpose = module.base.sanitize_github_output(str(edit.get("purpose", "") or "").strip(), config)
            replacement = module.base.sanitize_github_output(
                str(edit.get("replacement", "") or ""), config, neutralize_mentions=False
            )
            language = module.base.language_hint_for_path(str(edit.get("path", "") or ""))
            guidance_lines.extend(
                [
                    "",
                    f"- `{edit.get('path')}:{edit.get('start_line')}-{edit.get('end_line')}` — {purpose}",
                    f"```{language}",
                    replacement,
                    "```",
                ]
            )
        comments[0]["body"] = module.base.github_safe_body(
            comments[0]["body"] + "\n" + "\n".join(guidance_lines), limit=12000
        )
    return comments

def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    base = getattr(module, "base", None)
    if base is None:
        raise RuntimeError("DCOIR canonical finding-comment renderer requires the base review module")

    if not hasattr(module, "build_review_comments_for_finding"):
        raise RuntimeError("DCOIR canonical finding-comment renderer requires the review-comment expansion seam")

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        return render_inline_comment(module, finding, model_used, config)

    base.build_inline_comment = build_inline_comment
    module.build_review_comments_for_finding = lambda finding, model_used, config: build_review_comments_for_finding(
        module, finding, model_used, config
    )
    setattr(module, APPLIED_MARKER, True)


__all__ = [
    "APPLIED_MARKER",
    "apply_pareto_context_module",
    "build_review_comments_for_finding",
    "render_inline_comment",
]
