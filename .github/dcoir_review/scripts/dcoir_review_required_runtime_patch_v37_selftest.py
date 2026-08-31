#!/usr/bin/env python3
"""Regression checks for DCOIR Review v37 adjudicator shape normalization."""

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


def _finding(line: int = 12, title: str = "Predicate accepts rejected evidence") -> dict[str, Any]:
    return {
        "path": "probe.py",
        "line": line,
        "severity": "high",
        "confidence": 0.93,
        "title": title,
        "body": "A complete counterexample demonstrates the changed predicate accepting evidence that the surrounding proposition rejects.",
        "validation": "Trace the counterexample through the changed positive-evidence branch and confirm the branch returns true.",
        "suggested_replacement": "",
    }


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v37" in names
    assert names.index("dcoir_review_required_runtime_patch_v36") < names.index("dcoir_review_required_runtime_patch_v37")
    assert names.index("dcoir_review_required_runtime_patch_v37") < names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v35 = importlib.import_module("dcoir_review_required_runtime_patch_v35")
    v37 = importlib.import_module("dcoir_review_required_runtime_patch_v37")

    assert getattr(review, v37.APPLIED_MARKER, False) is True
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False

    fake_hardened = SimpleNamespace(ReviewQualityError=RuntimeError)
    fake_module = SimpleNamespace(
        hardened=fake_hardened,
        rank_findings_for_required_budget=lambda findings, limit: findings[:limit],
    )

    canonical = {"summary": "none", "findings": []}
    assert v37._normalize_adjudicator_result(fake_module, canonical) is canonical

    flat = _finding()
    normalized = v37._normalize_adjudicator_result(fake_module, flat)
    assert len(normalized["findings"]) == 1
    assert normalized["findings"][0]["title"] == flat["title"]
    assert normalized[v37.FLAT_SHAPE_MARKER] == v37.FLAT_SHAPE_VALUE

    capped_flat = v35._cap_adjudicated_findings(fake_module, flat, 8)
    assert len(capped_flat["findings"]) == 1
    assert capped_flat[v37.FLAT_SHAPE_MARKER] == v37.FLAT_SHAPE_VALUE

    many = {"findings": [_finding(index, f"finding-{index}") for index in range(1, 4)]}
    capped_many = v35._cap_adjudicated_findings(fake_module, many, 2)
    assert len(capped_many["findings"]) == 2
    assert capped_many["_semantic_adjudication_overflow_trimmed"] == 1

    malformed = _finding()
    malformed.pop("validation")
    try:
        v35._cap_adjudicated_findings(fake_module, malformed, 8)
    except RuntimeError as exc:
        assert "complete flat single finding" in str(exc)
    else:
        raise AssertionError("partial flat adjudicator result did not fail closed")

    try:
        v35._cap_adjudicated_findings(fake_module, {"findings": "not-a-list"}, 8)
    except RuntimeError as exc:
        assert "non-list findings" in str(exc)
    else:
        raise AssertionError("non-list findings envelope did not fail closed")

    # Reproduce the live loss seam through v35's actual semantic-adjudication
    # wrapper: the model returns one complete finding as the top-level object.
    debug_json: dict[str, Any] = {}
    reporter = _Reporter()

    def fake_detector(*args, **kwargs):
        return ({"summary": "detector", "findings": [_finding(10, "candidate")]}, "detector-model", "default")

    def fake_openrouter(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        return (_finding(12, "Recovered flat root cause"), "adjudicator-model", "default")

    wrapper_hardened = SimpleNamespace(
        openrouter_review=fake_openrouter,
        result_findings=lambda result: list(result.get("findings", [])),
        write_debug_text_artifact_safely=lambda *args, **kwargs: None,
        write_debug_json_artifact_safely=lambda cfg, path, payload: debug_json.__setitem__(path, payload),
        ReviewQualityError=RuntimeError,
    )
    wrapper_module = SimpleNamespace(
        openrouter_review_with_hybrid_first_pass=fake_detector,
        hardened=wrapper_hardened,
        base=SimpleNamespace(sanitize_text=lambda text, cfg: str(text)),
        build_prompt=lambda *args, **kwargs: "PR EVIDENCE",
        rank_findings_for_required_budget=lambda findings, limit: findings[:limit],
    )
    v35._patch_semantic_adjudication(wrapper_module)
    wrapper_config = SimpleNamespace(
        semantic_adjudication_review=True,
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        semantic_adjudication_model_stack=["adjudicator-model"],
        max_prompt_chars=120000,
    )
    result, model_label, tier = wrapper_module.openrouter_review_with_hybrid_first_pass(
        {"number": 1},
        [],
        "diff",
        {},
        wrapper_config,
        reporter,
        [],
        {},
        "",
        "deep-forced",
        "",
        object(),
    )
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Recovered flat root cause"
    assert result[v37.FLAT_SHAPE_MARKER] == v37.FLAT_SHAPE_VALUE
    assert result["_semantic_adjudication_output_findings"] == 1
    assert "semantic-adjudicator=adjudicator-model" in model_label
    assert tier == "default, default"
    artifact = debug_json["responses/06-semantic-adjudication-result.json"]
    assert artifact["output_finding_count"] == 1
    assert artifact["result"][v37.FLAT_SHAPE_MARKER] == v37.FLAT_SHAPE_VALUE
    assert any(stage == "semantic-adjudication" and "retained=1" in message for stage, message in reporter.events)

    # Reapplying v37 must not stack the v35 cap wrapper.
    cap_before = v35._cap_adjudicated_findings
    v37.apply_pareto_context_module(review)
    assert v35._cap_adjudicated_findings is cap_before

    print("dcoir_review_required_runtime_patch_v37_selftest passed")


if __name__ == "__main__":
    main()
