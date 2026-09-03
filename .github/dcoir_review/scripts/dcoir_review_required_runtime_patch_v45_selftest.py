#!/usr/bin/env python3
"""Offline regressions for verifier-authoritative publication v45."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v45 as v45
from dcoir_review.entrypoint import DcoirReviewEntrypoint


ROOT = Path(__file__).resolve().parent.parent
HEAD = "a" * 40


class ReviewQualityError(RuntimeError):
    pass


def finding(title: str = "Verified issue", *, head: str = HEAD) -> dict[str, object]:
    return {
        "path": "src/app.py",
        "line": 7,
        "title": title,
        "body": "Exact evidence.",
        v21.VERIFIER_MARKER: {"supported": True, "head_sha": head, "line": 7},
    }


def review_module(*, old_body: str = "legacy body"):
    artifacts = {}
    parsed = {"verifier_authoritative_publication_review": True}
    module = SimpleNamespace()
    module.base = SimpleNamespace(
        MARKER="<!-- dcoir-review -->",
        REVIEW_DISPLAY_NAME="DCOIR Review",
        short_commit=lambda value: value[:12] if value else "unavailable",
        github_safe_body=lambda value, limit=65535: str(value)[:limit],
    )
    module.hardened = SimpleNamespace(
        ReviewQualityError=ReviewQualityError,
        parse_yaml_like_data=lambda _path: parsed,
        bool_value=lambda data, key, default: data.get(key, default),
        write_debug_json_artifact_safely=lambda _cfg, path, value: artifacts.__setitem__(
            path, value
        ),
        build_review_body_with_unanchored=lambda *_args, **_kwargs: old_body,
    )
    module.load_pareto_context_config = lambda _path: SimpleNamespace()
    module.artifacts = artifacts
    return module


def config(enabled: bool = True):
    return SimpleNamespace(verifier_authoritative_publication_review=enabled)


def capture(module, candidates, verified, head=HEAD):
    return v45._capture_verifier_disposition(
        module, candidates, verified, {"head": {"sha": head}}
    )


def test_zero_published_discards_contradictory_summary() -> None:
    module = review_module(old_body="legacy actionable defect prose")
    v45._patch_review_body(module)
    candidate = {"path": "src/app.py", "line": 7, "title": "Candidate"}
    capture(module, [candidate], [])
    body = module.hardened.build_review_body_with_unanchored(
        {"summary": "Verified actionable defects remain.", "findings": [candidate]},
        [],
        [],
        "model",
        config(),
        HEAD,
    )
    assert "No verifier-supported findings were published" in body
    assert "Published findings: `0`" in body
    assert "Verifier-suppressed candidates: `1`" in body
    assert "Verified actionable defects remain" not in body
    assert "legacy actionable defect prose" not in body
    artifact = module.artifacts[v45.ARTIFACT_PATH]
    assert artifact["model_summary_discarded"] is True
    assert artifact["reviewed_head_sha"] == HEAD


def test_supported_and_downstream_suppressed_counts() -> None:
    module = review_module()
    v45._patch_review_body(module)
    first, second = finding("First"), finding("Second")
    capture(module, [first, second], [first, second])
    body = module.hardened.build_review_body_with_unanchored(
        {"summary": "Untrusted summary", "findings": [first, second]},
        [first],
        [],
        "model",
        config(),
        HEAD,
    )
    assert "Published findings: `1`" in body
    assert "Verifier-supported candidates: `2`" in body
    assert "Post-verifier suppressions: `1`" in body
    assert "Untrusted summary" not in body


def test_unanchored_and_overflow_are_not_rendered(monkey_summary=None) -> None:
    del monkey_summary
    module = review_module(old_body="UNSAFE LEGACY OVERFLOW PROSE")
    v45._patch_review_body(module)
    unanchored = {
        "path": "src/app.py",
        "line": 99,
        "title": "Unverified actionable issue",
        "body": "Must fix immediately.",
    }
    capture(module, [], [])
    body = module.hardened.build_review_body_with_unanchored(
        {"summary": "Another unsafe claim", "findings": [unanchored]},
        [],
        [unanchored],
        "model",
        config(),
        HEAD,
    )
    assert "Unanchored hypotheses not published: `1`" in body
    assert "Unverified actionable issue" not in body
    assert "Must fix immediately" not in body
    assert "UNSAFE LEGACY OVERFLOW PROSE" not in body


def test_missing_or_stale_verifier_evidence_fails_closed() -> None:
    module = review_module()
    v45._patch_review_body(module)
    try:
        module.hardened.build_review_body_with_unanchored({}, [], [], "model", config(), HEAD)
    except ReviewQualityError as exc:
        assert "missing the final verifier disposition" in str(exc)
    else:
        raise AssertionError("missing verifier disposition must fail closed")

    capture(module, [], [], head="b" * 40)
    try:
        module.hardened.build_review_body_with_unanchored({}, [], [], "model", config(), HEAD)
    except ReviewQualityError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("stale verifier disposition must fail closed")

    capture(module, [finding()], [finding()])
    try:
        module.hardened.build_review_body_with_unanchored(
            {}, [{"path": "src/app.py", "line": 7}], [], "model", config(), HEAD
        )
    except ReviewQualityError as exc:
        assert "without exact-head verifier support" in str(exc)
    else:
        raise AssertionError("unverified published finding must fail closed")


def test_rollback_delegates_to_prior_body() -> None:
    module = review_module(old_body="legacy rollback body")
    v45._patch_review_body(module)
    assert (
        module.hardened.build_review_body_with_unanchored(
            {"summary": "legacy"}, [], [], "model", config(False), HEAD
        )
        == "legacy rollback body"
    )


def test_verifier_wrapper_and_config() -> None:
    module = review_module()
    original = v21.verify_findings_for_publication
    stored = getattr(v21, v45._VERIFIER_STORAGE, None)
    had_stored = hasattr(v21, v45._VERIFIER_STORAGE)
    try:
        v21.verify_findings_for_publication = (
            lambda _module, items, _gh, _pr, _cfg, _reporter: items[:1]
        )
        if hasattr(v21, v45._VERIFIER_STORAGE):
            delattr(v21, v45._VERIFIER_STORAGE)
        v45._patch_verifier(module)
        items = [finding("First"), finding("Second")]
        verified = v21.verify_findings_for_publication(
            module, items, SimpleNamespace(), {"head": {"sha": HEAD}}, config(), None
        )
        assert len(verified) == 1
        disposition = getattr(module, v45._DISPOSITION_ATTR)
        assert disposition["verifier_candidate_count"] == 2
        assert disposition["verifier_supported_count"] == 1
        assert disposition["verifier_suppressed_count"] == 1
    finally:
        v21.verify_findings_for_publication = original
        if had_stored:
            setattr(v21, v45._VERIFIER_STORAGE, stored)
        elif hasattr(v21, v45._VERIFIER_STORAGE):
            delattr(v21, v45._VERIFIER_STORAGE)

    v45._patch_config_loader(module)
    loaded = module.load_pareto_context_config("unused.yml")
    assert loaded.verifier_authoritative_publication_review is True


def test_production_registration() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names[-2:] == (
        "dcoir_review_required_runtime_patch_v44",
        "dcoir_review_required_runtime_patch_v45",
    )
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "verifier_authoritative_publication_review: true" in production
    assert "dcoir_review_required_runtime_patch_v45_selftest.py" in production
    review = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(review)
    loaded = review.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )
    assert loaded.verifier_authoritative_publication_review is True
    assert getattr(review, v45._APPLIED_ATTR) is True


def main() -> None:
    test_zero_published_discards_contradictory_summary()
    test_supported_and_downstream_suppressed_counts()
    test_unanchored_and_overflow_are_not_rendered()
    test_missing_or_stale_verifier_evidence_fails_closed()
    test_rollback_delegates_to_prior_body()
    test_verifier_wrapper_and_config()
    test_production_registration()
    print("dcoir_review_required_runtime_patch_v45_selftest passed")


if __name__ == "__main__":
    main()
