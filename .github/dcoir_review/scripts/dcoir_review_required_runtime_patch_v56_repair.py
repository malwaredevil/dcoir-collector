"""Preparation and finalization helpers for DCOIR Review v56 critic batching."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from dcoir_review import repair as repair_policy
from dcoir_review import repair_pipeline as repair
import dcoir_review_required_runtime_patch_v30 as v30
import dcoir_review_required_runtime_patch_v36 as v36

VERSION = "v56"
MAX_ANCHOR_RECOVERY_LINE_DRIFT = 12


def _exact_original_locations(file_text: str, original: str) -> list[tuple[int, int]]:
    original = v36._normalized_newlines(original)
    original_lines = original.splitlines()
    if not original_lines or len(original_lines) > v36.MAX_EDIT_RANGE_LINES:
        return []
    canonical_original = "\n".join(original_lines)
    lines = v36._normalized_newlines(file_text).splitlines()
    width = len(original_lines)
    matches: list[tuple[int, int]] = []
    for offset in range(0, len(lines) - width + 1):
        if "\n".join(lines[offset : offset + width]) == canonical_original:
            matches.append((offset + 1, offset + width))
    return matches


def recover_author_edit_anchors(
    module: Any,
    raw: Any,
    gh: Any,
    head_sha: str,
    file_cache: dict[str, str],
) -> tuple[Any, list[dict[str, Any]]]:
    """Repair only exact-head line metadata; never invent edit semantics."""

    if not isinstance(raw, dict) or not isinstance(raw.get("edits"), list):
        return raw, []
    recovered = copy.deepcopy(raw)
    changes: list[dict[str, Any]] = []
    for edit in recovered["edits"]:
        if not isinstance(edit, dict):
            continue
        path = str(edit.get("path", "") or "").strip()
        original = v36._normalized_newlines(str(edit.get("original", "") or ""))
        if (
            not path
            or path.startswith("/")
            or ".." in Path(path).parts
            or not original
            or len(original) > v36.MAX_EDIT_TEXT_CHARS
            or any(token in original for token in ("```", "~~~", "\x00"))
        ):
            continue
        if path not in file_cache:
            try:
                file_cache[path] = module.fetch_pr_file_text(gh, path, head_sha)
            except Exception:
                continue
        matches = _exact_original_locations(file_cache[path], original)
        if not matches:
            continue
        try:
            declared_start = int(edit.get("start_line", 0) or 0)
        except (TypeError, ValueError):
            declared_start = 0
        original_line_count = len(original.splitlines())
        derived = (declared_start, declared_start + original_line_count - 1)
        selected: tuple[int, int] | None = None
        if declared_start > 0 and derived in matches:
            selected = derived
        elif (
            declared_start > 0
            and len(matches) == 1
            and abs(matches[0][0] - declared_start) <= MAX_ANCHOR_RECOVERY_LINE_DRIFT
        ):
            selected = matches[0]
        if selected is None:
            continue
        old_start = edit.get("start_line")
        old_end = edit.get("end_line")
        if old_start == selected[0] and old_end == selected[1]:
            continue
        edit["start_line"], edit["end_line"] = selected
        changes.append(
            {
                "path": path,
                "from": [old_start, old_end],
                "to": [selected[0], selected[1]],
                "basis": "exact reviewed-head original block",
            }
        )
    return recovered, changes


def critic_item_id(ordinal: int, finding: dict[str, Any], author: dict[str, Any]) -> str:
    payload = {
        "ordinal": ordinal,
        "path": finding.get("path", ""),
        "line": finding.get("line", 0),
        "title": finding.get("title", ""),
        "body": finding.get("body", ""),
        "validation": finding.get("validation", ""),
        "edits": author.get("edits", []),
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"C{ordinal:02d}-{digest}"


def prepare_candidate(
    module: Any,
    ordinal: int,
    finding: dict[str, Any],
    gh: Any,
    head_sha: str,
    pr_diff: str,
    config: Any,
    file_cache: dict[str, str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Run the historical author and pre-critic exact-head checks only."""

    path, line = repair._path_line(finding)
    if not path or line <= 0:
        raise module.hardened.ReviewQualityError("DCOIR v56 repair stage received an unreadable finding anchor")
    if path not in file_cache:
        file_cache[path] = module.fetch_pr_file_text(gh, path, head_sha)

    prompt = v36._repair_author_prompt(module, finding, file_cache[path], pr_diff, head_sha, config)
    raw, author_model, author_tier = module.hardened.openrouter_review(
        prompt, v36.REPAIR_SET_AUTHOR_SCHEMA, config, reporter=None
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair-v36/{ordinal:02d}-author.json",
        {"path": path, "line": line, "model": author_model, "service_tier": author_tier, "result": raw},
    )
    normalized_raw, anchor_changes = recover_author_edit_anchors(
        module, raw, gh, head_sha, file_cache
    )
    if anchor_changes:
        module.hardened.write_debug_json_artifact_safely(
            config,
            f"responses/repair-v56/{ordinal:02d}-author-anchor-recovery.json",
            {"changes": anchor_changes},
        )
    author = v36._parse_author(normalized_raw, finding, module.hardened)

    if author["defect_present"] is False:
        outcome = (
            v30.SUPPRESSED_OUTCOME
            if author["confidence"] >= v30.SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE
            else v36.NO_SAFE_REPAIR_OUTCOME
        )
        return (
            v36._declined_item(
                finding,
                author,
                author["rationale"] or "repair author concluded the defect is absent",
                outcome=outcome,
                author_model=author_model,
                author_tier=author_tier,
            ),
            None,
        )
    if author["action"] != "repair_set":
        return (
            v36._declined_item(
                finding,
                author,
                author["rationale"] or "repair author could not prove a safe complete repair set",
                author_model=author_model,
                author_tier=author_tier,
            ),
            None,
        )

    for edit in author["edits"]:
        target = edit["path"]
        if target not in file_cache:
            try:
                file_cache[target] = module.fetch_pr_file_text(gh, target, head_sha)
            except Exception as exc:
                return (
                    v36._declined_item(
                        finding,
                        author,
                        f"could not read repair target {target} at reviewed head: {str(exc)[:300]}",
                        author_model=author_model,
                        author_tier=author_tier,
                    ),
                    None,
                )

    _updated, reason = v36._apply_edits_to_files(file_cache, author["edits"])
    if reason:
        return (
            v36._declined_item(
                finding, author, reason, author_model=author_model, author_tier=author_tier
            ),
            None,
        )

    critic_config = repair_policy.build_repair_critic_config(config, author_model)
    return None, {
        "ordinal": ordinal,
        "finding": finding,
        "author": author,
        "author_model": author_model,
        "author_tier": author_tier,
        "critic_model": str(getattr(critic_config, "model", "") or "").strip(),
        "critic_item_id": critic_item_id(ordinal, finding, author),
    }


