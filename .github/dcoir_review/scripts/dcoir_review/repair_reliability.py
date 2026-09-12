"""Stable operational reliability for the DCOIR verified-repair pipeline.

The canonical repair pipeline uses this owner for the verify -> repair-author -> repair-critic ->
deterministic-validation execution path. It preserves the proven reliability contract:

- persist the repair-author result before any later stage can fail;
- use verifier-approved finding wording when the repair author omits display
  title/body rather than failing an otherwise useful exact repair;
- do not spend a critic call when the author declines or deterministic precheck
  already rejects the proposed one-line replacement;
- persist author/critic call and parse failures independently;
- persist bounded diagnostics on every fail-closed repair path;
- keep native suggestion eligibility exactly as strict as repair.

No branch writes are introduced. The historical v28 marker and debug paths are retained
for compatibility while the production patch module itself is retired.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from dcoir_review import repair_support as support


# Compatibility provenance value retained for existing review/debug consumers.
VERSION = "v28"

def _repair_contract() -> Any:
    """Return the already-loaded pipeline compatibility contract without importing it.

    The pipeline lazily imports this reliability owner, so a static reverse import
    would recreate the cycle that GHAS correctly identified.  Runtime lookups keep
    later compatibility overlays (notably v30) visible without a module import cycle.
    """

    contract = sys.modules.get("dcoir_review.repair_pipeline")
    if contract is None:
        raise RuntimeError("DCOIR repair reliability requires the canonical repair pipeline contract")
    return contract


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

    fallback_title, fallback_body = support._fallback_display(finding, path, line)
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
    if action == "replace_line" and confidence < float(_repair_contract().AUTHOR_MIN_CONFIDENCE):
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
    repair = _repair_contract()
    item = dict(finding)
    fallback_title, fallback_body = support._fallback_display(item, path, line)
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
    item[repair.REPAIR_MARKER] = {
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


def _stage_failure(
    module: Any,
    config: Any,
    ordinal: int,
    finding: dict[str, Any],
    path: str,
    line: int,
    stage: str,
    exc: Exception,
    *,
    author: dict[str, Any] | None = None,
    author_model: str = "",
    author_tier: str = "",
) -> dict[str, Any]:
    reason = f"{stage} failed closed: {type(exc).__name__}: {str(exc)[:500]}"
    _debug(
        module,
        config,
        f"responses/repair-v28/{ordinal:02d}-{stage}-failure.json",
        {
            "path": path,
            "line": line,
            "stage": stage,
            "error_type": type(exc).__name__,
            "error": str(exc)[:1200],
        },
    )
    return _declined_item(
        finding,
        path,
        line,
        reason,
        author=author,
        author_model=author_model,
        author_tier=author_tier,
        outcome=f"{stage}-stage-failed-closed",
    )


def _persist_final(module: Any, config: Any, ordinal: int, item: dict[str, Any]) -> None:
    repair = _repair_contract()
    marker = item.get(repair.REPAIR_MARKER) if isinstance(item.get(repair.REPAIR_MARKER), dict) else {}
    _debug(module, config, f"responses/repair-v28/{ordinal:02d}-final.json", dict(marker))


def build_repair_for_finding(
    module: Any,
    ordinal: int,
    finding: dict[str, Any],
    file_text: str,
    config: Any,
) -> dict[str, Any]:
    repair = _repair_contract()
    hardened = module.hardened
    path, line = support._path_line(finding)
    original = repair._file_line(file_text, line)
    if not path or not original:
        raise hardened.ReviewQualityError("DCOIR repair stage received an unreadable anchored finding")

    author_prompt = repair._repair_author_prompt(module, finding, path, line, original, file_text, config)
    try:
        author_raw, author_model, author_tier = hardened.openrouter_review(
            author_prompt, repair.REPAIR_AUTHOR_SCHEMA, config, reporter=None
        )
    except Exception as exc:
        item = _stage_failure(module, config, ordinal, finding, path, line, "author-call", exc)
        _persist_final(module, config, ordinal, item)
        return item

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
    try:
        author = _author_result(author_raw, finding, path, line, hardened)
    except Exception as exc:
        item = _stage_failure(module, config, ordinal, finding, path, line, "author-parse", exc)
        _persist_final(module, config, ordinal, item)
        return item

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
        _persist_final(module, config, ordinal, item)
        return item

    precheck_reason = repair._replacement_validation_reason(
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
        _persist_final(module, config, ordinal, item)
        return item

    critic_prompt = repair._repair_critic_prompt(module, finding, author, path, line, original, file_text, config)
    critic_config = repair._independent_config(config)
    try:
        critic_raw, critic_model, critic_tier = hardened.openrouter_review(
            critic_prompt, repair.REPAIR_CRITIC_SCHEMA, critic_config, reporter=None
        )
    except Exception as exc:
        item = _stage_failure(
            module,
            config,
            ordinal,
            finding,
            path,
            line,
            "critic-call",
            exc,
            author=author,
            author_model=author_model,
            author_tier=author_tier,
        )
        _persist_final(module, config, ordinal, item)
        return item

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
    try:
        accepted, critic_confidence, critic_reason = repair._parse_critic(critic_raw, hardened)
    except Exception as exc:
        item = _stage_failure(
            module,
            config,
            ordinal,
            finding,
            path,
            line,
            "critic-parse",
            exc,
            author=author,
            author_model=author_model,
            author_tier=author_tier,
        )
        _persist_final(module, config, ordinal, item)
        return item

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
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": critic_confidence,
            }
        )
        _persist_final(module, config, ordinal, item)
        return item

    final_reason = repair._replacement_validation_reason(
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
        item[repair.REPAIR_MARKER].update(
            {
                "critic_model": critic_model,
                "critic_service_tier": critic_tier,
                "critic_confidence": critic_confidence,
                "critic_accepted": True,
            }
        )
        _persist_final(module, config, ordinal, item)
        return item

    item = dict(finding)
    item["title"] = author["display_title"][:160]
    item["body"] = author["display_body"][:1800]
    item["suggested_replacement"] = author["replacement"]
    item.pop("fix_guidance", None)
    if author["validation"]:
        item["validation"] = author["validation"]
    item[repair.REPAIR_MARKER] = {
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
    _persist_final(module, config, ordinal, item)
    return item
