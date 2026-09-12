"""Preparation and finalization helpers for DCOIR Review v56 critic batching."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from dcoir_review import repair_pipeline as repair
import dcoir_review_required_runtime_patch_v30 as v30
import dcoir_review_required_runtime_patch_v36 as v36

VERSION = "v56"


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
    author = v36._parse_author(raw, finding, module.hardened)

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

    critic_config = v36._repair_critic_config(config, author_model)
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
    decision: tuple[bool, float, str],
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
    accepted, confidence, reason = decision
    if not accepted:
        item = v36._declined_item(
            finding,
            author,
            reason or "independent repair-set critic rejected the coordinated repair",
            author_model=pending["author_model"],
            author_tier=pending["author_tier"],
        )
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": confidence,
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