def finalize_candidate(
    module: Any,
    pending: dict[str, Any],
    decision: tuple[bool, float, str, bool],
    critic_model: str,
    critic_tier: str,
    right_line_index: dict[tuple[str, int], int],
    file_cache: dict[str, str],
    config: Any,
    batch_size: int,
) -> dict[str, Any]:
    """Apply the unchanged post-critic recheck and v36 publication contract."""

    finding = pending["finding"]
    author = pending["author"]
    accepted, confidence, reason, critic_failed_closed = decision
    if not accepted:
        outcome = "repair-stage-failed-closed" if critic_failed_closed else v36.NO_SAFE_REPAIR_OUTCOME
        item = v36._declined_item(
            finding,
            author,
            reason or "independent repair-set critic rejected the coordinated repair",
            outcome=outcome,
            author_model=pending["author_model"],
            author_tier=pending["author_tier"],
        )
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": confidence,
                "critic_failed_closed": critic_failed_closed,
            }
        )
        return item

    _updated, final_reason = v36._apply_edits_to_files(file_cache, author["edits"])
    if final_reason:
        item = v36._declined_item(
            finding,
            author,
            final_reason,
            author_model=pending["author_model"],
            author_tier=pending["author_tier"],
        )
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": confidence,
                "critic_accepted": True,
                "critic_failed_closed": False,
            }
        )
        return item

    edits = v36._annotate_native_eligibility(author["edits"], right_line_index)
    native_count = sum(1 for edit in edits if edit["native_suggestion"])
    path, line = repair._path_line(finding)
    item = repair._strip_legacy_model_finding_provenance(finding)
    item["title"] = author["display_title"]
    item["body"] = author["display_body"]
    item["suggested_replacement"] = ""
    item.pop("fix_guidance", None)
    if author["validation"]:
        item["validation"] = author["validation"]
    item[repair.REPAIR_MARKER] = {
        "version": v36.VERSION,
        "critic_batch_version": VERSION,
        "outcome": v36.REPAIR_SET_OUTCOME,
        "repair_set_id": f"R{pending['ordinal']:02d}",
        "path": path,
        "line": line,
        "edits": edits,
        "edit_count": len(edits),
        "native_suggestion_count": native_count,
        "guidance_edit_count": len(edits) - native_count,
        "author_model": pending["author_model"],
        "author_service_tier": pending["author_tier"],
        "author_confidence": author["confidence"],
        "critic_model": critic_model,
        "critic_service_tier": critic_tier,
        "critic_confidence": confidence,
        "critic_accepted": True,
        "critic_failed_closed": False,
        "critic_item_id": pending["critic_item_id"],
        "critic_batch_size": batch_size,
        "reason": reason[:800],
    }
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair-v36/{pending['ordinal']:02d}-final.json",
        dict(item[repair.REPAIR_MARKER]),
    )
    return item
