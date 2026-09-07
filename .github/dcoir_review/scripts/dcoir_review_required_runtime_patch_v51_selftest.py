#!/usr/bin/env python3
"""Offline regressions for Architecture-B semantic candidate identity v51."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v51 as v51
from dcoir_review.entrypoint import DcoirReviewEntrypoint


ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = "supporting_assets/review_acceptance_specimen/cache.py"


def patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def config(review):
    return review.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )


def stale_cache_candidate(title_suffix: str = "") -> dict[str, object]:
    return {
        "title": (
            "DecisionCache.get returns cached allow decisions without comparing "
            f"the stored policy_generation{title_suffix}"
        ),
        "body": (
            "CachedDecision stores policy_generation, but get returns entry.allowed "
            "without comparing the current record generation. Authorization decisions "
            "can therefore outlive the policy generation that justified them."
        ),
        "severity": "high",
        "confidence": 0.85,
        "path": CACHE_PATH,
        "line": 22,
        "validation": (
            f"python3 -m py_compile {CACHE_PATH}\n"
            "python3 -m pytest supporting_assets/review_acceptance_specimen"
        ),
    }


def test_free_text_risk_inference_cannot_rewrite_semantic_candidate(review) -> None:
    candidate = stale_cache_candidate()
    inferred = v51._legacy_normalized_key(candidate)
    assert inferred[2], inferred
    assert v51._risk_provenance(candidate, inferred) == ""

    ranked = review.rank_findings_for_required_budget([candidate], config(review))
    assert len(ranked) == 1, ranked
    selected = ranked[0]
    assert selected["title"] == candidate["title"]
    assert selected["body"] == candidate["body"]
    assert selected["validation"] == candidate["validation"]
    assert "policy_generation" in str(selected["body"])
    assert selected.get(v51.CANDIDATE_ID_FIELD)
    semantic_key = selected.get(v51.SEMANTIC_KEY_FIELD)
    assert isinstance(semantic_key, list) and len(semantic_key) == 3, selected
    assert str(semantic_key[2]).startswith(v51.SEMANTIC_KIND_PREFIX)
    assert "fix_guidance" not in selected
    assert "suggested_replacement" not in selected


def test_same_site_semantic_candidates_keep_distinct_identity(review) -> None:
    first = stale_cache_candidate(" in the primary lookup")
    second = stale_cache_candidate(" in the fallback lookup")
    second["body"] = (
        "A separate cache-generation invariant at the same changed line can preserve "
        "an obsolete authorization decision after policy_generation advances."
    )
    ranked = review.rank_findings_for_required_budget([first, second], config(review))
    assert len(ranked) == 2, ranked
    ids = [str(item.get(v51.CANDIDATE_ID_FIELD, "")) for item in ranked]
    keys = [tuple(item.get(v51.SEMANTIC_KEY_FIELD, [])) for item in ranked]
    assert len(set(ids)) == 2, ranked
    assert len(set(keys)) == 2, ranked
    assert {item["title"] for item in ranked} == {first["title"], second["title"]}


def test_required_sentinel_same_site_supplements_not_replaces(review) -> None:
    candidate = stale_cache_candidate()
    cfg = config(review)
    ranked = review.rank_findings_for_required_budget([candidate], cfg)
    candidate_id = str(ranked[0][v51.CANDIDATE_ID_FIELD])
    sentinel = SimpleNamespace(
        path=CACHE_PATH,
        line=22,
        text="subprocess.run(command, shell=True)",
        label="Python shell execution",
        detail="Deterministic required-risk signal",
    )

    captured: dict[str, object] = {}
    original_writer = review.hardened.write_debug_json_artifact_safely
    review.hardened.write_debug_json_artifact_safely = (
        lambda _cfg, path, value: captured.__setitem__(path, value)
    )
    try:
        final = review.hardened.add_risk_sentinel_fallback_findings(
            ranked, [sentinel], cfg, []
        )
    finally:
        review.hardened.write_debug_json_artifact_safely = original_writer

    assert len(final) == 2, final
    semantic = [item for item in final if item.get(v51.CANDIDATE_ID_FIELD) == candidate_id]
    assert len(semantic) == 1, final
    assert semantic[0]["title"] == candidate["title"]
    assert semantic[0]["body"] == candidate["body"]
    assert semantic[0][v51.SEMANTIC_KEY_FIELD] == ranked[0][v51.SEMANTIC_KEY_FIELD]

    required_coverage = v51._sentinel_coverage([sentinel])
    required = [
        item
        for item in final
        if item.get(v51.CANDIDATE_ID_FIELD) != candidate_id
        and v51._is_required_selection(item, required_coverage)
    ]
    assert len(required) == 1, final

    manifest = captured[v51.FINAL_SELECTION_ARTIFACT_PATH]
    disposition = next(
        item for item in manifest["dispositions"] if item["candidate_id"] == candidate_id
    )
    assert disposition["disposition"] == "reinserted-after-selector-collision"
    selected_ids = {item["candidate_id"] for item in manifest["selected"] if item["candidate_id"]}
    assert candidate_id in selected_ids


def test_explicit_risk_provenance_keeps_required_risk_behavior(review) -> None:
    path = "src/runner.py"
    line = 14
    risk_kind = v5.PYTHON_SHELL_EXEC
    candidate = {
        "title": "Caller-controlled shell execution",
        "body": "Caller-controlled command text is passed through a shell.",
        "severity": "critical",
        "confidence": 0.99,
        "path": path,
        "line": line,
        "_anchored_line_text": "subprocess.run(command, shell=True)",
        "_risk_sentinel_key": [path, line, risk_kind],
        "_risk_sentinel_kind": risk_kind,
        "validation": f"python3 -m py_compile {path}",
    }
    inferred = v51._legacy_normalized_key(candidate)
    assert inferred[2], inferred
    assert v51._risk_provenance(candidate, inferred) in {
        "explicit-risk-sentinel-key",
        "anchored-source-line",
    }
    cfg = config(review)
    ranked = review.rank_findings_for_required_budget([candidate], cfg)
    assert len(ranked) == 1, ranked
    assert ranked[0].get(v51.CANDIDATE_ID_FIELD)
    assert not ranked[0].get(v51.SEMANTIC_KEY_FIELD)
    assert ranked[0].get("_risk_sentinel_key") == candidate["_risk_sentinel_key"]

    sentinel = SimpleNamespace(
        path=path,
        line=line,
        text="subprocess.run(command, shell=True)",
        label="Python shell execution",
        detail="Deterministic required-risk signal",
    )
    final = review.hardened.add_risk_sentinel_fallback_findings(
        ranked, [sentinel], cfg, []
    )
    assert len(final) == 1, final
    assert v51._is_required_selection(final[0], v51._sentinel_coverage([sentinel]))


def test_debug_manifest_records_candidate_provenance(review) -> None:
    captured: dict[str, object] = {}
    original_writer = review.hardened.write_debug_json_artifact_safely
    review.hardened.write_debug_json_artifact_safely = (
        lambda _cfg, path, value: captured.__setitem__(path, value)
    )
    try:
        ranked = review.rank_findings_for_required_budget(
            [stale_cache_candidate()], config(review)
        )
    finally:
        review.hardened.write_debug_json_artifact_safely = original_writer
    assert len(ranked) == 1
    manifest = captured[v51.SELECTION_ARTIFACT_PATH]
    assert manifest["schema_version"] == "dcoir_review_v51_candidate_integrity_v1"
    assert manifest["input_candidate_count"] == 1
    record = manifest["candidates"][0]
    assert record["candidate_id"] == ranked[0][v51.CANDIDATE_ID_FIELD]
    assert record["legacy_inferred_kind"]
    assert record["risk_provenance"] == "none"
    assert record["disposition"] == "semantic-identity-protected"
    assert record["selected_by_ranker"] is True
    snapshot = manifest["selected"][0]
    assert snapshot["candidate_id"] == record["candidate_id"]
    assert snapshot["semantic_key"] == ranked[0][v51.SEMANTIC_KEY_FIELD]


def test_production_registration_and_config(review) -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names[-1] == (
        "dcoir_review_required_runtime_patch_v50"
    )
    assert entrypoint.candidate_integrity_patch_module_names == (
        "dcoir_review_required_runtime_patch_v51",
    )
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "semantic_candidate_identity_review: true" in production
    assert "dcoir_review_required_runtime_patch_v51_selftest.py" in production
    loaded = config(review)
    assert loaded.semantic_candidate_identity_review is True
    assert getattr(review, "DCOIR_SEMANTIC_CANDIDATE_IDENTITY_CONTRACT", "").startswith("v51:")


def main() -> None:
    review = patched_review()
    test_free_text_risk_inference_cannot_rewrite_semantic_candidate(review)
    test_same_site_semantic_candidates_keep_distinct_identity(review)
    test_required_sentinel_same_site_supplements_not_replaces(review)
    test_explicit_risk_provenance_keeps_required_risk_behavior(review)
    test_debug_manifest_records_candidate_provenance(review)
    test_production_registration_and_config(review)
    print("dcoir_review_required_runtime_patch_v51_selftest passed")


if __name__ == "__main__":
    main()
