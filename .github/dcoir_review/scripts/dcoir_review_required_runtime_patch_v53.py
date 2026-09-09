"""DCOIR Review v53 configured repair-confidence execution gate.

The governed configuration has long separated finding publication confidence
from repair-synthesis confidence. The legacy fix-synthesis path honored
``fix_synthesis_min_confidence`` before spending a repair model call, but the
v33/v36 verified-repair replacement accidentally reduced repair eligibility to
only an enabled/count budget. That allowed verifier-supported findings below
the configured repair floor to enter the expensive repair-author/critic tail.

v53 restores the existing policy boundary without changing finding publication:

* every verifier-supported finding remains publishable;
* only findings with a finite numeric confidence at or above the configured
  repair floor may enter v36 repair synthesis;
* below-floor or malformed confidence fails closed for repair only and receives
  an explicit non-applyable repair status;
* the configured repair-count budget applies to eligible findings rather than
  raw verified-finding ordinals; and
* every attempted repair continues through the unchanged v36 author, exact-head
  structural checks, independent critic, and final exact-head revalidation.

Detector-authored replacement text remains untrusted and is stripped by v25.
This overlay performs no branch mutation and changes no provider/model routing.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v25 as v25
import dcoir_review_required_runtime_patch_v30 as v30
import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v36 as v36


VERSION = "v53"
APPLIED_MARKER = "_dcoir_review_v53_applied"
CONFIDENCE_DEFERRED_OUTCOME = "verified-repair-confidence-deferred"
METRICS_SCHEMA_VERSION = "dcoir_review_repair_v53_metrics_v1"


def repair_confidence_floor(config: Any) -> float:
    """Return the configured repair floor, failing closed to the legacy 0.80."""

    raw = getattr(config, "fix_synthesis_min_confidence", 0.80)
    if isinstance(raw, bool):
        return 0.80
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.80
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        return 0.80
    return value


def finding_confidence(finding: dict[str, Any]) -> float | None:
    """Return a valid finding confidence or None for repair-ineligible input."""

    raw = finding.get("confidence")
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        return None
    return value


def _confidence_deferred_verified_finding(
    raw: dict[str, Any],
    ordinal: int,
    floor: float,
    confidence: float | None,
) -> dict[str, Any]:
    """Keep a verified finding visible while withholding repair synthesis."""

    finding = v25._strip_legacy_model_finding_provenance(raw)
    path, line = v25._path_line(finding)
    finding["suggested_replacement"] = ""
    if confidence is None:
        reason = "finding confidence was missing, malformed, non-finite, or outside 0.0..1.0"
        detail = "its confidence could not be safely compared with the configured repair-synthesis floor"
    else:
        reason = f"finding confidence {confidence:.2f} was below configured repair floor {floor:.2f}"
        detail = f"its confidence {confidence:.2f} is below the configured repair-synthesis floor {floor:.2f}"
    finding["fix_guidance"] = {
        "language": Path(path).suffix.lstrip(".") or "text",
        "notes": (
            "Verifier-supported finding; repair synthesis was not attempted because "
            + detail
            + ". The finding remains published, but no one-click repair is authorized by this stage."
        )[:1400],
    }
    finding[v25.REPAIR_MARKER] = {
        "version": VERSION,
        "outcome": CONFIDENCE_DEFERRED_OUTCOME,
        "path": path,
        "line": line,
        "ordinal": ordinal,
        "finding_confidence": confidence,
        "repair_confidence_floor": floor,
        "reason": reason,
    }
    return finding


def _repair_result_counters(item: dict[str, Any]) -> dict[str, int]:
    marker = item.get(v25.REPAIR_MARKER) if isinstance(item.get(v25.REPAIR_MARKER), dict) else {}
    outcome = str(marker.get("outcome", "") or "")
    counters = {
        "repair_sets": 0,
        "native_blocks": 0,
        "guidance_blocks": 0,
        "declined": 0,
        "precritic_declined": 0,
        "critic_rejected": 0,
        "postcritic_declined": 0,
    }
    if outcome == v36.REPAIR_SET_OUTCOME:
        counters["repair_sets"] = 1
        counters["native_blocks"] = int(marker.get("native_suggestion_count", 0) or 0)
        counters["guidance_blocks"] = int(marker.get("guidance_edit_count", 0) or 0)
        return counters
    if outcome == v30.SUPPRESSED_OUTCOME:
        return counters

    counters["declined"] = 1
    critic_model = str(marker.get("critic_model", "") or "").strip()
    if not critic_model:
        counters["precritic_declined"] = 1
    elif marker.get("critic_accepted") is True:
        counters["postcritic_declined"] = 1
    else:
        counters["critic_rejected"] = 1
    return counters


def synthesize_verified_repair_sets(
    module: Any,
    findings: list[dict[str, Any]],
    gh: Any,
    pr: dict[str, Any],
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
) -> list[dict[str, Any]]:
    """Run v36 repair synthesis only for findings admitted by configured policy."""

    del schema
    verified = v21.verify_findings_for_publication(module, findings, gh, pr, config, reporter)
    if not verified:
        reporter.update("repair-v53", "no verifier-supported findings required repair")
        return []

    head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
    if not head_sha:
        raise module.hardened.ReviewQualityError("DCOIR v53 repair stage could not determine the PR head SHA")
    pr_number = int(pr.get("number", 0) or 0)
    if pr_number <= 0:
        raise module.hardened.ReviewQualityError("DCOIR v53 repair stage could not determine the PR number")

    repair_budget = v33.repair_synthesis_budget(config)
    floor = repair_confidence_floor(config)
    enabled = bool(getattr(config, "fix_synthesis_enabled", True))

    confidence_values = [finding_confidence(raw) for raw in verified]
    eligible_total = sum(1 for value in confidence_values if value is not None and value >= floor)
    confidence_deferred_total = len(verified) - eligible_total
    repair_attempt_target = min(eligible_total, repair_budget) if enabled else 0
    budget_deferred_total = eligible_total - repair_attempt_target

    reporter.update(
        "repair-v53",
        (
            f"verified={len(verified)}; repair_floor={floor:.2f}; eligible={eligible_total}; "
            f"confidence_deferred={confidence_deferred_total}; repair_budget={repair_budget}; "
            f"repair_attempts={repair_attempt_target}; budget_deferred={budget_deferred_total}"
        ),
    )

    pr_diff = ""
    right_line_index: dict[tuple[str, int], int] = {}
    if repair_attempt_target > 0:
        pr_diff = gh.get_pr_diff(pr_number)
        right_line_index = module.base.build_diff_line_index(pr_diff)

    file_cache: dict[str, str] = {}
    repaired: list[dict[str, Any]] = []
    eligible_seen = 0
    attempts = 0
    repair_sets = 0
    native_blocks = 0
    guidance_blocks = 0
    declined = 0
    precritic_declined = 0
    critic_rejected = 0
    postcritic_declined = 0

    for ordinal, (raw, confidence) in enumerate(zip(verified, confidence_values), start=1):
        if not enabled:
            repaired.append(v33._deferred_verified_finding(raw, ordinal))
            continue

        if confidence is None or confidence < floor:
            repaired.append(_confidence_deferred_verified_finding(raw, ordinal, floor, confidence))
            continue

        eligible_seen += 1
        if eligible_seen > repair_budget:
            repaired.append(v33._deferred_verified_finding(raw, ordinal))
            continue

        attempts += 1
        finding = v25._strip_legacy_model_finding_provenance(raw)
        try:
            item = v36._build_repair_set_for_finding(
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
            item = v36._declined_item(
                finding,
                None,
                f"repair-set stage failed closed: {type(exc).__name__}: {str(exc)[:500]}",
            )

        counters = _repair_result_counters(item)
        repair_sets += counters["repair_sets"]
        native_blocks += counters["native_blocks"]
        guidance_blocks += counters["guidance_blocks"]
        declined += counters["declined"]
        precritic_declined += counters["precritic_declined"]
        critic_rejected += counters["critic_rejected"]
        postcritic_declined += counters["postcritic_declined"]
        repaired.append(item)

    reporter.update(
        "repair-v53",
        (
            f"published_verified={len(repaired)}; attempted={attempts}; repair_sets={repair_sets}; "
            f"native_blocks={native_blocks}; guidance_blocks={guidance_blocks}; declined={declined}; "
            f"precritic_declined={precritic_declined}; critic_rejected={critic_rejected}; "
            f"postcritic_declined={postcritic_declined}; confidence_deferred={confidence_deferred_total}; "
            f"budget_deferred={budget_deferred_total}"
        ),
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/repair-v53-metrics.json",
        {
            "schema_version": METRICS_SCHEMA_VERSION,
            "head_sha": head_sha,
            "verified_findings": len(repaired),
            "repair_confidence_floor": floor,
            "repair_eligible_findings": eligible_total,
            "repair_confidence_deferred": confidence_deferred_total,
            "repair_budget": repair_budget,
            "repair_attempts": attempts,
            "repair_budget_deferred": budget_deferred_total,
            "repair_sets": repair_sets,
            "native_suggestion_blocks": native_blocks,
            "guidance_edit_blocks": guidance_blocks,
            "declined": declined,
            "precritic_declined": precritic_declined,
            "critic_rejected": critic_rejected,
            "postcritic_declined": postcritic_declined,
        },
    )
    return repaired


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    # v25's public synthesis wrapper resolves this symbol dynamically. v30's
    # suppression wrapper therefore remains outside this replacement, while v36
    # continues to own every repair attempt's author/critic/exact-head mechanics.
    v25.synthesize_verified_repairs = lambda mod, findings, gh, pr, schema, config, reporter: synthesize_verified_repair_sets(
        mod, findings, gh, pr, schema, config, reporter
    )
    setattr(module, APPLIED_MARKER, True)
