"""DCOIR Review v32 adversarial semantic-recall overlay for issue #456.

Issue #456 was opened after repeated evidence that a clean DCOIR Review could be
followed immediately by a GitHub Copilot Balanced review containing valid
semantic findings.  The misses were not primarily syntax/security patterns;
they were counterexamples against changed scorers and validation gates (scope
binding, negation/rejection polarity, duplicate variants, and token evidence in
the wrong semantic lane).

v32 changes the review process rather than teaching it PR-specific answers:

* every per-file detector prompt receives an explicit invariant-falsification
  checklist;
* deep review gets an independent adversarial confirmation pass using a
  separately configured model stack and merges the union of findings;
* OpenRouter reasoning effort is requested for models whose reasoning mode is
  not already fixed by the model SKU;
* configuration exposes the confirmation model stack and reasoning effort.

OpenRouter's ``*-pro`` OpenAI SKUs already select a fixed Pro reasoning mode.
v32 therefore does not layer an explicit reasoning-effort override on those
models; doing so can make an otherwise available endpoint ineligible.  Other
configured models still receive the governed review reasoning effort.

The confirmation pass is fail-closed: when enabled for a deep review, inability
to complete the independent pass is a review failure rather than a false clean
result.  This overlay adds no branch-write, commit, or autonomous remediation
capability.  Native GitHub suggestions remain downstream human-applied output.
"""

from __future__ import annotations

import copy
from typing import Any


VERSION = "v32"
APPLIED_MARKER = "_dcoir_review_v32_applied"
DEFAULT_CONFIRMATION_MODELS = ("openai/gpt-5.6-sol-pro",)
DEFAULT_REASONING_EFFORT = "xhigh"

ADVERSARIAL_SEMANTIC_BLOCK = """
Adversarial semantic falsification requirements:
- For every changed validator, scorer, parser, normalizer, router, policy gate, selector, or acceptance helper, state the intended accept/reject invariant from the supplied code, tests, PR description, and repository guidance, then actively try to falsify it.
- Construct minimal counterexamples that should be rejected but might pass, and valid examples that should pass but might be rejected. Report only counterexamples you can validate against the supplied implementation.
- Probe semantic scope binding: a required token/action in the wrong clause, lane, object, branch, phase, or namespace must not satisfy the intended requirement.
- Probe assertion polarity and discourse: negation, rejection of a quoted/mentioned claim, postposed prohibition/unavailability, disclaimers, and statements such as 'wrong to say X' must not be mistaken for affirmative evidence of X.
- Probe representation variants when matching text or structure: numbered/inline headings, punctuation, normalization, snake_case versus spaced keys, serialization/JSON forms, quoting, repeated blocks, and duplicate procedures.
- Probe helper consistency: if one path uses stronger negation/scope/rejection handling than a sibling path for the same semantic concept, attempt the weaker-path bypass.
- Treat passing tests as evidence, not proof. Inspect whether the negative controls actually isolate the changed invariant and whether an untested neighboring variant can bypass it.
- Prefer a concrete reproducible counterexample over a general warning. If no counterexample or other actionable defect survives inspection, return a clean result.
""".strip()

INDEPENDENT_CONFIRMATION_BLOCK = """
Independent adversarial confirmation pass:
The preceding detector pass is untrusted evidence, not a conclusion. Review the supplied PR independently and try to disprove its changed correctness/validation contracts before accepting a clean result. In particular, apply the adversarial semantic falsification requirements below. Do not merely restate tests or the PR description, and do not assume an existing detector would have caught the defect.

""" + ADVERSARIAL_SEMANTIC_BLOCK


def _as_string_list(value: Any, fallback: tuple[str, ...]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback)


def _model_owns_fixed_pro_reasoning(model: Any) -> bool:
    """Return True for OpenAI model SKUs that already encode Pro reasoning."""

    value = str(model or "").strip().lower()
    if not value.startswith("openai/"):
        return False
    model_id = value.split("/", 1)[1].split(":", 1)[0]
    return model_id.endswith("-pro") or "-pro-" in model_id


