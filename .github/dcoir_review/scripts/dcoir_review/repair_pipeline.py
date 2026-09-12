"""Canonical verified-repair pipeline for DCOIR Review.

This permanent owner replaces the historical v25 runtime patch while preserving
its fail-closed repair contract. Later historical overlays still adjust a small
set of hooks here until their responsibilities are retired into stable owners.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dcoir_review import repair_support as support
import dcoir_review_required_runtime_patch_v21 as v21

VERSION = "repair"
REPAIR_MARKER = "_dcoir_repair"
AUTHOR_MIN_CONFIDENCE = 0.90
CRITIC_MIN_CONFIDENCE = 0.90
MAX_REPAIR_CANDIDATES = 6

REPAIR_AUTHOR_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Verified Finding Repair Author",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "action",
        "replacement",
        "confidence",
        "display_title",
        "display_body",
        "rationale",
        "validation",
    ],
    "properties": {
        "action": {"type": "string", "enum": ["replace_line", "no_safe_single_line_fix"]},
        "replacement": {"type": "string", "maxLength": 1200},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "display_title": {"type": "string", "maxLength": 160},
        "display_body": {"type": "string", "maxLength": 1800},
        "rationale": {"type": "string", "maxLength": 1800},
        "validation": {"type": "string", "maxLength": 1800},
    },
}

REPAIR_CRITIC_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Verified Finding Repair Critic",
    "type": "object",
    "additionalProperties": False,
    "required": ["accepted", "confidence", "reason"],
    "properties": {
        "accepted": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 1800},
    },
}



# Stable helper exports intentionally remain module globals because later
# historical overlays still replace a bounded subset during staged retirement.
_path_line = support._path_line
_unused_file_line = support._file_line
_strip_legacy_model_finding_provenance = support._strip_legacy_model_finding_provenance

def _verifier_evidence(finding: dict[str, Any]) -> str:
    return support._verifier_evidence(finding)


def _sanitize_prompt(module: Any, text: str, config: Any) -> str:
    return support._sanitize_prompt(module, text, config)


_repair_author_prompt = support._repair_author_prompt
_repair_critic_prompt = support._repair_critic_prompt
_independent_config = support._independent_config
_parse_author = support._parse_author
_parse_critic = support._parse_critic
_replacement_validation_reason = support._replacement_validation_reason
_fallback_display = support._fallback_display

def _build_repair_for_finding(
    module: Any,
    ordinal: int,
    finding: dict[str, Any],
    file_text: str,
    config: Any,
) -> dict[str, Any]:
    # Lazy import avoids a module cycle while keeping this compatibility hook
    # available for later staged overlays such as v33.
    from dcoir_review import repair_reliability

    return repair_reliability.build_repair_for_finding(module, ordinal, finding, file_text, config)


def synthesize_verified_repairs(
    module: Any,
    findings: list[dict[str, Any]],
    gh: Any,
    pr: dict[str, Any],
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
) -> list[dict[str, Any]]:
    del schema
    verified = v21.verify_findings_for_publication(module, findings, gh, pr, config, reporter)
    if not verified:
        reporter.update("repair", "no verifier-supported findings required repair")
        return []
    if len(verified) > MAX_REPAIR_CANDIDATES:
        raise module.hardened.ReviewQualityError(
            f"DCOIR repair candidate count {len(verified)} exceeds bounded limit {MAX_REPAIR_CANDIDATES}"
        )

    head_sha = str(pr.get("head", {}).get("sha", "") or "").strip()
    if not head_sha:
        raise module.hardened.ReviewQualityError("DCOIR repair stage could not determine the PR head SHA")

    reporter.update("repair", f"authoring and independently critiquing {len(verified)} verified repair(s)")
    file_cache: dict[str, str] = {}
    repaired: list[dict[str, Any]] = []
    native = 0
    declined = 0
    for ordinal, raw in enumerate(verified, start=1):
        finding = _strip_legacy_model_finding_provenance(raw)
        path, _line = _path_line(finding)
        if path not in file_cache:
            file_cache[path] = module.fetch_pr_file_text(gh, path, head_sha)
        try:
            item = _build_repair_for_finding(module, ordinal, finding, file_cache[path], config)
        except Exception as exc:
            # Finding publication remains useful even when repair generation is
            # unavailable; applyable suggestions fail closed, not findings.
            item = finding
            path, line = _path_line(item)
            title, body = _fallback_display(item, path, line)
            item["title"] = title
            item["body"] = body
            item["suggested_replacement"] = ""
            item["fix_guidance"] = {
                "language": Path(path).suffix.lstrip(".") or "text",
                "notes": "Verified finding; one-click repair was withheld because the repair pipeline failed closed.",
            }
            item[REPAIR_MARKER] = {
                "version": VERSION,
                "outcome": "repair-stage-failed-closed",
                "path": path,
                "line": line,
                "reason": str(exc)[:600],
            }
        if item.get(REPAIR_MARKER, {}).get("outcome") == "native-suggestion":
            native += 1
        else:
            declined += 1
        repaired.append(item)

    reporter.update(
        "repair",
        f"verified={len(repaired)}; native_suggestions={native}; fallback_or_declined={declined}",
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/repair-metrics.json",
        {
            "schema_version": "dcoir_review_repair_metrics_v1",
            "head_sha": head_sha,
            "verified_findings": len(repaired),
            "native_suggestions": native,
            "fallback_or_declined": declined,
        },
    )
    return repaired


def _render_repair(module: Any, finding: dict[str, Any], config: Any) -> str:
    from dcoir_review import repair_render

    return repair_render.render_repair(module, finding, config)


def apply_pareto_context_module(module: Any) -> None:
    # Replace—not wrap—the accumulated legacy post-verifier synthesis stack.
    # v21 remains the finding publication verifier and is called explicitly by
    # synthesize_verified_repairs above.
    def synthesize_fixes_for_findings(
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        try:
            return synthesize_verified_repairs(module, findings, gh, pr, schema, config, reporter)
        except Exception as exc:
            # Preserve the terminal reliability diagnostic formerly installed by
            # historical v28 without wrapping this permanent owner at runtime.
            module.hardened.write_debug_json_artifact_safely(
                config,
                "metadata/repair-v28-terminal-failure.json",
                {
                    "schema_version": "dcoir_review_repair_v28_failure_v1",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1200],
                },
            )
            raise

    module.synthesize_fixes_for_findings = synthesize_fixes_for_findings

    base = getattr(module, "base", None)
    if base is None:
        return
    storage = "_dcoir_required_v25_original_build_inline_comment"
    original = getattr(base, storage, None)
    if original is None:
        original = getattr(base, "build_inline_comment", None)
        if callable(original):
            setattr(base, storage, original)

    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        if isinstance(finding.get(REPAIR_MARKER), dict):
            return _render_repair(module, finding, config)
        if callable(original):
            return original(finding, model_used, config)
        return ""

    base.build_inline_comment = build_inline_comment
