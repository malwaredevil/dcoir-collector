"""Stable sequential orchestration for one coordinated verified repair set."""

from __future__ import annotations

from typing import Any

from dcoir_review import repair as repair_policy
from dcoir_review import repair_precision
from dcoir_review import repair_set_contract
from dcoir_review import repair_set_edits
from dcoir_review import repair_set_prompts
from dcoir_review import repair_set_results
from dcoir_review import repair_support as repair


def build_repair_set_for_finding(
    module: Any,
    ordinal: int,
    finding: dict[str, Any],
    gh: Any,
    head_sha: str,
    pr_diff: str,
    right_line_index: dict[tuple[str, int], int],
    config: Any,
    file_cache: dict[str, str],
    author_config_override: Any | None = None,
) -> dict[str, Any]:
    """Author, verify, critic-review, and finalize one exact-head repair set."""

    path, line = repair._path_line(finding)
    if not path or line <= 0:
        raise module.hardened.ReviewQualityError(
            "DCOIR repair-set stage received an unreadable finding anchor"
        )
    if path not in file_cache:
        file_cache[path] = module.fetch_pr_file_text(gh, path, head_sha)

    author_prompt = repair_set_prompts.author_prompt(
        module, finding, file_cache[path], pr_diff, head_sha, config
    )
    author_config = (
        author_config_override
        if author_config_override is not None
        else repair_policy.build_repair_author_config(config)
    )
    author_raw, author_model, author_tier = module.hardened.openrouter_review(
        author_prompt, repair_set_contract.AUTHOR_SCHEMA, author_config, reporter=None
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair-v36/{ordinal:02d}-author.json",
        {
            "path": path,
            "line": line,
            "model": author_model,
            "service_tier": author_tier,
            "result": author_raw,
        },
    )
    author = repair_set_contract.parse_author(author_raw, finding, module.hardened)

    if author["defect_present"] is False:
        return repair_set_results.declined_item(
            finding,
            author,
            author["rationale"] or "repair author concluded the defect is absent",
            outcome=(
                repair_precision.SUPPRESSED_OUTCOME
                if author["confidence"] >= repair_precision.SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE
                else repair_set_contract.NO_SAFE_REPAIR_OUTCOME
            ),
            author_model=author_model,
            author_tier=author_tier,
        )
    if author["action"] != "repair_set":
        return repair_set_results.declined_item(
            finding,
            author,
            author["rationale"] or "repair author could not prove a safe complete repair set",
            author_model=author_model,
            author_tier=author_tier,
        )

    for edit in author["edits"]:
        target = edit["path"]
        if target not in file_cache:
            try:
                file_cache[target] = module.fetch_pr_file_text(gh, target, head_sha)
            except Exception as exc:
                return repair_set_results.declined_item(
                    finding,
                    author,
                    f"could not read repair target {target} at reviewed head: {str(exc)[:300]}",
                    author_model=author_model,
                    author_tier=author_tier,
                )

    _updated, precheck_reason = repair_set_edits.apply_edits_to_files(
        file_cache, author["edits"]
    )
    if precheck_reason:
        return repair_set_results.declined_item(
            finding,
            author,
            precheck_reason,
            author_model=author_model,
            author_tier=author_tier,
        )

    critic_prompt = repair_set_prompts.critic_prompt(
        module, finding, author, file_cache, config
    )
    critic_config = repair_set_contract.build_critic_config(config, author_model)
    critic_raw, critic_model, critic_tier = module.hardened.openrouter_review(
        critic_prompt, repair_set_contract.CRITIC_SCHEMA, critic_config, reporter=None
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair-v36/{ordinal:02d}-critic.json",
        {
            "path": path,
            "line": line,
            "model": critic_model,
            "service_tier": critic_tier,
            "result": critic_raw,
        },
    )
    accepted, critic_confidence, critic_reason = repair_set_contract.parse_critic(
        critic_raw, module.hardened
    )
    if not accepted:
        item = repair_set_results.declined_item(
            finding,
            author,
            critic_reason or "independent repair-set critic rejected the coordinated repair",
            author_model=author_model,
            author_tier=author_tier,
        )
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": critic_confidence,
            }
        )
        return item

    _updated, final_reason = repair_set_edits.apply_edits_to_files(
        file_cache, author["edits"]
    )
    if final_reason:
        item = repair_set_results.declined_item(
            finding,
            author,
            final_reason,
            author_model=author_model,
            author_tier=author_tier,
        )
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": critic_confidence,
                "critic_accepted": True,
            }
        )
        return item

    edits = repair_set_edits.annotate_native_eligibility(
        author["edits"], right_line_index
    )
    native_count = sum(1 for edit in edits if edit["native_suggestion"])
    item = repair._strip_legacy_model_finding_provenance(finding)
    item["title"] = author["display_title"]
    item["body"] = author["display_body"]
    item["suggested_replacement"] = ""
    item.pop("fix_guidance", None)
    if author["validation"]:
        item["validation"] = author["validation"]
    item[repair.REPAIR_MARKER] = {
        "version": repair_set_contract.MARKER_VERSION,
        "outcome": repair_set_contract.REPAIR_SET_OUTCOME,
        "repair_set_id": f"R{ordinal:02d}",
        "path": path,
        "line": line,
        "edits": edits,
        "edit_count": len(edits),
        "native_suggestion_count": native_count,
        "guidance_edit_count": len(edits) - native_count,
        "author_model": author_model,
        "author_service_tier": author_tier,
        "author_confidence": author["confidence"],
        "critic_model": critic_model,
        "critic_service_tier": critic_tier,
        "critic_confidence": critic_confidence,
        "critic_accepted": True,
        "reason": critic_reason[:800],
    }
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair-v36/{ordinal:02d}-final.json",
        dict(item[repair.REPAIR_MARKER]),
    )
    return item
