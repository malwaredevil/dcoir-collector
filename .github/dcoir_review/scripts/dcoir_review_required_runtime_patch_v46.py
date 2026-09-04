"""Architecture-B v46 canonical semantic context and adaptive budgets."""

from __future__ import annotations

import copy
from typing import Any

import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v46_budget as budgets
import dcoir_review_required_runtime_patch_v46_context as context
from dcoir_review_required_runtime_patch_v46_contract import (
    APPLIED_ATTR,
    BUDGET_CONTRACT,
    CONTEXT_PACKAGE_CONTRACT,
    PACKAGE_ATTR,
    RUNTIME_ATTR,
    positive_int,
)


_CONFIG_STORAGE = "_dcoir_v46_original_load_pareto_context_config"
_HYBRID_STORAGE = "_dcoir_v46_original_hybrid_first_pass"
_FILE_CONTEXT_STORAGE = "_dcoir_v46_original_build_file_contexts"
_FILE_PROMPT_STORAGE = "_dcoir_v46_original_build_per_file_review_prompt"
_BROAD_PROMPT_STORAGE = "_dcoir_v46_original_build_prompt"


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, _CONFIG_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, _CONFIG_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v46 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.canonical_semantic_context_review = module.hardened.bool_value(
            data, "canonical_semantic_context_review", True
        )
        config.adaptive_semantic_budgets_review = module.hardened.bool_value(
            data, "adaptive_semantic_budgets_review", True
        )
        defaults = {
            "adaptive_semantic_min_prompt_chars": 48000,
            "adaptive_semantic_small_delta_prompt_chars": 60000,
            "adaptive_semantic_small_delta_max_files": 4,
            "adaptive_semantic_small_delta_max_diff_chars": 20000,
            "adaptive_semantic_small_delta_max_context_chars": 30000,
        }
        for key, fallback in defaults.items():
            setattr(config, key, positive_int(data.get(key, fallback), fallback))
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _runtime(module: Any, config: Any | None = None) -> dict[str, Any] | None:
    runtime = getattr(module, RUNTIME_ATTR, None)
    if not isinstance(runtime, dict):
        return None
    if config is not None:
        package_id = str(runtime.get("metadata", {}).get("package_id", "") or "")
        if str(getattr(config, "_dcoir_v46_context_package_id", "") or "") != package_id:
            return None
    return runtime


def _patch_context_projections(module: Any) -> tuple[Any, Any, Any]:
    original_contexts = getattr(module, _FILE_CONTEXT_STORAGE, None)
    if original_contexts is None:
        original_contexts = getattr(module, "build_file_contexts", None)
        if callable(original_contexts):
            setattr(module, _FILE_CONTEXT_STORAGE, original_contexts)
    original_file_prompt = getattr(module, _FILE_PROMPT_STORAGE, None)
    if original_file_prompt is None:
        original_file_prompt = getattr(module, "build_per_file_review_prompt", None)
        if callable(original_file_prompt):
            setattr(module, _FILE_PROMPT_STORAGE, original_file_prompt)
    original_broad_prompt = getattr(module, _BROAD_PROMPT_STORAGE, None)
    if original_broad_prompt is None:
        original_broad_prompt = getattr(module, "build_prompt", None)
        if callable(original_broad_prompt):
            setattr(module, _BROAD_PROMPT_STORAGE, original_broad_prompt)
    builders = (original_contexts, original_file_prompt, original_broad_prompt)
    if not all(callable(item) for item in builders):
        raise RuntimeError("DCOIR v46 could not locate semantic context builders")

    def build_file_contexts(gh, pr, files, config):
        active = _runtime(module, config)
        if active is not None and context.matches_file_surface(active, pr, files):
            active["telemetry"]["file_context_projection_reuse_count"] += 1
            return copy.deepcopy(active.get("file_contexts", []))
        if isinstance(getattr(module, RUNTIME_ATTR, None), dict):
            getattr(module, RUNTIME_ATTR)["telemetry"]["fallback_projection_count"] += 1
        return original_contexts(gh, pr, files, config)

    def build_per_file_review_prompt(
        pr, item, file_text, diff, config, path_sentinels, review_mode
    ):
        active = _runtime(module, config)
        if active is None:
            return original_file_prompt(
                pr, item, file_text, diff, config, path_sentinels, review_mode
            )
        key = context.per_file_prompt_key(
            module,
            pr,
            item,
            file_text,
            diff,
            config,
            path_sentinels,
            review_mode,
        )
        cache = active["per_file_prompt_cache"]
        if key in cache:
            active["telemetry"]["per_file_prompt_reuse_count"] += 1
            return cache[key]
        prompt = original_file_prompt(
            pr, item, file_text, diff, config, path_sentinels, review_mode
        )
        cache[key] = prompt
        active["telemetry"]["per_file_prompt_build_count"] += 1
        return prompt

    def build_prompt(
        pr,
        files,
        diff,
        config,
        risk_sentinels,
        deep_context_block,
        review_mode,
        context_summary,
    ):
        active = _runtime(module, config)
        if active is None:
            return original_broad_prompt(
                pr,
                files,
                diff,
                config,
                risk_sentinels,
                deep_context_block,
                review_mode,
                context_summary,
            )
        expected = active.get("metadata", {}).get("input_signature")
        actual = context.input_signature(
            pr, files, diff, deep_context_block, review_mode, context_summary
        )
        if expected != actual:
            active["telemetry"]["fallback_projection_count"] += 1
            return original_broad_prompt(
                pr,
                files,
                diff,
                config,
                risk_sentinels,
                deep_context_block,
                review_mode,
                context_summary,
            )
        key = context.broad_prompt_key(
            pr,
            files,
            diff,
            config,
            deep_context_block,
            review_mode,
            context_summary,
            risk_sentinels,
            module,
        )
        cache = active["broad_prompt_cache"]
        if key in cache:
            active["telemetry"]["broad_prompt_reuse_count"] += 1
            return cache[key]
        prompt = original_broad_prompt(
            pr,
            files,
            diff,
            config,
            risk_sentinels,
            deep_context_block,
            review_mode,
            context_summary,
        )
        cache[key] = prompt
        active["telemetry"]["broad_prompt_build_count"] += 1
        return prompt

    module.build_file_contexts = build_file_contexts
    module.build_per_file_review_prompt = build_per_file_review_prompt
    module.build_prompt = build_prompt
    return original_contexts, original_file_prompt, original_broad_prompt


