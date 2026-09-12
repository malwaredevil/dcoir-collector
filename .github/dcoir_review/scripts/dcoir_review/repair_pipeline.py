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
_file_line = support._file_line
_strip_legacy_model_finding_provenance = support._strip_legacy_model_finding_provenance
_verifier_evidence = support._verifier_evidence
_sanitize_prompt = support._sanitize_prompt
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
    hardened = module.hardened
    path, line = _path_line(finding)
    original = _file_line(file_text, line)
    if not path or not original:
        raise hardened.ReviewQualityError("DCOIR repair stage received an unreadable anchored finding")

    author_prompt = _repair_author_prompt(module, finding, path, line, original, file_text, config)
    author_raw, author_model, author_tier = hardened.openrouter_review(
        author_prompt, REPAIR_AUTHOR_SCHEMA, config, reporter=None
    )
    author = _parse_author(author_raw, hardened)

    precheck_reason = ""
    if author["action"] == "replace_line":
        precheck_reason = _replacement_validation_reason(
            module, path, line, original, author["replacement"], file_text
        )
        if precheck_reason:
            author["action"] = "no_safe_single_line_fix"
            author["replacement"] = ""

    critic_prompt = _repair_critic_prompt(module, finding, author, path, line, original, file_text, config)
    critic_raw, critic_model, critic_tier = hardened.openrouter_review(
        critic_prompt, REPAIR_CRITIC_SCHEMA, _independent_config(config), reporter=None
    )
    accepted, critic_confidence, critic_reason = _parse_critic(critic_raw, hardened)

    item = dict(finding)
    fallback_title, fallback_body = _fallback_display(item, path, line)
    if accepted:
        item["title"] = author["display_title"][:160]
        item["body"] = author["display_body"][:1800]
    else:
        item["title"] = fallback_title[:160]
        item["body"] = fallback_body[:1800]

    item["suggested_replacement"] = ""
    outcome = "no-safe-single-line-fix"
    final_reason = critic_reason or precheck_reason or author["rationale"]
    if accepted and author["action"] == "replace_line":
        final_check = _replacement_validation_reason(
            module, path, line, original, author["replacement"], file_text
        )
        if not final_check:
            item["suggested_replacement"] = author["replacement"]
            outcome = "native-suggestion"
        else:
            final_reason = final_check

    if not item["suggested_replacement"]:
        item["fix_guidance"] = {
            "language": Path(path).suffix.lstrip(".") or "text",
            "notes": (
                "DCOIR Review verified the finding but did not expose a one-click GitHub suggestion because "
                + (final_reason or "the repair stage could not prove a safe exact one-line replacement")
                + "."
            )[:1400],
        }
    else:
        item.pop("fix_guidance", None)

    validation = author["validation"]
    if validation:
        item["validation"] = validation

    item[REPAIR_MARKER] = {
        "version": VERSION,
        "outcome": outcome,
        "path": path,
        "line": line,
        "author_model": author_model,
        "author_service_tier": author_tier,
        "author_confidence": author["confidence"],
        "critic_model": critic_model,
        "critic_service_tier": critic_tier,
        "critic_confidence": critic_confidence,
        "critic_accepted": accepted,
        "reason": final_reason,
    }

    hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair/{ordinal:02d}.json",
        {
            "path": path,
            "line": line,
            "author": author,
            "author_model": author_model,
            "critic": {
                "accepted": accepted,
                "confidence": critic_confidence,
                "reason": critic_reason,
                "model": critic_model,
            },
            "precheck_reason": precheck_reason,
            "outcome": outcome,
        },
    )
    return item


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
    base = module.base
    marker = finding.get(REPAIR_MARKER) if isinstance(finding.get(REPAIR_MARKER), dict) else {}
    title = base.markdown_emphasis_safe_text(
        base.sanitize_github_output(str(finding.get("title", "Finding") or "Finding").strip(), config)
    )
    severity = base.markdown_emphasis_safe_text(str(finding.get("severity", "medium") or "medium").upper())
    body = base.strip_model_validation_section(
        base.sanitize_github_output(str(finding.get("body", "") or "").strip(), config)
    )
    parts = [f"**{severity}: {title}**", "", body]

    suggestion = str(finding.get("suggested_replacement", "") or "")
    if marker.get("outcome") == "native-suggestion" and suggestion:
        path, line = _path_line(finding)
        if (
            path
            and line > 0
            and not any(token in suggestion for token in ("\n", "\r", "```", "~~~"))
            and len(suggestion) <= 1000
            and base.is_safe_suggestion(suggestion)
        ):
            safe = base.sanitize_github_output(suggestion, config, neutralize_mentions=False)
            parts.extend(["", "**Suggested change:**", "", "```suggestion", safe, "```"])

    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    notes = base.fix_guidance_value_text(guidance.get("notes", ""), config) if guidance else ""
    if notes:
        parts.extend(["", "**Repair status:**", "", notes])

    validation = base.sanitize_github_output(base.validation_text_for_finding(finding), config)
    if validation:
        parts.extend(["", "**Validation expected after fix:**"])
        base.append_language_fence(parts, "bash", validation)
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME} · verified repair pipeline</sub>"])
    return base.github_safe_body("\n".join(parts), limit=12000)


def apply_pareto_context_module(module: Any) -> None:
    def synthesize_fixes_for_findings(
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        return synthesize_verified_repairs(module, findings, gh, pr, schema, config, reporter)

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
