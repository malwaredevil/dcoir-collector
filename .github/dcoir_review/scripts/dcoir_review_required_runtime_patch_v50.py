"""Architecture-B v50 unresolved verified-finding gate overlay."""

from __future__ import annotations

import os
from typing import Any

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v45 as v45
import dcoir_review_required_runtime_patch_v50_prior as gate_prior
import dcoir_review_required_runtime_patch_v50_state as gate_state

VERSION = "v50"
_APPLIED_ATTR = "_dcoir_v50_applied"
_CONFIG_STORAGE = "_dcoir_v50_original_load_pareto_context_config"
_VERIFIER_STORAGE = "_dcoir_v50_original_verify_findings_for_publication"
_BODY_STORAGE = "_dcoir_v50_original_build_review_body_with_unanchored"
_REPORTER_STORAGE = "_dcoir_v50_original_progress_reporter"
_PRIOR_ATTR = "_dcoir_v50_prior_gate_context"
_STATE_ATTR = "_dcoir_v50_gate_state"


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, _CONFIG_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, _CONFIG_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v50 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.verified_finding_gate_state_review = module.hardened.bool_value(
            data, "verified_finding_gate_state_review", True
        )
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _patch_verifier(module: Any) -> None:
    original = getattr(v21, _VERIFIER_STORAGE, None)
    if original is None:
        original = getattr(v21, "verify_findings_for_publication", None)
        if callable(original):
            setattr(v21, _VERIFIER_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v50 could not locate the active publication verifier")

    def verify_findings_for_publication(
        review_module: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        verified = original(review_module, findings, gh, pr, config, reporter)
        if not bool(getattr(config, "verified_finding_gate_state_review", False)):
            return verified
        prior = gate_prior.load_prior_gate_context(review_module, gh, pr)
        setattr(review_module, _PRIOR_ATTR, prior)
        disposition = getattr(review_module, v45._DISPOSITION_ATTR, None)
        if not isinstance(disposition, dict):
            raise review_module.hardened.ReviewQualityError(
                "DCOIR v50 is missing the v45 exact-head verifier disposition"
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
        return verified

    v21.verify_findings_for_publication = verify_findings_for_publication


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


def _patch_review_body(module: Any) -> None:
    original = getattr(module, _BODY_STORAGE, None)
    if original is None:
        original = getattr(module.hardened, "build_review_body_with_unanchored", None)
        if callable(original):
            setattr(module, _BODY_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v50 could not locate the final review-body builder")

    def build_review_body_with_unanchored(
        result: dict[str, Any],
        findings: list[dict[str, Any]],
        unanchored_findings: list[dict[str, Any]],
        model_used: str,
        config: Any,
        reviewed_commit: str = "",
    ) -> str:
        body = original(
            result,
            findings,
            unanchored_findings,
            model_used,
            config,
            reviewed_commit,
        )
        if not bool(getattr(config, "verified_finding_gate_state_review", False)):
            return body
        prior = getattr(module, _PRIOR_ATTR, None)
        if not isinstance(prior, dict):
            raise module.hardened.ReviewQualityError(
                "DCOIR v50 publication is missing prior verified-finding gate context"
            )
        if not reviewed_commit:
            raise module.hardened.ReviewQualityError(
                "DCOIR v50 publication could not determine the reviewed PR head SHA"
            )
        state = gate_state.compose_state(
            [item for item in findings if isinstance(item, dict)],
            prior,
            reviewed_commit,
            str(os.environ.get("GITHUB_RUN_ID", "") or ""),
        )
        if not gate_prior.persist_gate_state(module, config, state):
            raise module.hardened.ReviewQualityError(
                "DCOIR v50 could not persist exact-head verified-finding gate state"
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

    module.hardened.build_review_body_with_unanchored = build_review_body_with_unanchored


def _patch_progress_reporter(module: Any) -> None:
    owners = [
        owner
        for owner in (getattr(module, "base", None), getattr(module, "hardened", None), module)
        if owner is not None
    ]
    original = getattr(module, _REPORTER_STORAGE, None)
    if original is None:
        original = next(
            (
                getattr(owner, "ProgressReporter", None)
                for owner in owners
                if isinstance(getattr(owner, "ProgressReporter", None), type)
            ),
            None,
        )
        if isinstance(original, type):
            setattr(module, _REPORTER_STORAGE, original)
    if not isinstance(original, type):
        raise RuntimeError("DCOIR v50 could not locate ProgressReporter")
    required = ("complete", "_record", "_body", "_update_comment")
    if any(not callable(getattr(original, name, None)) for name in required):
        raise RuntimeError("DCOIR v50 ProgressReporter contract is incomplete")

    class GateAwareProgressReporter(original):
        def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
            config = getattr(self, "config", None)
            active = getattr(module, _STATE_ATTR, None)
            if (
                not bool(getattr(config, "verified_finding_gate_state_review", False))
                or not isinstance(active, dict)
            ):
                return super().complete(model_used, findings_count, review_event)
            status = str(active.get("gate_status", "") or "")
            if status not in {"blocked", "indeterminate"}:
                return super().complete(model_used, findings_count, review_event)

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
            else:
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
            self._record("completed", message)
            self._update_comment(self._body("completed", final_lines=final_lines))
            return None

    GateAwareProgressReporter.__name__ = original.__name__
    GateAwareProgressReporter.__qualname__ = original.__qualname__
    GateAwareProgressReporter._dcoir_v50_gate_aware = True
    patched = False
    for owner in owners:
        if getattr(owner, "ProgressReporter", None) is original:
            setattr(owner, "ProgressReporter", GateAwareProgressReporter)
            patched = True
    if not patched:
        raise RuntimeError("DCOIR v50 could not install ProgressReporter overlay")


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, _APPLIED_ATTR, False):
        return
    _patch_config_loader(module)
    _patch_verifier(module)
    _patch_review_body(module)
    _patch_progress_reporter(module)
    module.DCOIR_VERIFIED_FINDING_GATE_CONTRACT = gate_state.STATE_CONTRACT
    setattr(module, _APPLIED_ATTR, True)