def _write_state(
    module: Any,
    gh: Any,
    config: Any,
    runtime: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    package = context.public_payload(runtime)
    package["budget_plan"] = copy.deepcopy(plan)
    setattr(gh, PACKAGE_ATTR, copy.deepcopy(package))
    module.hardened.write_debug_json_artifact_safely(
        config, "metadata/semantic-context-package-v46.json", package
    )
    module.hardened.write_debug_json_artifact_safely(
        config, "metadata/adaptive-semantic-budget-v46.json", copy.deepcopy(plan)
    )
    ledger = getattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, None)
    if isinstance(ledger, dict):
        ledger["context_package"] = {
            "contract": CONTEXT_PACKAGE_CONTRACT,
            "package_id": package.get("package_id", ""),
            "input_signature": package.get("input_signature", ""),
            "telemetry": copy.deepcopy(package.get("telemetry", {})),
        }
        ledger["adaptive_budget"] = copy.deepcopy(plan)
        setattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, ledger)
        v42_hooks._LAST_LEDGER = ledger
        module.hardened.write_debug_json_artifact_safely(
            config, "metadata/semantic-review-ledger.json", ledger
        )


def _patch_hybrid(module: Any, original_contexts: Any) -> None:
    original = getattr(module, _HYBRID_STORAGE, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, _HYBRID_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v46 could not locate active hybrid review function")

    def openrouter_review_with_hybrid_first_pass(
        pr,
        files,
        diff,
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        if not bool(getattr(config, "canonical_semantic_context_review", False)):
            return original(
                pr,
                files,
                diff,
                schema,
                config,
                reporter,
                risk_sentinels,
                line_index,
                deep_context_block,
                review_mode,
                context_summary,
                gh,
            )
        active = context.build_context_runtime(
            module,
            gh,
            pr,
            files,
            diff,
            schema,
            config,
            risk_sentinels,
            deep_context_block,
            review_mode,
            context_summary,
            original_contexts,
        )
        setattr(module, RUNTIME_ATTR, active)
        plan = budgets.select_budget_plan(active, config, risk_sentinels)
        staged = budgets.configured_for_plan(config, plan)
        active["metadata"]["budget_contract"] = BUDGET_CONTRACT
        active["metadata"]["budget_mode"] = plan["mode"]
        active["metadata"]["outcome"] = "prepared"
        _write_state(module, gh, staged, active, plan)
        update = getattr(reporter, "update", None)
        if callable(update):
            update(
                "semantic-context-budget",
                (
                    f"package={active['metadata']['package_id'][:12]}; "
                    f"budget={plan['mode']}; prompt={plan['selected']['max_prompt_chars']}"
                ),
            )
        try:
            result, model, tier = original(
                pr,
                files,
                diff,
                schema,
                staged,
                reporter,
                risk_sentinels,
                line_index,
                deep_context_block,
                review_mode,
                context_summary,
                gh,
            )
        except Exception as exc:
            active["metadata"]["outcome"] = "failed"
            active["metadata"]["failure_type"] = type(exc).__name__
            _write_state(module, gh, staged, active, plan)
            raise
        active["metadata"]["outcome"] = "completed"
        _write_state(module, gh, staged, active, plan)
        final = dict(result)
        final["_semantic_context_package_id"] = active["metadata"]["package_id"]
        final["_adaptive_semantic_budget_mode"] = plan["mode"]
        return final, model, tier

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def semantic_context_package_for_client(gh: Any) -> dict[str, Any]:
    value = getattr(gh, PACKAGE_ATTR, {})
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_ATTR, False):
        return
    _patch_config_loader(module)
    original_contexts, _file_prompt, _broad_prompt = _patch_context_projections(module)
    _patch_hybrid(module, original_contexts)
    module.semantic_context_package_for_client = semantic_context_package_for_client
    module.DCOIR_SEMANTIC_CONTEXT_PACKAGE_CONTRACT = CONTEXT_PACKAGE_CONTRACT
    module.DCOIR_ADAPTIVE_SEMANTIC_BUDGET_CONTRACT = BUDGET_CONTRACT
    setattr(module, APPLIED_ATTR, True)


__all__ = [
    "apply_pareto_context_module",
    "semantic_context_package_for_client",
]
