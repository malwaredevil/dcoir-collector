#!/usr/bin/env python3
"""Prompt-floor regressions for stable final-adjudication policy."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from dcoir_review import final_adjudication_policy as final_policy


def _run_projected(module: Any, prompt: Any, config: Any):
    projected_prompt, projected_config = final_policy.project_review_call(
        module, prompt, config
    )
    return module.hardened.openrouter_review(
        projected_prompt, {}, projected_config, None
    )


def _run_with_forced_final_callsite(module: Any, prompt: str, config: Any):
    original_callsite_probe = final_policy._is_final_v35_semantic_adjudication_call
    final_policy._is_final_v35_semantic_adjudication_call = lambda _prompt: True
    try:
        return _run_projected(module, prompt, config)
    finally:
        final_policy._is_final_v35_semantic_adjudication_call = original_callsite_probe


def _run_with_v35_semantic_callsite(module: Any, prompt: str, config: Any):
    namespace: dict[str, Any] = {
        "_run_projected": _run_projected,
        "module": module,
        "config": config,
    }
    exec(
        compile(
            """
def semantic_adjudication_stage(prompt):
    return _run_projected(module, prompt, config)
""",
            "dcoir_review_required_runtime_patch_v35.py",
            "exec",
        ),
        namespace,
    )
    return namespace["semantic_adjudication_stage"](prompt)


def run_prompt_regressions(module: Any, config: Any) -> None:
    semantic_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects.\n\n"
        f"{final_policy.FINAL_ADJUDICATION_PROMPT_MARKER}\n[]"
    )
    _run_with_forced_final_callsite(module, semantic_prompt, config)
    injected = module.hardened.review_prompts[-1]
    assert final_policy.PROMPT_MARKER in injected
    assert "0.70" in injected
    assert "empty findings list and a clean summary" in injected
    assert injected.count(final_policy.PROMPT_MARKER) == 1
    assert module.hardened.review_stages[-1] == "semantic-adjudicator"
    assert module.hardened.debug_text_artifacts[final_policy.PROMPT_ARTIFACT_PATH] == injected

    _run_with_v35_semantic_callsite(module, semantic_prompt, config)
    composed_injected = module.hardened.review_prompts[-1]
    assert final_policy.PROMPT_MARKER in composed_injected
    assert "empty findings list and a clean summary" in composed_injected
    assert module.hardened.review_stages[-1] == "semantic-adjudicator"

    escalation_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects.\n\n"
        "Candidate hypotheses from the bounded primary/challenger evidence:\n[]\n\n"
        "Escalation context scope: candidate-scoped."
    )
    _run_projected(module, escalation_prompt, config)
    assert module.hardened.review_prompts[-1] == escalation_prompt
    assert module.hardened.review_stages[-1] != "semantic-adjudicator"

    ordinary_prompt = "Routine per-file review prompt."
    _run_projected(module, ordinary_prompt, config)
    assert module.hardened.review_prompts[-1] == ordinary_prompt
    assert module.hardened.review_stages[-1] != "semantic-adjudicator"

    untrusted_marker_prompt = (
        "Final semantic adjudication pass.\n\n"
        "PR diff mentions: "
        f"{final_policy.PROMPT_MARKER}\n\n"
        f"{final_policy.FINAL_ADJUDICATION_PROMPT_MARKER}\n[]"
    )
    _run_projected(module, untrusted_marker_prompt, config)
    assert module.hardened.review_prompts[-1] == untrusted_marker_prompt

    tiny_budget_config = SimpleNamespace(
        minimum_confidence=0.70,
        fail_on_summary_only_problem=True,
        max_prompt_chars=220,
    )
    _run_with_forced_final_callsite(module, semantic_prompt, tiny_budget_config)
    bounded_injected = module.hardened.review_prompts[-1]
    assert len(bounded_injected) <= tiny_budget_config.max_prompt_chars
    assert bounded_injected.endswith(final_policy.PROMPT_TRUNCATION_MARKER)
    assert final_policy.PROMPT_MARKER in bounded_injected

    tiny_marker_budget = SimpleNamespace(
        minimum_confidence=0.70,
        fail_on_summary_only_problem=True,
        max_prompt_chars=8,
    )
    _run_with_forced_final_callsite(module, semantic_prompt, tiny_marker_budget)
    smallest_bounded = module.hardened.review_prompts[-1]
    assert len(smallest_bounded) == tiny_marker_budget.max_prompt_chars

    malformed_budget_config = SimpleNamespace(
        minimum_confidence=0.70,
        fail_on_summary_only_problem=True,
        max_prompt_chars="invalid",
    )
    _run_with_forced_final_callsite(module, semantic_prompt, malformed_budget_config)
    malformed_budget_injected = module.hardened.review_prompts[-1]
    assert final_policy.PROMPT_MARKER in malformed_budget_injected
    assert not malformed_budget_injected.endswith(final_policy.PROMPT_TRUNCATION_MARKER)

    original_writer = module.hardened.write_debug_text_artifact_safely

    def failing_writer(_config, _path: str, _payload: Any) -> None:
        raise RuntimeError("debug artifact unavailable")

    module.hardened.write_debug_text_artifact_safely = failing_writer
    try:
        assert _run_with_forced_final_callsite(module, semantic_prompt, config) == (
            {"summary": "clean", "findings": []},
            "fake-model",
            "default",
        )
    finally:
        module.hardened.write_debug_text_artifact_safely = original_writer

    reinjected = final_policy._inject_publication_floor(injected, config)
    assert reinjected == injected

    original_inject = final_policy._inject_publication_floor
    source_prompt = object()
    source_config = SimpleNamespace(minimum_confidence=0.70)
    def broken_inject(_prompt, _config):
        raise RuntimeError("synthetic injection failure")
    final_policy._inject_publication_floor = broken_inject
    try:
        projected_prompt, projected_config = final_policy.project_review_call(
            module, source_prompt, source_config
        )
    finally:
        final_policy._inject_publication_floor = original_inject
    assert projected_prompt is source_prompt
    assert projected_config is source_config
