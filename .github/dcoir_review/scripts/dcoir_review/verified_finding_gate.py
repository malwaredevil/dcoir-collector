"""Stable unresolved verified-finding gate for DCOIR Review."""

from __future__ import annotations

import os
from typing import Any

from dcoir_review import publication_contract as publication
from dcoir_review import verified_finding_gate_prior as gate_prior
from dcoir_review import verified_finding_gate_state as gate_state

VERSION = "v50"
_APPLIED_ATTR = "_dcoir_review_verified_finding_gate_applied"
_PRIOR_ATTR = "_dcoir_review_verified_finding_gate_prior_context"
_STATE_ATTR = "_dcoir_review_verified_finding_gate_state"


def _render_gate_section(module: Any, state: dict[str, Any]) -> str:
    status = str(state.get("gate_status", "") or "")
    carried = int(state.get("carried_unresolved_count", 0) or 0)
    if status == "clear" or (status == "blocked" and carried == 0):
        return ""
    lines = ["", "### Verified finding gate state"]
    if status == "indeterminate":
        lines.extend(
            [
                "- Gate status: `INDETERMINATE / BLOCKED`",
                f"- Current exact-head published findings: `{int(state.get('current_published_count', 0) or 0)}`",
                f"- Prior unresolved count known but not safely attributable: `{int(state.get('indeterminate_prior_count', 0) or 0)}`",
                f"- Reason: `{str(state.get('prior_state_reason', '') or 'prior verified-finding state unavailable')}`",
                "",
                "The incremental review cannot be treated as clean until prior verified-finding state is recovered or a cumulative review re-establishes it.",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "- Gate status: `BLOCKED`",
            f"- Current exact-head published findings: `{int(state.get('current_published_count', 0) or 0)}`",
            f"- Carried unresolved prior verified findings: `{carried}`",
            "",
            "Unchanged prior verifier-supported findings remain gate-active. They are not duplicated as new inline comments on this incremental delta.",
        ]
    )
    records = [
        item
        for item in state.get("unresolved_findings", [])
        if isinstance(item, dict) and item.get("status") == "carried-unresolved"
    ]
    for record in records[:12]:
        path = str(record.get("path", "") or "")
        line = int(record.get("line", 0) or 0)
        lines.append(f"- `{path}:{line}` — prior verifier-supported finding remains unresolved")
    if len(records) > 12:
        lines.append(f"- ... and `{len(records) - 12}` more carried unresolved finding(s)")
    return "\n".join(lines)


def capture_prior_gate_context(
    review_module: Any,
    gh: Any,
    pr: dict[str, Any],
    config: Any,
    reporter: Any,
) -> None:
    if not bool(getattr(config, "verified_finding_gate_state_review", False)):
        return
    prior = gate_prior.load_prior_gate_context(review_module, gh, pr)
    setattr(review_module, _PRIOR_ATTR, prior)
    disposition = getattr(review_module, publication.DISPOSITION_ATTR, None)
    if not isinstance(disposition, dict):
        raise review_module.hardened.ReviewQualityError(
            "DCOIR verified-finding gate is missing the v45 exact-head verifier disposition"
        )
    carried = len(
        [item for item in prior.get("carried_records", []) if isinstance(item, dict)]
    )
    disposition["carried_unresolved_count"] = carried
    disposition["prior_gate_status"] = str(prior.get("status", "") or "")
    disposition["prior_gate_state_source"] = str(prior.get("source", "") or "")
    disposition["prior_gate_state_reason"] = str(prior.get("reason", "") or "")
    disposition["incremental_gate_indeterminate"] = (
        str(prior.get("status", "") or "") == "indeterminate"
    )
    update = getattr(reporter, "update", None)
    if callable(update):
        update(
            "verified-gate-state",
            (
                f"prior={disposition['prior_gate_state_source'] or 'none'}; "
                f"carried_unresolved={carried}; "
                f"indeterminate={str(disposition['incremental_gate_indeterminate']).lower()}"
            ),
        )


def apply_gate_to_review_body(
    module: Any,
    body: str,
    findings: list[dict[str, Any]],
    config: Any,
    reviewed_commit: str,
) -> str:
    if not bool(getattr(config, "verified_finding_gate_state_review", False)):
        return body
    prior = getattr(module, _PRIOR_ATTR, None)
    if not isinstance(prior, dict):
        raise module.hardened.ReviewQualityError(
            "DCOIR verified-finding gate publication is missing prior verified-finding gate context"
        )
    if not reviewed_commit:
        raise module.hardened.ReviewQualityError(
            "DCOIR verified-finding gate publication could not determine the reviewed PR head SHA"
        )
    state = gate_state.compose_state(
        [item for item in findings if isinstance(item, dict)],
        prior,
        reviewed_commit,
        str(os.environ.get("GITHUB_RUN_ID", "") or ""),
    )
    if not gate_prior.persist_gate_state(module, config, state):
        raise module.hardened.ReviewQualityError(
            "DCOIR verified-finding gate could not persist exact-head verified-finding gate state"
        )
    setattr(module, _STATE_ATTR, state)
    final = gate_state.final_disposition(state)
    module.hardened.write_debug_json_artifact_safely(
        config, gate_state.FINAL_ARTIFACT_PATH, final
    )
    section = _render_gate_section(module, state)
    if not section:
        return body
    reserve = len(section) + 1
    prefix = body.rstrip()
    if len(prefix) + reserve > 12000:
        prefix = prefix[: max(0, 12000 - reserve)].rstrip()
    return module.base.github_safe_body(f"{prefix}\n{section}", limit=12000)


def progress_completion_override(
    module: Any,
    config: Any,
    findings_count: int,
    review_event: str,
) -> tuple[str, list[str]] | None:
    """Return gate-aware terminal completion text, or ``None`` for base behavior."""

    active = getattr(module, _STATE_ATTR, None)
    if (
        not bool(getattr(config, "verified_finding_gate_state_review", False))
        or not isinstance(active, dict)
    ):
        return None
    status = str(active.get("gate_status", "") or "")
    if status not in {"blocked", "indeterminate"}:
        return None

    plural = "finding" if findings_count == 1 else "findings"
    if status == "blocked":
        carried = int(active.get("carried_unresolved_count", 0) or 0)
        carried_plural = "finding" if carried == 1 else "findings"
        message = (
            f"posted GitHub review; {findings_count} new inline {plural}; "
            f"gate BLOCKED by {carried} carried unresolved prior verified "
            f"{carried_plural}; event={review_event}"
        )
        final_lines = [
            f"- Result: GitHub review posted with `{findings_count}` new inline {plural}.",
            "- Verified finding gate: `BLOCKED`.",
            f"- Carried unresolved prior verified findings: `{carried}`.",
            f"- Review event: `{review_event}`.",
        ]
        return message, final_lines

    known = int(active.get("indeterminate_prior_count", 0) or 0)
    message = (
        f"posted GitHub review; {findings_count} new inline {plural}; "
        "gate INDETERMINATE/BLOCKED because prior verified-finding state "
        f"is incomplete; known_prior={known}; event={review_event}"
    )
    final_lines = [
        f"- Result: GitHub review posted with `{findings_count}` new inline {plural}.",
        "- Verified finding gate: `INDETERMINATE / BLOCKED`.",
        f"- Prior unresolved count known but not safely attributable: `{known}`.",
        f"- Review event: `{review_event}`.",
    ]
    return message, final_lines


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, _APPLIED_ATTR, False):
        return
    module.DCOIR_VERIFIED_FINDING_GATE_CONTRACT = gate_state.STATE_CONTRACT
    setattr(module, _APPLIED_ATTR, True)
