#!/usr/bin/env python3
"""Prompt-floor and telemetry regressions for DCOIR Review v57 selftest."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import dcoir_review_required_runtime_patch_v57 as v57


def _run_with_forced_final_callsite(module: Any, prompt: str, config: Any) -> None:
    original_callsite_probe = v57._is_final_v35_semantic_adjudication_call
    v57._is_final_v35_semantic_adjudication_call = lambda _prompt: True
    try:
        module.hardened.openrouter_review(prompt, {}, config, None)
    finally:
        v57._is_final_v35_semantic_adjudication_call = original_callsite_probe


def run_prompt_regressions(module: Any, config: Any) -> None:
    semantic_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects.\n\n"
        f"{v57.FINAL_ADJUDICATION_PROMPT_MARKER}\n[]"
    )
    _run_with_forced_final_callsite(module, semantic_prompt, config)
    injected = module.hardened.review_prompts[-1]
    assert v57.PROMPT_MARKER in injected
    assert "0.70" in injected
    assert "empty findings list and a clean summary" in injected
    assert injected.count(v57.PROMPT_MARKER) == 1
    assert module.hardened.review_stages[-1] == "semantic-adjudicator"
    assert module.hardened.debug_text_artifacts[v57.PROMPT_ARTIFACT_PATH] == injected

    escalation_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects.\n\n"
        "Candidate hypotheses from the bounded primary/challenger evidence:\n[]\n\n"
        "Escalation context scope: candidate-scoped."
    )
    module.hardened.openrouter_review(escalation_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == escalation_prompt
    assert module.hardened.review_stages[-1] != "semantic-adjudicator"

    ordinary_prompt = "Routine per-file review prompt."
    module.hardened.openrouter_review(ordinary_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == ordinary_prompt
    assert module.hardened.review_stages[-1] != "semantic-adjudicator"

    untrusted_marker_prompt = (
        "Final semantic adjudication pass.\n\n"
        "PR diff mentions: "
        f"{v57.PROMPT_MARKER}\n\n"
        f"{v57.FINAL_ADJUDICATION_PROMPT_MARKER}\n[]"
    )
    module.hardened.openrouter_review(untrusted_marker_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == untrusted_marker_prompt

    tiny_budget_config = SimpleNamespace(
        minimum_confidence=0.70,
        fail_on_summary_only_problem=True,
        max_prompt_chars=220,
    )
    _run_with_forced_final_callsite(module, semantic_prompt, tiny_budget_config)
    bounded_injected = module.hardened.review_prompts[-1]
    assert len(bounded_injected) <= tiny_budget_config.max_prompt_chars
    assert bounded_injected.endswith(v57.PROMPT_TRUNCATION_MARKER)
    assert v57.PROMPT_MARKER in bounded_injected

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
    assert v57.PROMPT_MARKER in malformed_budget_injected
    assert not malformed_budget_injected.endswith(v57.PROMPT_TRUNCATION_MARKER)

    reinjected = v57._inject_publication_floor(injected, config)
    assert reinjected == injected