def _patch_config_loader(module: Any) -> None:
    storage = "_dcoir_review_v32_original_load_pareto_context_config"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v32 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.adversarial_confirmation_review = module.hardened.bool_value(
            data, "adversarial_confirmation_review", True
        )
        config.adversarial_confirmation_model_stack = _as_string_list(
            data.get("adversarial_confirmation_model_stack"), DEFAULT_CONFIRMATION_MODELS
        )
        config.review_reasoning_effort = str(
            data.get("review_reasoning_effort", DEFAULT_REASONING_EFFORT) or DEFAULT_REASONING_EFFORT
        ).strip()
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _patch_reasoning_payload(module: Any) -> None:
    hardened = module.hardened
    storage = "_dcoir_review_v32_original_build_openrouter_payload"
    original = getattr(hardened, storage, None)
    if original is None:
        original = getattr(hardened, "build_openrouter_payload", None)
        if callable(original):
            setattr(hardened, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v32 could not locate hardened build_openrouter_payload")

    def build_openrouter_payload(prompt, schema, config, ignored_providers, model):
        payload = original(prompt, schema, config, ignored_providers, model)
        if _model_owns_fixed_pro_reasoning(model):
            # OpenRouter's OpenAI *-pro SKUs already encode reasoning.mode=pro.
            # Do not add or retain a second reasoning selector that can make the
            # otherwise available Pro endpoint ineligible.
            payload.pop("reasoning", None)
            return payload
        effort = str(getattr(config, "review_reasoning_effort", DEFAULT_REASONING_EFFORT) or "").strip()
        if effort and effort.lower() != "none":
            payload["reasoning"] = {
                "enabled": True,
                "effort": effort,
                "exclude": True,
            }
        return payload

    hardened.build_openrouter_payload = build_openrouter_payload
    # Some compatibility surfaces re-export the payload builder directly.
    if hasattr(module, "build_openrouter_payload"):
        module.build_openrouter_payload = build_openrouter_payload


def _patch_per_file_prompt(module: Any) -> None:
    storage = "_dcoir_review_v32_original_build_per_file_review_prompt"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "build_per_file_review_prompt", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v32 could not locate build_per_file_review_prompt")

    def build_per_file_review_prompt(*args, **kwargs):
        prompt = str(original(*args, **kwargs))
        config = kwargs.get("config")
        if config is None and len(args) >= 5:
            config = args[4]
        max_chars = int(getattr(config, "max_prompt_chars", 120000)) if config is not None else 120000
        combined = f"{prompt}\n\n{ADVERSARIAL_SEMANTIC_BLOCK}"
        marker = "\n\n[adversarial semantic prompt truncated by reviewer]"
        if len(combined) > max_chars:
            keep = max(0, max_chars - len(marker))
            combined = combined[:keep] + marker
        return combined

    module.build_per_file_review_prompt = build_per_file_review_prompt


def _patch_hybrid_confirmation(module: Any) -> None:
    storage = "_dcoir_review_v32_original_hybrid_first_pass"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v32 could not locate openrouter_review_with_hybrid_first_pass")

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
        first_result, first_model, first_tier = getattr(module, storage)(
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

        enabled = bool(getattr(config, "adversarial_confirmation_review", True))
        if not enabled or review_mode not in {"first-pass-deep", "deep-forced"}:
            return first_result, first_model, first_tier

        confirmation_config = copy.copy(config)
        confirmation_models = _as_string_list(
            getattr(config, "adversarial_confirmation_model_stack", None),
            DEFAULT_CONFIRMATION_MODELS,
        )
        confirmation_config.model_stack = confirmation_models
        confirmation_config.model = confirmation_models[0]

        aggregate_prompt = module.build_prompt(
            pr,
            files,
            diff,
            confirmation_config,
            risk_sentinels,
            deep_context_block,
            review_mode,
            context_summary,
        )
        confirmation_prompt = f"{INDEPENDENT_CONFIRMATION_BLOCK}\n\n{aggregate_prompt}"
        max_chars = int(getattr(confirmation_config, "max_prompt_chars", 120000))
        marker = "\n\n[independent adversarial confirmation prompt truncated by reviewer]"
        if len(confirmation_prompt) > max_chars:
            keep = max(0, max_chars - len(marker))
            confirmation_prompt = confirmation_prompt[:keep] + marker

        module.hardened.write_debug_text_artifact_safely(
            confirmation_config,
            "prompts/04-adversarial-confirmation-prompt.txt",
            confirmation_prompt,
        )
        if reporter:
            reporter.update(
                "adversarial-confirmation",
                f"running independent semantic challenger with {confirmation_models[0]}",
            )

        confirmation_result, confirmation_model, confirmation_tier = module.hardened.openrouter_review(
            confirmation_prompt,
            schema,
            confirmation_config,
            reporter,
        )
        module.hardened.write_debug_json_artifact_safely(
            confirmation_config,
            "responses/04-adversarial-confirmation-result.json",
            {
                "model_used": confirmation_model,
                "service_tier": confirmation_tier,
                "result": confirmation_result,
            },
        )

        merged = module.hardened.merge_review_results(first_result, confirmation_result)
        merged["_adversarial_confirmation_attempted"] = True
        merged["_adversarial_confirmation_model"] = confirmation_model
        merged["_adversarial_confirmation_first_model"] = first_model
        module.hardened.write_debug_json_artifact_safely(
            confirmation_config,
            "responses/05-adversarial-confirmation-merged-result.json",
            {
                "first_model": first_model,
                "confirmation_model": confirmation_model,
                "merged_finding_count": len(module.hardened.result_findings(merged)),
                "result": merged,
            },
        )
        model_label = f"{first_model}; independent-confirmation={confirmation_model}"
        tier_parts = [str(first_tier or "").strip(), str(confirmation_tier or "").strip()]
        tier_label = ", ".join(item for item in tier_parts if item)
        return merged, model_label, tier_label

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_config_loader(module)
    _patch_reasoning_payload(module)
    _patch_per_file_prompt(module)
    _patch_hybrid_confirmation(module)
    setattr(module, APPLIED_MARKER, True)
