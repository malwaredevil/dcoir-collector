"""DCOIR Review v56 bounded independent repair-critic batching.

Independently authored repair sets keep their existing exact-head checks and
cross-family critic gate. Compatible critic candidates are evaluated together
with identity-bound dispositions; ambiguous output fails closed per repair.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v25 as v25
import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v36 as v36
import dcoir_review_required_runtime_patch_v53 as v53
import dcoir_review_required_runtime_patch_v56_batch as batch
import dcoir_review_required_runtime_patch_v56_repair as repair

VERSION = "v56"
APPLIED_MARKER = "_dcoir_review_v56_applied"


def _batch_limit(config: Any) -> int:
    raw = getattr(config, "repair_critic_batch_max_findings", batch.MAX_BATCH_ITEMS)
    try:
        return max(1, min(batch.MAX_BATCH_ITEMS, int(raw)))
    except (TypeError, ValueError):
        return batch.MAX_BATCH_ITEMS


def synthesize_verified_repair_sets(
    module: Any,
    findings: list[dict[str, Any]],
    gh: Any,
    pr: dict[str, Any],
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
) -> list[dict[str, Any]]:
    """Preserve v53 admission policy while batching only compatible critics."""

    max_items = _batch_limit(config)
    if (
        not bool(getattr(config, "repair_critic_batching_enabled", True))
        or not bool(getattr(config, "fix_synthesis_enabled", True))
        or max_items <= 1
    ):
        return v53.synthesize_verified_repair_sets(module, findings, gh, pr, schema, config, reporter)

    del schema
    verified = v21.verify_findings_for_publication(module, findings, gh, pr, config, reporter)
    if not verified:
        reporter.update("repair-v56", "no verifier-supported findings required repair")
        return []

    head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
    pr_number = int(pr.get("number", 0) or 0)
    if not head_sha or pr_number <= 0:
        raise module.hardened.ReviewQualityError("DCOIR v56 repair stage could not determine PR identity")

    repair_budget = v33.repair_synthesis_budget(config)
    floor = v53.repair_confidence_floor(config)
    confidences = [v53.finding_confidence(raw) for raw in verified]
    qualified = sum(1 for value in confidences if value is not None and value >= floor)
    attempt_target = min(qualified, repair_budget)
    confidence_deferred = len(verified) - qualified
    budget_deferred = qualified - attempt_target
    reporter.update(
        "repair-v53",
        (
            f"verified={len(verified)}; repair_floor={floor:.2f}; confidence_qualified={qualified}; "
            f"confidence_deferred={confidence_deferred}; repair_budget={repair_budget}; "
            f"repair_attempts={attempt_target}; budget_deferred={budget_deferred}"
        ),
    )

    pr_diff = gh.get_pr_diff(pr_number) if attempt_target else ""
    right_line_index = module.base.build_diff_line_index(pr_diff) if pr_diff else {}
    file_cache: dict[str, str] = {}
    repaired_by_ordinal: dict[int, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    eligible_seen = 0
    attempts = 0

    for ordinal, (raw, confidence) in enumerate(zip(verified, confidences), start=1):
        if confidence is None or confidence < floor:
            repaired_by_ordinal[ordinal] = v53._confidence_deferred_verified_finding(
                raw, ordinal, floor, confidence
            )
            continue
        eligible_seen += 1
        if eligible_seen > repair_budget:
            repaired_by_ordinal[ordinal] = v33._deferred_verified_finding(raw, ordinal)
            continue

        attempts += 1
        finding = v25._strip_legacy_model_finding_provenance(raw)
        try:
            final, candidate = repair.prepare_candidate(
                module, ordinal, finding, gh, head_sha, pr_diff, config, file_cache
            )
            if final is not None:
                repaired_by_ordinal[ordinal] = final
            elif candidate is not None:
                pending.append(candidate)
        except Exception as exc:
            repaired_by_ordinal[ordinal] = v36._declined_item(
                finding,
                None,
                f"repair-set stage failed closed: {type(exc).__name__}: {str(exc)[:500]}",
            )

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in pending:
        groups.setdefault(item["critic_model"], []).append(item)

    critic_calls = 0
    critic_batches = 0
    for compatible in groups.values():
        for offset in range(0, len(compatible), max_items):
            chunk = compatible[offset : offset + max_items]
            results, calls = batch.run_group(
                module, chunk, file_cache, right_line_index, config
            )
            critic_calls += calls
            critic_batches += 1
            for ordinal, item in results:
                repaired_by_ordinal[ordinal] = item

    repaired = [repaired_by_ordinal[i] for i in range(1, len(verified) + 1)]
    counters = {
        key: 0
        for key in (
            "repair_sets",
            "native_blocks",
            "guidance_blocks",
            "declined",
            "precritic_declined",
            "critic_rejected",
            "postcritic_declined",
        )
    }
    for item in repaired:
        for key, value in v53._repair_result_counters(item).items():
            counters[key] += value

    reporter.update(
        "repair-v53",
        (
            f"published_verified={len(repaired)}; attempted={attempts}; repair_sets={counters['repair_sets']}; "
            f"native_blocks={counters['native_blocks']}; guidance_blocks={counters['guidance_blocks']}; "
            f"declined={counters['declined']}; precritic_declined={counters['precritic_declined']}; "
            f"critic_rejected={counters['critic_rejected']}; postcritic_declined={counters['postcritic_declined']}; "
            f"confidence_deferred={confidence_deferred}; budget_deferred={budget_deferred}"
        ),
    )
    reporter.update(
        "repair-v56",
        (
            f"attempted={attempts}; critic_candidates={len(pending)}; "
            f"critic_batches={critic_batches}; critic_calls={critic_calls}; "
            f"repair_sets={counters['repair_sets']}; declined={counters['declined']}"
        ),
    )
    v53._write_metrics(
        module,
        config,
        head_sha=head_sha,
        verified_findings=len(repaired),
        floor=floor,
        confidence_qualified=qualified,
        confidence_deferred=confidence_deferred,
        repair_budget=repair_budget,
        attempts=attempts,
        budget_deferred=budget_deferred,
        repair_sets=counters["repair_sets"],
        native_blocks=counters["native_blocks"],
        guidance_blocks=counters["guidance_blocks"],
        declined=counters["declined"],
        precritic_declined=counters["precritic_declined"],
        critic_rejected=counters["critic_rejected"],
        postcritic_declined=counters["postcritic_declined"],
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/repair-v56-batching.json",
        {
            "schema_version": "dcoir_review_repair_v56_batching_v1",
            "critic_candidates": len(pending),
            "critic_batches": critic_batches,
            "critic_calls": critic_calls,
            "max_batch_items": max_items,
        },
    )
    return repaired


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    v25.synthesize_verified_repairs = synthesize_verified_repair_sets
    setattr(module, APPLIED_MARKER, True)
