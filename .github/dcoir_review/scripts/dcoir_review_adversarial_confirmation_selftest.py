#!/usr/bin/env python3
"""Regression checks for canonical independent adversarial confirmation."""

from __future__ import annotations

import importlib
from pathlib import Path

from dcoir_review import adversarial_confirmation
from dcoir_review import adversarial_prompt_policy
from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v32" not in entrypoint.patch_module_names
    assert "dcoir_review.review_orchestration" in entrypoint.execution_policy_patch_module_names

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    assert config.adversarial_confirmation_review is True
    assert adversarial_confirmation.confirmation_models(config) == ["openai/gpt-5.6-sol-pro"]
    assert adversarial_confirmation.INDEPENDENT_CONFIRMATION_BLOCK == adversarial_prompt_policy.INDEPENDENT_CONFIRMATION_BLOCK
    assert adversarial_confirmation.confirmation_models(type("C", (), {"adversarial_confirmation_model_stack": []})()) == ["openai/gpt-5.6-sol-pro"]
    assert adversarial_confirmation.confirmation_models(type("C", (), {"adversarial_confirmation_model_stack": "openai/gpt-custom"})()) == ["openai/gpt-custom"]
    try:
        adversarial_confirmation.build_adversarial_confirmation_stage(review, None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("non-callable challenger predecessor must fail closed")
    for required_phrase in (
        "minimal counterexamples",
        "semantic scope binding",
        "assertion polarity",
        "representation variants",
        "helper consistency",
        "passing tests as evidence, not proof",
    ):
        assert required_phrase in adversarial_prompt_policy.ADVERSARIAL_SEMANTIC_BLOCK

    system_prompt = Path(".github/dcoir_review/prompts/openrouter-pr-review-system.md").read_text(encoding="utf-8")
    assert "adversarial" in system_prompt.lower()
    assert "counterexample" in system_prompt.lower()
    assert "scope binding" in system_prompt.lower()

    observed: dict[str, object] = {}
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    }

    def fake_first_pass(*_args, **_kwargs):
        return {"summary": "Primary clean.", "findings": []}, "primary-test", "tier-primary"

    def fake_build_prompt(*_args, **_kwargs):
        return "aggregate PR context"

    def fake_openrouter_review(prompt, _schema, cfg, _reporter):
        observed["prompt"] = prompt
        observed["models"] = list(cfg.model_stack)
        return (
            {
                "summary": "Independent challenger found a semantic bypass.",
                "findings": [{
                    "title": "Scope binding bypass",
                    "severity": "medium",
                    "confidence": 0.93,
                    "path": "probe.py",
                    "line": 10,
                    "body": "Required evidence can be supplied in the wrong semantic lane.",
                    "suggested_replacement": "",
                    "validation": "Run focused regression.",
                }],
            },
            "openai/gpt-5.6-sol-pro",
            "tier-confirmation",
        )

    original_build_prompt = review.build_prompt
    original_openrouter_review = review.hardened.openrouter_review
    original_write_text = review.hardened.write_debug_text_artifact_safely
    original_write_json = review.hardened.write_debug_json_artifact_safely
    try:
        review.build_prompt = fake_build_prompt
        review.hardened.openrouter_review = fake_openrouter_review
        review.hardened.write_debug_text_artifact_safely = lambda *_args, **_kwargs: None
        review.hardened.write_debug_json_artifact_safely = lambda *_args, **_kwargs: None
        stage = adversarial_confirmation.build_adversarial_confirmation_stage(review, fake_first_pass)
        result, model_used, service_tier = stage(
            {}, [], "", schema, config, None, [], {}, "", "deep-forced", "", None
        )
    finally:
        review.build_prompt = original_build_prompt
        review.hardened.openrouter_review = original_openrouter_review
        review.hardened.write_debug_text_artifact_safely = original_write_text
        review.hardened.write_debug_json_artifact_safely = original_write_json

    assert observed["models"] == ["openai/gpt-5.6-sol-pro"]
    assert "Independent adversarial confirmation pass" in str(observed["prompt"])
    assert len(result.get("findings", [])) == 1
    assert result.get("_adversarial_confirmation_attempted") is True
    assert result.get("_adversarial_confirmation_model") == "openai/gpt-5.6-sol-pro"
    assert "primary-test" in model_used and "openai/gpt-5.6-sol-pro" in model_used
    assert "tier-primary" in service_tier and "tier-confirmation" in service_tier

    # Opposite-polarity controls: disabled and non-deep review must preserve the
    # preceding result exactly and never call the challenger.
    skip_calls = {"count": 0}
    def should_not_run(*_args, **_kwargs):
        skip_calls["count"] += 1
        raise AssertionError("challenger should not run")
    original_openrouter_review = review.hardened.openrouter_review
    review.hardened.openrouter_review = should_not_run
    try:
        disabled = type("C", (), vars(config).copy())()
        disabled.adversarial_confirmation_review = False
        stage = adversarial_confirmation.build_adversarial_confirmation_stage(review, fake_first_pass)
        assert stage({}, [], "", schema, disabled, None, [], {}, "", "deep-forced", "", None) == (
            {"summary": "Primary clean.", "findings": []}, "primary-test", "tier-primary"
        )
        assert stage({}, [], "", schema, config, None, [], {}, "", "first-pass", "", None) == (
            {"summary": "Primary clean.", "findings": []}, "primary-test", "tier-primary"
        )
    finally:
        review.hardened.openrouter_review = original_openrouter_review
    assert skip_calls["count"] == 0

    # Tiny prompt budgets remain true hard ceilings, including budgets shorter
    # than the truncation marker itself.
    for tiny_budget in (0, 1, 7):
        tiny = type("C", (), vars(config).copy())()
        tiny.max_prompt_chars = tiny_budget
        seen = {"prompt": None}
        original_build_prompt = review.build_prompt
        original_openrouter_review = review.hardened.openrouter_review
        original_write_text = review.hardened.write_debug_text_artifact_safely
        original_write_json = review.hardened.write_debug_json_artifact_safely
        try:
            review.build_prompt = lambda *_args, **_kwargs: "aggregate context" * 100
            review.hardened.openrouter_review = lambda prompt, *_args, **_kwargs: (
                seen.__setitem__("prompt", prompt) or {"summary": "clean", "findings": []},
                "openai/gpt-5.6-sol-pro",
                "default",
            )
            review.hardened.write_debug_text_artifact_safely = lambda *_args, **_kwargs: None
            review.hardened.write_debug_json_artifact_safely = lambda *_args, **_kwargs: None
            adversarial_confirmation.build_adversarial_confirmation_stage(review, fake_first_pass)(
                {}, [], "", schema, tiny, None, [], {}, "", "deep-forced", "", None
            )
        finally:
            review.build_prompt = original_build_prompt
            review.hardened.openrouter_review = original_openrouter_review
            review.hardened.write_debug_text_artifact_safely = original_write_text
            review.hardened.write_debug_json_artifact_safely = original_write_json
        assert isinstance(seen["prompt"], str) and len(seen["prompt"]) <= tiny_budget

    # Provider failures remain fail-closed and preserve exception identity.
    sentinel = RuntimeError("challenger provider failed")
    original_openrouter_review = review.hardened.openrouter_review
    original_build_prompt = review.build_prompt
    original_write_text = review.hardened.write_debug_text_artifact_safely
    try:
        review.build_prompt = lambda *_args, **_kwargs: "aggregate"
        def fail_provider(*_args, **_kwargs):
            raise sentinel
        review.hardened.openrouter_review = fail_provider
        review.hardened.write_debug_text_artifact_safely = lambda *_args, **_kwargs: None
        try:
            adversarial_confirmation.build_adversarial_confirmation_stage(review, fake_first_pass)(
                {}, [], "", schema, config, None, [], {}, "", "deep-forced", "", None
            )
        except RuntimeError as exc:
            assert exc is sentinel
        else:
            raise AssertionError("challenger provider failure must propagate")
    finally:
        review.hardened.openrouter_review = original_openrouter_review
        review.build_prompt = original_build_prompt
        review.hardened.write_debug_text_artifact_safely = original_write_text

    print("dcoir_review_adversarial_confirmation_selftest passed")


if __name__ == "__main__":
    main()
