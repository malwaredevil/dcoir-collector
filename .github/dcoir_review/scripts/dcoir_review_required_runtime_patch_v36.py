"""DCOIR Review v36 coordinated verified repair sets.

repair-v30 deliberately restricted native GitHub suggestions to an exact single
source line. That was a useful safety bootstrap, but it prevents verified defects
from receiving Copilot-class repairs when the smallest correct fix spans a
contiguous block, multiple ranges, or multiple files.

v36 keeps the finding-verification boundary and human-application model while
upgrading repair synthesis to a bounded repair set:

    verify -> repair-set author -> exact-head deterministic validation
           -> independent whole-set critic -> exact-head revalidation
           -> one or more linked GitHub suggestion comments

Each edit carries an exact path, start/end line, original block, replacement
block, and purpose. Contiguous changed ranges can render as native GitHub
suggestions. Non-contiguous or cross-file repairs become multiple linked
suggestion comments. Necessary edits that cannot be anchored to the PR's
right-side diff remain explicit coordinated guidance rather than being silently
dropped or posted as invalid suggestions.

This overlay never writes to the pull-request branch.
"""

from __future__ import annotations

import ast
from typing import Any

from dcoir_review import finding_verifier as v21
from dcoir_review import repair as repair_policy
from dcoir_review import repair_pipeline as repair
from dcoir_review import repair_precision
from dcoir_review import finding_comment_policy
from dcoir_review import repair_set_contract
from dcoir_review import repair_set_results
from dcoir_review import repair_set_builder


VERSION = repair_set_contract.MARKER_VERSION
APPLIED_MARKER = "_dcoir_review_v36_applied"
REPAIR_SET_OUTCOME = repair_set_contract.REPAIR_SET_OUTCOME

_path_line = repair._path_line






def synthesize_verified_repair_sets(
    module: Any,
    findings: list[dict[str, Any]],
    gh: Any,
    pr: dict[str, Any],
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
) -> list[dict[str, Any]]:
    del schema
    verified = v21.verify_findings_for_publication(module, findings, gh, pr, config, reporter)
    if not verified:
        reporter.update("repair-v36", "no verifier-supported findings required repair")
        return []

    head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
    if not head_sha:
        raise module.hardened.ReviewQualityError("DCOIR v36 repair stage could not determine the PR head SHA")
    pr_number = int(pr.get("number", 0) or 0)
    if pr_number <= 0:
        raise module.hardened.ReviewQualityError("DCOIR v36 repair stage could not determine the PR number")
    pr_diff = gh.get_pr_diff(pr_number)
    right_line_index = module.base.build_diff_line_index(pr_diff)
    repair_budget = repair_policy.repair_synthesis_budget(config)
    repair_count = min(len(verified), repair_budget)
    deferred_count = len(verified) - repair_count
    reporter.update(
        "repair-v36",
        f"verified={len(verified)}; repair_budget={repair_budget}; repair_sets={repair_count}; deferred={deferred_count}",
    )

    file_cache: dict[str, str] = {}
    repaired: list[dict[str, Any]] = []
    repair_sets = 0
    native_blocks = 0
    guidance_blocks = 0
    declined = 0
    for ordinal, raw in enumerate(verified, start=1):
        if ordinal > repair_count:
            repaired.append(repair_policy.budget_deferred_verified_finding(raw, ordinal, repair))
            continue
        finding = repair._strip_legacy_model_finding_provenance(raw)
        try:
            item = repair_set_builder.build_repair_set_for_finding(
                module,
                ordinal,
                finding,
                gh,
                head_sha,
                pr_diff,
                right_line_index,
                config,
                file_cache,
            )
        except Exception as exc:
            item = repair_set_results.declined_item(finding, None, f"repair-set stage failed closed: {type(exc).__name__}: {str(exc)[:500]}")
        marker = item.get(repair.REPAIR_MARKER) if isinstance(item.get(repair.REPAIR_MARKER), dict) else {}
        if marker.get("outcome") == REPAIR_SET_OUTCOME:
            repair_sets += 1
            native_blocks += int(marker.get("native_suggestion_count", 0) or 0)
            guidance_blocks += int(marker.get("guidance_edit_count", 0) or 0)
        elif marker.get("outcome") != repair_precision.SUPPRESSED_OUTCOME:
            declined += 1
        repaired.append(item)

    reporter.update(
        "repair-v36",
        (
            f"published_verified={len(repaired)}; repair_sets={repair_sets}; "
            f"native_blocks={native_blocks}; guidance_blocks={guidance_blocks}; declined={declined}; deferred={deferred_count}"
        ),
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/repair-v36-metrics.json",
        {
            "schema_version": "dcoir_review_repair_v36_metrics_v1",
            "head_sha": head_sha,
            "verified_findings": len(repaired),
            "repair_budget": repair_budget,
            "repair_sets": repair_sets,
            "native_suggestion_blocks": native_blocks,
            "guidance_edit_blocks": guidance_blocks,
            "declined": declined,
            "repair_budget_deferred": deferred_count,
        },
    )
    return repaired


def _render_primary_body(module: Any, finding: dict[str, Any], config: Any, marker: dict[str, Any]) -> str:
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
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME} · verified repair pipeline {VERSION}</sub>"])
    return base.github_safe_body("\n".join(parts), limit=12000)


def _render_edit_body(
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
        parts.append(_render_primary_body(module, finding, config, marker))
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
    marker = finding.get(repair.REPAIR_MARKER) if isinstance(finding.get(repair.REPAIR_MARKER), dict) else {}
    if marker.get("version") != VERSION or marker.get("outcome") != REPAIR_SET_OUTCOME:
        path, line = _path_line(finding)
        return [{"path": path, "line": line, "side": "RIGHT", "body": module.base.build_inline_comment(finding, model_used, config)}]

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
            "body": _render_edit_body(module, finding, primary_edit, marker, config, primary=True),
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
                "body": _render_edit_body(module, finding, edit, marker, config, primary=False),
            }
            if edit["start_line"] < edit["end_line"]:
                payload["start_line"] = edit["start_line"]
                payload["start_side"] = "RIGHT"
            comments.append(payload)
    else:
        path, line = _path_line(finding)
        comments.append(
            {
                "path": path,
                "line": line,
                "side": "RIGHT",
                "body": _render_primary_body(module, finding, config, marker),
            }
        )

    if guidance_edits:
        guidance_lines = ["", f"**Additional coordinated edits for `{marker.get('repair_set_id', 'repair')}`:**"]
        for edit in guidance_edits:
            purpose = module.base.sanitize_github_output(str(edit.get("purpose", "") or "").strip(), config)
            replacement = module.base.sanitize_github_output(str(edit.get("replacement", "") or ""), config, neutralize_mentions=False)
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

    if not hasattr(module, "build_review_comments_for_finding"):
        raise RuntimeError("DCOIR v36 requires the repair-set publication expansion seam")
    module.build_review_comments_for_finding = lambda finding, model_used, config: build_review_comments_for_finding(
        module, finding, model_used, config
    )

    setattr(module, APPLIED_MARKER, True)
