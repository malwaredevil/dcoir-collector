#!/usr/bin/env python3
"""Production-stack regression for the stable DCOIR finding verifier."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PROBE_PATH = ".github/dcoir_review/evaluation/live_suggestion_probe.py"
PROBE_SOURCE = '''"""controlled test"""


def is_high_severity(severity: str) -> bool:
    if severity == "critical" or "high":
        return True
    return False
'''
ORDINARY_PATH = ".github/dcoir_review/evaluation/verifier_ordinary_probe.py"
ORDINARY_SOURCE = '''def advertised_even(value: int) -> bool:
    return value % 2 == 1
'''


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, detail: str) -> None:
        self.events.append((stage, detail))


def patched_modules():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v16 = importlib.import_module("dcoir_review_required_runtime_patch_v16")
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    verifier = importlib.import_module("dcoir_review.finding_verifier")
    v16.v9._ensure_prompt_review = lambda _config: None
    return review, v20, verifier


def pr() -> dict:
    return {"head": {"sha": "a" * 40}}


def test_deterministic_core_sentinel_is_evidence_verified_without_model(review, v20, verifier) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    sentinel = review.hardened.RiskSentinel(
        path=PROBE_PATH,
        line=5,
        label="truthy literal branch condition",
        detail="literal branch",
        text='    if severity == "critical" or "high":',
    )
    finding = review.hardened.add_risk_sentinel_fallback_findings([], [sentinel], config, [])[0]
    assert finding["_risk_sentinel_kind"] == v20.PYTHON_TRUTHY_LITERAL_BRANCH

    review.fetch_pr_file_text = lambda _gh, path, _sha: PROBE_SOURCE if path == PROBE_PATH else ""
    original = review.hardened.openrouter_review
    review.hardened.openrouter_review = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("core sentinel must not require model verifier"))
    try:
        verified = verifier.verify_findings_for_publication(review, [finding], object(), pr(), config, Reporter())
    finally:
        review.hardened.openrouter_review = original
    assert len(verified) == 1
    marker = verified[0][verifier.VERIFIER_MARKER]
    assert marker["mode"] == "deterministic-core-sentinel"
    assert marker["supported"] is True


def ordinary_finding() -> dict:
    return {
        "title": "Function contradicts its advertised even-number behavior",
        "severity": "medium",
        "confidence": 0.91,
        "path": ORDINARY_PATH,
        "line": 2,
        "body": "The implementation returns true for odd values instead of even values.",
        "validation": "python3 -m py_compile " + ORDINARY_PATH,
    }


def test_unsupported_model_candidate_is_suppressed(review, verifier) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    review.fetch_pr_file_text = lambda _gh, path, _sha: ORDINARY_SOURCE if path == ORDINARY_PATH else ""
    original = review.hardened.openrouter_review
    review.hardened.openrouter_review = lambda *_args, **_kwargs: (
        {"supported": False, "confidence": 0.97, "evidence": "", "reason": "The supplied file does not establish the advertised contract."},
        "verifier-model",
        "default",
    )
    reporter = Reporter()
    try:
        verified = verifier.verify_findings_for_publication(review, [ordinary_finding()], object(), pr(), config, reporter)
    finally:
        review.hardened.openrouter_review = original
    assert verified == []
    assert any("suppressed=1" in detail for stage, detail in reporter.events if stage == "finding-verifier")


def test_supported_model_candidate_retains_concrete_evidence(review, verifier) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    review.fetch_pr_file_text = lambda _gh, path, _sha: ORDINARY_SOURCE if path == ORDINARY_PATH else ""
    original = review.hardened.openrouter_review
    review.hardened.openrouter_review = lambda *_args, **_kwargs: (
        {
            "supported": True,
            "confidence": 0.94,
            "evidence": "Line 2 compares value % 2 to 1, which is true for odd values.",
            "reason": "The exact line directly supports the candidate claim.",
        },
        "verifier-model",
        "default",
    )
    try:
        verified = verifier.verify_findings_for_publication(review, [ordinary_finding()], object(), pr(), config, Reporter())
    finally:
        review.hardened.openrouter_review = original
    assert len(verified) == 1
    marker = verified[0][verifier.VERIFIER_MARKER]
    assert marker["mode"] == "model-judge"
    assert marker["confidence"] == 0.94
    assert "value % 2" in marker["evidence"]


def test_ambiguous_verifier_output_fails_closed(review, verifier) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    review.fetch_pr_file_text = lambda _gh, path, _sha: ORDINARY_SOURCE if path == ORDINARY_PATH else ""
    original = review.hardened.openrouter_review
    review.hardened.openrouter_review = lambda *_args, **_kwargs: (
        {"supported": "maybe", "confidence": 0.9, "evidence": "unclear", "reason": "ambiguous"},
        "verifier-model",
        "default",
    )
    try:
        try:
            verifier.verify_findings_for_publication(review, [ordinary_finding()], object(), pr(), config, Reporter())
        except review.hardened.ReviewQualityError:
            pass
        else:
            raise AssertionError("ambiguous verifier output must fail closed")
    finally:
        review.hardened.openrouter_review = original



def test_stable_owner_composition() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review.finding_verifier" in names, names
    assert "dcoir_review_required_runtime_patch_v21" not in names, names
    index = names.index("dcoir_review.finding_verifier")
    assert names[index - 1] == "dcoir_review_required_runtime_patch_v20", names[max(0, index - 2):index + 4]
    assert names[index + 1] == "dcoir_review.quality_gate", names[max(0, index - 2):index + 4]

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    verifier = importlib.import_module("dcoir_review.finding_verifier")
    v33 = importlib.import_module("dcoir_review_required_runtime_patch_v33")
    semantic = importlib.import_module("dcoir_review.semantic_evidence_hardening")
    publication = importlib.import_module("dcoir_review.publication_disposition")
    gate = importlib.import_module("dcoir_review.verified_finding_gate")
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    assert verifier.verify_findings_for_publication.__module__ == "dcoir_review.finding_verifier"
    assert config.dcoir_v32_verifier_repair_limit == 8
    assert verifier.verifier_candidate_limit(config) == config.dcoir_v32_verifier_repair_limit
    assert v33.verifier_candidate_limit(config) == verifier.verifier_candidate_limit(config)
    assert not hasattr(v33, "VERIFIER_STORAGE")
    assert not hasattr(semantic, "VERIFIER_STORAGE")
    assert not hasattr(publication, "_VERIFIER_STORAGE")
    assert not hasattr(gate, "_VERIFIER_STORAGE")

def main() -> None:
    test_stable_owner_composition()
    review, v20, verifier = patched_modules()
    test_deterministic_core_sentinel_is_evidence_verified_without_model(review, v20, verifier)
    test_unsupported_model_candidate_is_suppressed(review, verifier)
    test_supported_model_candidate_retains_concrete_evidence(review, verifier)
    test_ambiguous_verifier_output_fails_closed(review, verifier)
    print("dcoir_review_finding_verifier_selftest passed")


if __name__ == "__main__":
    main()
