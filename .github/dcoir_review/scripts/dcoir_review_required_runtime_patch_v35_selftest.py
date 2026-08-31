#!/usr/bin/env python3
"""Regression checks for DCOIR Review v35 semantic adjudication."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class _Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v35" in entrypoint.patch_module_names
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v34") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v35")
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v35") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v35 = importlib.import_module("dcoir_review_required_runtime_patch_v35")

    assert getattr(review, v35.APPLIED_MARKER, False) is True
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False
    assert config.semantic_adjudication_review is True
    assert config.semantic_adjudication_max_findings <= config.max_inline_comments
    assert config.semantic_adjudication_model_stack

    assert "untrusted hypothesis" in v35.ADJUDICATION_BLOCK
    assert "concrete minimal input" in v35.ADJUDICATION_BLOCK
    assert "Collapse multiple manifestations" in v35.ADJUDICATION_BLOCK
    assert "MAY add a high-confidence defect" in v35.ADJUDICATION_BLOCK
    assert "first try to prove it false" in v35.VERIFIER_FALSIFICATION_BLOCK

    digest, count = v35._candidate_digest(
        {
            "findings": [
                {
                    "path": "probe.py",
                    "line": 10,
                    "severity": "high",
                    "confidence": 0.94,
                    "title": "First hypothesis",
                    "body": "Possible scope failure",
                    "validation": "counterexample A",
                },
                {
                    "path": "probe.py",
                    "line": 11,
                    "severity": "medium",
                    "confidence": 0.90,
                    "title": "Neighboring manifestation",
                    "body": "Possible duplicate root cause",
                    "validation": "counterexample B",
                },
            ]
        },
        12000,
    )
    assert count == 2
    assert "First hypothesis" in digest and "Neighboring manifestation" in digest

    debug_text: dict[str, str] = {}
    debug_json: dict[str, dict[str, Any]] = {}
    reporter = _Reporter()

    def fake_detector(*args, **kwargs):
        return (
            {
                "summary": "Raw detector hypotheses",
                "findings": [
                    {
                        "path": "probe.py",
                        "line": 10,
                        "severity": "high",
                        "confidence": 0.94,
                        "title": "First hypothesis",
                        "body": "Possible scope failure",
                        "validation": "counterexample A",
                    },
                    {
                        "path": "probe.py",
                        "line": 11,
                        "severity": "medium",
                        "confidence": 0.90,
                        "title": "Neighboring manifestation",
                        "body": "Possible duplicate root cause",
                        "validation": "counterexample B",
                    },
                ],
            },
            "detector-model",
            "default",
        )

    def fake_openrouter(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        assert "First hypothesis" in prompt
        assert "concrete minimal input" in prompt
        assert "Independently adjudicate" in prompt
        # The adjudicator is authoritative and may return a proven root cause
        # that was not literally named in the detector candidate titles.
        return (
            {
                "summary": "One demonstrated root cause survives adjudication.",
                "findings": [
                    {
                        "path": "probe.py",
                        "line": 12,
                        "severity": "medium",
                        "confidence": 0.97,
                        "title": "Predicate accepts rejected evidence",
                        "body": "Counterexample: a rejected proposition still satisfies the positive branch. The sibling OR path omits the contextual rejection filter.",
                        "validation": "Trace the rejected input through the weaker sibling predicate and observe the true return value.",
                    }
                ],
            },
            "adjudicator-model",
            "default",
        )

    fake_hardened = SimpleNamespace(
        parse_yaml_like_data=lambda path: {},
        bool_value=lambda data, key, default: default,
        write_debug_text_artifact_safely=lambda cfg, path, text: debug_text.__setitem__(path, text),
        write_debug_json_artifact_safely=lambda cfg, path, payload: debug_json.__setitem__(path, payload),
        openrouter_review=fake_openrouter,
        result_findings=lambda result: list(result.get("findings", [])),
        ReviewQualityError=RuntimeError,
    )
    fake_base = SimpleNamespace(sanitize_text=lambda text, cfg: str(text))
    fake_module = SimpleNamespace(
        openrouter_review_with_hybrid_first_pass=fake_detector,
        hardened=fake_hardened,
        base=fake_base,
        build_prompt=lambda *args, **kwargs: "PR EVIDENCE: changed predicate and tests",
        rank_findings_for_required_budget=lambda findings, limit: findings[:limit],
    )
    v35._patch_semantic_adjudication(fake_module)
    fake_config = SimpleNamespace(
        semantic_adjudication_review=True,
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        semantic_adjudication_model_stack=["adjudicator-model"],
        max_prompt_chars=120000,
    )
    result, model_label, tier = fake_module.openrouter_review_with_hybrid_first_pass(
        {"number": 1},
        [],
        "diff",
        {},
        fake_config,
        reporter,
        [],
        {},
        "",
        "deep-forced",
        "",
        object(),
    )
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Predicate accepts rejected evidence"
    assert result["_semantic_adjudication_input_candidates"] == 2
    assert result["_semantic_adjudication_output_findings"] == 1
    assert "semantic-adjudicator=adjudicator-model" in model_label
    assert tier == "default, default"
    assert "prompts/06-semantic-adjudication-prompt.txt" in debug_text
    assert "responses/06-semantic-adjudication-result.json" in debug_json
    assert any(stage == "semantic-adjudication" and "input=2; retained=1" in message for stage, message in reporter.events)

    verifier_prompt = v21._verifier_prompt(
        {
            "title": "Candidate",
            "severity": "medium",
            "confidence": 0.95,
            "body": "Candidate body",
            "validation": "Candidate validation",
        },
        "probe.py",
        1,
        "return True",
        "return True\n",
        review.base,
        config,
    )
    assert v35.VERIFIER_FALSIFICATION_BLOCK in verifier_prompt

    # Reapplying the real v35 module must not stack wrappers.
    hybrid_before = review.openrouter_review_with_hybrid_first_pass
    verifier_before = v21._verifier_prompt
    v35.apply_pareto_context_module(review)
    assert review.openrouter_review_with_hybrid_first_pass is hybrid_before
    assert v21._verifier_prompt is verifier_before

    print("dcoir_review_required_runtime_patch_v35_selftest passed")


if __name__ == "__main__":
    main()
