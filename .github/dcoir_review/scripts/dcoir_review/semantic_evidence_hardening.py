"""Semantic predicate-audit and verifier-evidence hardening for DCOIR Review.

Issue #456 blind run 33371074405 demonstrated two remaining generalized gaps:

* both independent semantic reviewers found neighboring polarity/scope defects
  but missed a changed positive-evidence call site whose omitted contextual
  matcher option allowed a rejected proposition to count as affirmative proof;
* normalization may legitimately select a changed blank line as a GitHub inline
  anchor, while v21 historically treated an empty line string as unreadable
  evidence and aborted the whole review before model verification.

This owner strengthens the existing adversarial prompt into a call-site/predicate audit,
preserves blank changed-line anchors using an explicit verifier-only notation,
and records compact post-normalization verifier input/output manifests when debug
is enabled. It does not raise publication budgets, bypass evidence verification,
or add any branch-write/remediation capability.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import adversarial_prompt_policy as prompt_policy
from dcoir_review import finding_verifier_contract as verifier_contract
from dcoir_review import repair as repair_policy


APPLIED_MARKER = "_dcoir_review_semantic_evidence_hardening_applied"
BLANK_LINE_NOTATION = verifier_contract.BLANK_LINE_NOTATION

PREDICATE_AUDIT_BLOCK = prompt_policy.PREDICATE_AUDIT_BLOCK


def _snapshot_finding(finding: dict[str, Any]) -> dict[str, Any]:
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    try:
        confidence = float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "path": str(finding.get("path", "") or "").strip(),
        "line": line,
        "severity": str(finding.get("severity", "") or "").strip(),
        "confidence": confidence,
        "title": str(finding.get("title", "") or "").strip(),
        "body": str(finding.get("body", "") or "").strip(),
        "validation": str(finding.get("validation", "") or "").strip(),
    }


def record_verifier_input(
    module: Any,
    findings: list[dict[str, Any]],
    pr: dict[str, Any],
    config: Any,
) -> None:
    head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/v34-verifier-input.json",
        {
            "schema_version": "dcoir_review_v34_verifier_input_v1",
            "head_sha": head_sha,
            "candidate_count": len(findings),
            "verification_limit": verifier_contract.verifier_candidate_limit(config),
            "repair_budget": repair_policy.repair_synthesis_budget(config),
            "candidates": [_snapshot_finding(item) for item in findings],
        },
    )


def record_verifier_output(
    module: Any,
    verified: list[dict[str, Any]],
    pr: dict[str, Any],
    config: Any,
) -> None:
    head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
    module.hardened.write_debug_json_artifact_safely(
        config,
        "responses/v34-verifier-output.json",
        {
            "schema_version": "dcoir_review_v34_verifier_output_v1",
            "head_sha": head_sha,
            "verified_count": len(verified),
            "verified": [_snapshot_finding(item) for item in verified],
        },
    )


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    setattr(module, APPLIED_MARKER, True)
