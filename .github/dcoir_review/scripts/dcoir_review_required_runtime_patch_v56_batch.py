"""Bounded identity-safe batch critic helpers for DCOIR Review v56."""

from __future__ import annotations

import json
from typing import Any

import dcoir_review_required_runtime_patch_v25 as v25
import dcoir_review_required_runtime_patch_v36 as v36
import dcoir_review_required_runtime_patch_v56_repair as repair

MAX_BATCH_ITEMS = 8
MAX_BATCH_PROMPT_CHARS = 120000
STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"

BATCH_CRITIC_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Verified Repair Set Batch Critic",
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "maxItems": MAX_BATCH_ITEMS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["critic_item_id", "accepted", "confidence", "reason"],
                "properties": {
                    "critic_item_id": {"type": "string", "minLength": 1, "maxLength": 80},
                    "accepted": {"type": "boolean"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string", "maxLength": 2200},
                },
            },
        }
    },
}


def batch_prompt(module: Any, pending: list[dict[str, Any]], file_cache: dict[str, str], config: Any) -> str:
    """Build a batch without reducing any item's historical critic context cap."""

    sections: list[str] = []
    for item in pending:
        finding = item["finding"]
        author = item["author"]
        payload = {
            "critic_item_id": item["critic_item_id"],
            "verified_finding": {
                "path": finding.get("path", ""),
                "line": finding.get("line", 0),
                "title": finding.get("title", ""),
                "verifier_evidence": v25._verifier_evidence(finding),
            },
            "repair_set": author,
        }
        context = v36._critic_context(module, file_cache, author["edits"], config)
        encoded = module.base.sanitize_text(json.dumps(payload, ensure_ascii=False, indent=2), config)
        sections.append(
            f"## Candidate {item['critic_item_id']}\n```json\n{encoded}\n```\n\n"
            f"Exact head-file context for this candidate:\n{context}"
        )

    prompt = f"""
You are the independent DCOIR Review VERIFIED REPAIR-SET CRITIC. Evaluate every
listed repair set independently. Do not find new issues or author a different
patch. Return exactly one disposition for every supplied critic_item_id.

For EACH repair set, accepted=true requires all existing v36/v38 rules:
- the verified finding is real in exact-head context;
- every edit is necessary, complete, exact, and semantically appropriate;
- no unrelated cleanup, speculative change, stale range, or omitted companion edit exists;
- unrelated behavior is preserved and the set is safe for human application;
- confidence is numeric in 0.0..1.0 and accepted=true requires confidence >= {v36.CRITIC_MIN_CONFIDENCE:.2f}.

Judge candidates independently. Never invent, omit, rename, or duplicate
critic_item_id values. One candidate's disposition must not affect another.

{chr(10).join(sections)}
""".strip()
    return v25._sanitize_prompt(module, prompt, config)


def parse_batch(raw: Any, pending: list[dict[str, Any]], hardened: Any) -> dict[str, tuple[bool, float, str]]:
    """Map by identity; ambiguity fails closed only for the affected repair."""

    expected = {item["critic_item_id"] for item in pending}
    missing = (False, 0.0, "independent repair-set critic returned no valid identity-bound disposition")
    if not isinstance(raw, dict) or not isinstance(raw.get("results"), list):
        return {item_id: missing for item_id in expected}

    parsed: dict[str, tuple[bool, float, str]] = {}
    duplicates: set[str] = set()
    for item in raw["results"]:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("critic_item_id", "") or "").strip()
        if item_id not in expected:
            continue
        if item_id in parsed or item_id in duplicates:
            duplicates.add(item_id)
            parsed.pop(item_id, None)
            continue
        try:
            parsed[item_id] = v36._parse_critic(item, hardened)
        except Exception as exc:
            parsed[item_id] = (
                False,
                0.0,
                f"independent repair-set critic result failed closed: {type(exc).__name__}: {str(exc)[:300]}",
            )
    for item_id in duplicates:
        parsed[item_id] = (False, 0.0, "independent repair-set critic returned duplicate dispositions")
    for item_id in expected:
        parsed.setdefault(item_id, missing)
    return parsed


def run_group(
    module: Any,
    group: list[dict[str, Any]],
    file_cache: dict[str, str],
    right_line_index: dict[tuple[str, int], int],
    config: Any,
) -> tuple[list[tuple[int, dict[str, Any]]], int]:
    """Run one compatible critic group, splitting only when its prompt is too large."""

    if not group:
        return [], 0
    if len(group) == 1:
        item = group[0]
        critic_config = v36._repair_critic_config(config, item["author_model"])
        prompt = v36._repair_critic_prompt(module, item["finding"], item["author"], file_cache, config)
        try:
            raw, model, tier = module.hardened.openrouter_review(
                prompt, v36.REPAIR_SET_CRITIC_SCHEMA, critic_config, reporter=None
            )
            decision = v36._parse_critic(raw, module.hardened)
        except Exception as exc:
            raw, model, tier = {}, item["critic_model"], ""
            decision = (False, 0.0, f"repair critic failed closed: {type(exc).__name__}: {str(exc)[:300]}")
        module.hardened.write_debug_json_artifact_safely(
            config,
            f"responses/repair-v36/{item['ordinal']:02d}-critic.json",
            {"path": item["finding"].get("path", ""), "line": item["finding"].get("line", 0), "model": model, "service_tier": tier, "result": raw},
        )
        final = repair.finalize_candidate(
            module, item, decision, model, tier, right_line_index, file_cache, config, 1
        )
        return [(item["ordinal"], final)], 1

    prompt = batch_prompt(module, group, file_cache, config)
    if len(prompt) > MAX_BATCH_PROMPT_CHARS:
        midpoint = len(group) // 2
        left, left_calls = run_group(module, group[:midpoint], file_cache, right_line_index, config)
        right, right_calls = run_group(module, group[midpoint:], file_cache, right_line_index, config)
        return left + right, left_calls + right_calls

    critic_config = v36._repair_critic_config(config, group[0]["author_model"])
    setattr(critic_config, STAGE_LABEL_ATTR, "repair-critic")
    model = group[0]["critic_model"]
    tier = ""
    try:
        raw, model, tier = module.hardened.openrouter_review(
            prompt, BATCH_CRITIC_SCHEMA, critic_config, reporter=None
        )
        decisions = parse_batch(raw, group, module.hardened)
    except Exception as exc:
        raw = {}
        decisions = {
            item["critic_item_id"]: (
                False,
                0.0,
                f"repair critic batch failed closed: {type(exc).__name__}: {str(exc)[:300]}",
            )
            for item in group
        }

    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/repair-v56/batch-{group[0]['ordinal']:02d}-{group[-1]['ordinal']:02d}-critic.json",
        {"critic_model": model, "service_tier": tier, "item_count": len(group), "result": raw},
    )
    results: list[tuple[int, dict[str, Any]]] = []
    for item in group:
        decision = decisions[item["critic_item_id"]]
        module.hardened.write_debug_json_artifact_safely(
            config,
            f"responses/repair-v36/{item['ordinal']:02d}-critic.json",
            {"path": item["finding"].get("path", ""), "line": item["finding"].get("line", 0), "model": model, "service_tier": tier, "critic_item_id": item["critic_item_id"], "batch_size": len(group), "decision": decision},
        )
        final = repair.finalize_candidate(
            module, item, decision, model, tier, right_line_index, file_cache, config, len(group)
        )
        results.append((item["ordinal"], final))
    return results, 1
