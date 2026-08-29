"""DCOIR Review v28 staged repair-pipeline reliability overlay.

v25 established the desired verify -> repair-author -> repair-critic ->
deterministic-validation architecture. v28 makes that pipeline operationally
robust and observable:

- persist the repair-author result before any later stage can fail;
- use verifier-approved finding wording when the repair author omits display
  title/body rather than failing an otherwise useful exact repair;
- do not spend a critic call when the author declines or deterministic precheck
  already rejects the proposed one-line replacement;
- persist critic results independently;
- persist bounded failure diagnostics on every fail-closed path;
- keep native suggestion eligibility exactly as strict as v25.

No branch writes are introduced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v25 as v25


VERSION = "v28"


def _author_result(result: Any, finding: dict[str, Any], path: str, line: int, hardened: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise hardened.ReviewQualityError("DCOIR repair author returned a non-object result")
    action = str(result.get("action", "") or "").strip()
    if action not in {"replace_line", "no_safe_single_line_fix"}:
        raise hardened.ReviewQualityError("DCOIR repair author returned an invalid action")
    try:
        confidence = float(result.get("confidence", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise hardened.ReviewQualityError("DCOIR repair author returned invalid confidence") from exc

    fallback_title, fallback_body = v25._fallback_display(finding, path, line)
    display_title = str(result.get("display_title", "") or "").strip()
    display_body = str(result.get("display_body", "") or "").strip()
    if not display_title:
        display_title = str(finding.get("title", "") or fallback_title).strip() or fallback_title
    if not display_body:
        display_body = str(finding.get("body", "") or fallback_body).strip() or fallback_body

    parsed = {
        "action": action,
        "replacement": str(result.get("replacement", "") or ""),
        "confidence": confidence,
        "display_title": display_title[:160],
        "display_body": display_body[:1800],
        "rationale": str(result.get("rationale", "") or "").strip(),
        "validation": str(result.get("validation", "") or "").strip(),
    }
    if action == "replace_line" and confidence < v25.AUTHOR_MIN_CONFIDENCE:
        parsed["action"] = "no_safe_single_line_fix"
        parsed["replacement"] = ""
        parsed["rationale"] = parsed["rationale"] or "Repair author confidence was below the suggestion threshold."
    if parsed["action"] == "no_safe_single_line_fix":
        parsed["replacement"] = ""
    return parsed


def _debug(module: Any, config: Any, path: str, payload: dict[str, Any]) -> None:
    module.hardened.write_debug_json_artifact_safely(config, path, payload)


def _declined_item(
    finding: dict[str, Any],
    path: str,
    line: int,
    reason: str,
    *,
    author: dict[str, Any] | None = None,
    author_model: str = "",
    author_tier: str = "",
    outcome: str = "no-safe-single-line-fix",
) -> dict[str, Any]:
    item = dict(finding)
    fallback_title, fallback_body = v25._fallback_display(item, path, line)
    if author:
        item["title"] = str(author.get("display_title", "") or fallback_title)[:160]
        item["body"] = str(author.get("display_body", "") or fallback_body)[:1800]
    else:
        item["title"] = fallback_title[:160]
        item["body"] = fallback_body[:1800]
    item["suggested_replacement"] = ""
    item["fix_guidance"] = {
        "language": Path(path).suffix.lstrip(".") or "text",
        "notes": (
            "DCOIR Review verified the finding but did not expose a one-click GitHub suggestion because "
            + (reason or "the repair pipeline could not prove a safe exact one-line replacement")
            + "."
        )[:1400],
    }
    item[v25.REPAIR_MARKER] = {
        "version": VERSION,
        "outcome": outcome,
        "path": path,
        "line": line,
        "author_model": author_model,
        "author_service_tier": author_tier,
        "author_confidence": float(author.get("confidence", 0) or 0) if author else 0.0,
        "critic_accepted": False,
        "reason": reason[:600],
    }
    return item


def build_repair_for_finding(
    module: Any,
    ordinal: int,
    finding: dict[str, Any],
    file_text: str,
    config: Any,
) -> dict[str, Any]:
    hardened = module.hardened
    path, line = v25._path_line(finding)
    original = v25._file_line(file_text, line)
    if not path or not original:
        raise hardened.ReviewQualityError("DCOIR repair stage received an unreadable anchored finding")

    author_prompt = v25._repair_author_prompt(module, finding, path, line, original, file_text, config)
    author_raw, author_model, author_tier = hardened.openrouter_review(
        author_prompt, v25.REPAIR_AUTHOR_SCHEMA, config, reporter=None
    )
    _debug(
        module,
        config,
        f"responses/repair-v28/{ordinal:02d}-author.json",
        {
            "path": path,
            "line": line,
            "model": author_model,
            "service_tier": author_tier,
            "result": author_raw if isinstance(author_raw, dict) else {"shape": type(author_raw).__name__},
        },
    )
    author = _author_result(author_raw, finding, path, line, hardened)

    if author["action"] != "replace_line":
        reason = author["rationale"] or "Repair author did not support a safe exact one-line replacement."
        item = _declined_item(
            finding,
            path,
            line,
            reason,
            author=author,
            author_model=author_model,
            author_tier=author_tier,
            outcome="author-declined",
        )
        _debug(module, config, f"responses/repair-v28/{ordinal:02d}-final.json", item[v25.REPAIR_MARKER])
        return item

    precheck_reason = v25._replacement_validation_reason(
        module, path, line, original, author["replacement"], file_text
    )
    if precheck_reason:
        item = _declined_item(
            finding,
            path,
            line,
            precheck_reason,
            author=author,
            author_model=author_model,
            author_tier=author_tier,
            outcome="deterministic-precheck-declined",
        )
        _debug(
            module,
            config,
            f"responses/repair-v28/{ordinal:02d}-precheck.json",
            {"path": path, "line": line, "reason": precheck_reason, "replacement": author["replacement"]},
        )
        return item

    critic_prompt = v25._repair_critic_prompt(module, finding, author, path, line, original, file_text, config)
    critic_raw, critic_model, critic_tier = hardened.openrouter_review(
        critic_prompt, v25.REPAIR_CRITIC_SCHEMA, v25._independent_config(config), reporter=None
    )
    _debug(
        module,
        config,
        f"responses/repair-v28/{ordinal:02d}-critic.json",
        {
            "path": path,
            "line": line,
            "model": critic_model,
            "service_tier": critic_tier,
            "result": critic_raw if isinstance(critic_raw, dict) else {"shape": type(critic_raw).__name__},
        },
    )
    accepted, critic_confidence, critic_reason = v25._parse_critic(critic_raw, hardened)
    if not accepted:
        item = _declined_item(
            finding,
            path,
            line,
            critic_reason or "Independent repair critic did not support one-click application.",
            author=author,
            author_model=author_model,
            author_tier=author_tier,
            outcome="critic-declined",
        )
        item[v25.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": critic_confidence,
            }
        )
        return item

    final_reason = v25._replacement_validation_reason(
        module, path, line, original, author["replacement"], file_text
    )
    if final_reason:
        item = _declined_item(
            finding,
            path,
            line,
            final_reason,
            author=author,
            author_model=author_model,
            author_tier=author_tier,
            outcome="deterministic-final-declined",
        )
        item[v25.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": critic_confidence,
                "critic_accepted": True,
            }
        )
        return item

    item = dict(finding)
    item["title"] = author["display_title"][:160]
    item["body"] = author["display_body"][:1800]
    item["suggested_replacement"] = author["replacement"]
    item.pop("fix_guidance", None)
    if author["validation"]:
        item["validation"] = author["validation"]
    item[v25.REPAIR_MARKER] = {
        "version": VERSION,
        "outcome": "native-suggestion",
        "path": path,
        "line": line,
        "author_model": author_model,
        "author_service_tier": author_tier,
        "author_confidence": author["confidence"],
        "critic_model": critic_model,
        "critic_service_tier": critic_tier,
        "critic_confidence": critic_confidence,
        "critic_accepted": True,
        "reason": critic_reason,
    }
    _debug(
        module,
        config,
        f"responses/repair-v28/{ordinal:02d}-final.json",
        {
            "path": path,
            "line": line,
            "outcome": "native-suggestion",
            "replacement": author["replacement"],
            "author_model": author_model,
            "critic_model": critic_model,
            "critic_confidence": critic_confidence,
        },
    )
    return item


def apply_pareto_context_module(module: Any) -> None:
    # v25.synthesize_verified_repairs resolves this global dynamically, so
    # replacing the helper upgrades the active production pipeline without
    # re-wrapping the verifier or renderer.
    v25._build_repair_for_finding = lambda mod, ordinal, finding, file_text, config: build_repair_for_finding(
        mod, ordinal, finding, file_text, config
    )

    # Add bounded failure diagnostics around the v25 synthesize boundary.
    storage = "_dcoir_required_v28_original_synthesize_verified_repairs"
    original = getattr(v25, storage, None)
    if original is None:
        original = getattr(v25, "synthesize_verified_repairs", None)
        if callable(original):
            setattr(v25, storage, original)
    if not callable(original):
        return

    def synthesize_verified_repairs(
        mod: Any,
        findings: list[dict[str, Any]],
        gh: Any,
        pr: dict[str, Any],
        schema: dict[str, Any],
        config: Any,
        reporter: Any,
    ) -> list[dict[str, Any]]:
        try:
            return original(mod, findings, gh, pr, schema, config, reporter)
        except Exception as exc:
            _debug(
                mod,
                config,
                "metadata/repair-v28-terminal-failure.json",
                {
                    "schema_version": "dcoir_review_repair_v28_failure_v1",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1200],
                },
            )
            raise

    v25.synthesize_verified_repairs = synthesize_verified_repairs
