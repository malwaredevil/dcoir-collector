"""DCOIR Review v33 candidate-verification and repair-budget separation.

Issue #456 exposed a second-order integration problem after v32 added an
independent adversarial reviewer.  The merged review can legitimately contain
more raw actionable candidates than the number of findings for which the
reviewer is configured to synthesize one-click repairs.  Treating those two
budgets as one causes a fail-closed review before the evidence verifier can
suppress unsupported candidates.

v33 separates the stages while keeping each bounded:

* ordinary model candidates may enter v21 verification up to the already
  normalized inline-review ceiling, with an absolute 12-candidate hard cap;
* every verifier-supported finding remains publishable;
* repair author/critic work is attempted only for the configured
  ``fix_synthesis_max_findings`` budget;
* verifier-supported findings beyond that repair budget remain visible but
  receive no one-click suggestion.

This module does not weaken the v21 evidence requirement, does not increase the
GitHub inline-publication ceiling, and adds no autonomous remediation or branch
write capability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v25 as v25


VERSION = "v33"
APPLIED_MARKER = "_dcoir_review_v33_applied"
VERIFIER_CANDIDATE_HARD_CAP = 12
VERIFIER_STORAGE = "_dcoir_review_v33_original_verify_findings_for_publication"
REPAIR_STORAGE = "_dcoir_review_v33_original_synthesize_verified_repairs"
DEFERRED_OUTCOME = "verified-repair-budget-deferred"


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(0, parsed)


def verifier_candidate_limit(config: Any) -> int:
    """Bound pre-publication evidence verification independently of repair cost."""

    inline_limit = _positive_int(getattr(config, "max_inline_comments", VERIFIER_CANDIDATE_HARD_CAP), VERIFIER_CANDIDATE_HARD_CAP)
    return max(1, min(inline_limit, VERIFIER_CANDIDATE_HARD_CAP))


def repair_synthesis_budget(config: Any) -> int:
    """Return how many verified findings may enter one-click repair synthesis."""

    if not bool(getattr(config, "fix_synthesis_enabled", True)):
        return 0
    inline_limit = _positive_int(getattr(config, "max_inline_comments", VERIFIER_CANDIDATE_HARD_CAP), VERIFIER_CANDIDATE_HARD_CAP)
    configured = _positive_int(getattr(config, "fix_synthesis_max_findings", 0), 0)
    return min(configured, inline_limit)


def _patch_verifier_candidate_limit() -> None:
    original = getattr(v21, VERIFIER_STORAGE, None)
    if original is None:
        original = getattr(v21, "verify_findings_for_publication", None)
        if callable(original):
            setattr(v21, VERIFIER_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v33 could not locate v21 finding verifier")

    def verify_findings_for_publication(
        module: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        # Normalization already bounds actionable inline candidates.  Temporarily
        # give v21 the corresponding verification ceiling, then restore the
        # historical constant so unrelated compatibility tests remain stable.
        previous = v21.VERIFIER_MAX_MODEL_FINDINGS
        v21.VERIFIER_MAX_MODEL_FINDINGS = verifier_candidate_limit(config)
        try:
            verifier = getattr(v21, VERIFIER_STORAGE)
            return verifier(module, findings, gh, pr, config, reporter)
        finally:
            v21.VERIFIER_MAX_MODEL_FINDINGS = previous

    v21.verify_findings_for_publication = verify_findings_for_publication


def _deferred_verified_finding(raw: dict[str, Any], ordinal: int) -> dict[str, Any]:
    finding = v25._strip_legacy_model_finding_provenance(raw)
    path, line = v25._path_line(finding)
    finding["suggested_replacement"] = ""
    finding["fix_guidance"] = {
        "language": Path(path).suffix.lstrip(".") or "text",
        "notes": (
            "Verifier-supported finding; one-click repair synthesis was not attempted "
            "because the configured repair budget was exhausted."
        ),
    }
    finding[v25.REPAIR_MARKER] = {
        "version": VERSION,
        "outcome": DEFERRED_OUTCOME,
        "path": path,
        "line": line,
        "ordinal": ordinal,
        "reason": "configured fix_synthesis_max_findings budget exhausted",
    }
    return finding


def _patch_verified_repair_budget(module: Any) -> None:
    original = getattr(v25, REPAIR_STORAGE, None)
    if original is None:
        original = getattr(v25, "synthesize_verified_repairs", None)
        if callable(original):
            setattr(v25, REPAIR_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v33 could not locate v25 verified repair pipeline")

    def synthesize_verified_repairs(
        mod: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        del schema
        verified = v21.verify_findings_for_publication(mod, findings, gh, pr, config, reporter)
        if not verified:
            reporter.update("repair-v33", "no verifier-supported findings required repair")
            return []

        head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
        if not head_sha:
            raise mod.hardened.ReviewQualityError("DCOIR v33 repair stage could not determine the PR head SHA")

        repair_budget = repair_synthesis_budget(config)
        repair_count = min(len(verified), repair_budget)
        deferred_count = len(verified) - repair_count
        reporter.update(
            "repair-v33",
            (
                f"verified={len(verified)}; repair_budget={repair_budget}; "
                f"repair_attempts={repair_count}; verified_without_repair={deferred_count}"
            ),
        )

        file_cache: dict[str, str] = {}
        repaired: list[dict[str, Any]] = []
        native = 0
        declined = 0

        for ordinal, raw in enumerate(verified, start=1):
            if ordinal > repair_count:
                repaired.append(_deferred_verified_finding(raw, ordinal))
                continue

            finding = v25._strip_legacy_model_finding_provenance(raw)
            path, _line = v25._path_line(finding)
            if path not in file_cache:
                file_cache[path] = mod.fetch_pr_file_text(gh, path, head_sha)
            try:
                item = v25._build_repair_for_finding(mod, ordinal, finding, file_cache[path], config)
            except Exception as exc:
                # Match v25's fail-closed repair behavior: preserve the verified
                # finding while withholding a suggestion when repair generation
                # itself fails.
                item = finding
                path, line = v25._path_line(item)
                title, body = v25._fallback_display(item, path, line)
                item["title"] = title
                item["body"] = body
                item["suggested_replacement"] = ""
                item["fix_guidance"] = {
                    "language": Path(path).suffix.lstrip(".") or "text",
                    "notes": "Verified finding; one-click repair was withheld because the repair pipeline failed closed.",
                }
                item[v25.REPAIR_MARKER] = {
                    "version": VERSION,
                    "outcome": "repair-stage-failed-closed",
                    "path": path,
                    "line": line,
                    "reason": str(exc)[:600],
                }

            if item.get(v25.REPAIR_MARKER, {}).get("outcome") == "native-suggestion":
                native += 1
            else:
                declined += 1
            repaired.append(item)

        reporter.update(
            "repair-v33",
            (
                f"published_verified={len(repaired)}; native_suggestions={native}; "
                f"fallback_or_declined={declined}; repair_budget_deferred={deferred_count}"
            ),
        )
        mod.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/repair-v33-metrics.json",
            {
                "schema_version": "dcoir_review_repair_v33_metrics_v1",
                "head_sha": head_sha,
                "verified_findings": len(repaired),
                "repair_budget": repair_budget,
                "repair_attempts": repair_count,
                "repair_budget_deferred": deferred_count,
                "native_suggestions": native,
                "fallback_or_declined": declined,
            },
        )
        return repaired

    # v25's module-level synthesize_fixes_for_findings resolves this symbol at
    # call time.  v30's later publication-suppression wrapper therefore still
    # surrounds this replacement and can suppress explicit defect-absent repair
    # attestations exactly as before.
    v25.synthesize_verified_repairs = synthesize_verified_repairs


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_verifier_candidate_limit()
    _patch_verified_repair_budget(module)
    setattr(module, APPLIED_MARKER, True)
