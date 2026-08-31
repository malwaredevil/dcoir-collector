"""DCOIR Review v34 predicate-audit recall and verifier-evidence hardening.

Issue #456 blind run 33371074405 demonstrated two remaining generalized gaps:

* both independent semantic reviewers found neighboring polarity/scope defects
  but missed a changed positive-evidence call site whose omitted contextual
  matcher option allowed a rejected proposition to count as affirmative proof;
* normalization may legitimately select a changed blank line as a GitHub inline
  anchor, while v21 historically treated an empty line string as unreadable
  evidence and aborted the whole review before model verification.

v34 strengthens the existing adversarial prompt into a call-site/predicate audit,
preserves blank changed-line anchors using an explicit verifier-only notation,
and records compact post-normalization verifier input/output manifests when debug
is enabled. It does not raise publication budgets, bypass evidence verification,
or add any branch-write/remediation capability.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v32 as v32
import dcoir_review_required_runtime_patch_v33 as v33


VERSION = "v34"
APPLIED_MARKER = "_dcoir_review_v34_applied"
LINE_TEXT_STORAGE = "_dcoir_review_v34_original_file_line_text"
VERIFIER_STORAGE = "_dcoir_review_v34_original_verify_findings_for_publication"
BLANK_LINE_NOTATION = "[DCOIR anchor is an intentionally blank changed line]"

PREDICATE_AUDIT_BLOCK = """
Predicate and call-site audit requirements:
- For each changed boolean acceptance/rejection helper, enumerate every positive-evidence branch or disjunct before deciding the helper is sound. Audit the actual call-site arguments and omitted defaults, not only the helper definition.
- When a contextual matcher exposes polarity, quotation, rejection, scope, or boundary options, compare those options across sibling call sites. An omitted option is executable behavior and must be tested as deliberately as an explicitly enabled option.
- For every changed positive textual signal, test four semantic placements when applicable: direct affirmative use, direct negation, quotation/mention-only use, and a rejected proposition such as saying that the signal would be wrong/false/misleading. A phrase that is itself worded as a prohibition is not automatically affirmative evidence when the whole proposition containing it is rejected or merely mentioned.
- Audit each OR branch independently. A strong polarity check on one positive-evidence path does not protect a sibling path that calls the same matcher with weaker/default filtering.
- Prefer root-cause defects in executable changed code over speculative fixture/loader concerns. For fixture-only findings, report only when the supplied consuming implementation or test wiring demonstrates the mis-score or evidence loss; do not hypothesize unseen loader behavior.
- Keep the finding set Pareto-small: when several counterexamples share one root cause, report the root cause once with the strongest minimal counterexample instead of emitting neighboring variants as separate findings.
""".strip()


def _append_once(text: str, addition: str) -> str:
    base = str(text or "").strip()
    if addition in base:
        return base
    return f"{base}\n\n{addition}".strip()


def _patch_v32_prompt_blocks() -> None:
    # v32's installed prompt wrappers resolve these module globals at call time,
    # so v34 can strengthen both primary per-file and independent aggregate
    # reviews without stacking another prompt wrapper.
    v32.ADVERSARIAL_SEMANTIC_BLOCK = _append_once(v32.ADVERSARIAL_SEMANTIC_BLOCK, PREDICATE_AUDIT_BLOCK)
    v32.INDEPENDENT_CONFIRMATION_BLOCK = _append_once(v32.INDEPENDENT_CONFIRMATION_BLOCK, PREDICATE_AUDIT_BLOCK)


def _patch_blank_anchor_readback() -> None:
    original = getattr(v21, LINE_TEXT_STORAGE, None)
    if original is None:
        original = getattr(v21, "_file_line_text", None)
        if callable(original):
            setattr(v21, LINE_TEXT_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v34 could not locate v21 line-evidence reader")

    def _file_line_text(file_text: str, line_number: int) -> str:
        lines = file_text.splitlines()
        if line_number <= 0 or line_number > len(lines):
            return ""
        value = str(original(file_text, line_number))
        if value == "":
            # Preserve the distinction between an in-range blank changed line
            # and missing/out-of-range evidence. The verifier still receives
            # full head-file context and must independently support the claim.
            return BLANK_LINE_NOTATION
        return value

    v21._file_line_text = _file_line_text


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


def _patch_verifier_lifecycle_debug() -> None:
    original = getattr(v21, VERIFIER_STORAGE, None)
    if original is None:
        original = getattr(v21, "verify_findings_for_publication", None)
        if callable(original):
            setattr(v21, VERIFIER_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v34 could not locate active v21 verifier")

    def verify_findings_for_publication(
        module: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
        module.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/v34-verifier-input.json",
            {
                "schema_version": "dcoir_review_v34_verifier_input_v1",
                "head_sha": head_sha,
                "candidate_count": len(findings),
                "verification_limit": v33.verifier_candidate_limit(config),
                "repair_budget": v33.repair_synthesis_budget(config),
                "candidates": [_snapshot_finding(item) for item in findings],
            },
        )
        verified = original(module, findings, gh, pr, config, reporter)
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
        return verified

    v21.verify_findings_for_publication = verify_findings_for_publication


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_v32_prompt_blocks()
    _patch_blank_anchor_readback()
    _patch_verifier_lifecycle_debug()
    setattr(module, APPLIED_MARKER, True)
