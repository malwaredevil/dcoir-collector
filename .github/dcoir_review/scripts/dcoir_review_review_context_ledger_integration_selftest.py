#!/usr/bin/env python3
"""Regression checks for review-context enrichment across v42/v43/v44."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v43 as v43
import dcoir_review_required_runtime_patch_v44_telemetry as v44_telemetry


def base_ledger() -> dict[str, object]:
    return {
        "context_fingerprint": "c" * 64,
        "runtime_context_fingerprint": "r" * 64,
        "review_surface": {
            "files": [
                {"path": "src/a.py", "status": "modified", "reuse_allowed": False}
            ]
        },
        "telemetry": {
            "reviewed_file_count": 1,
            "reused_file_count": 0,
            "recomputed_file_count": 1,
            "dependency_expanded_file_count": 0,
            "invalidation_reason": "v42-foundation",
        },
        "reuse": {},
    }


def test_helper_contract() -> None:
    ledger = base_ledger()
    enriched = v42_hooks._review_context_payload_with_ledger(
        {"existing": True}, ledger
    )
    assert enriched["existing"] is True
    assert enriched["semantic_ledger_contract"] == v42_hooks.SEMANTIC_LEDGER_CONTRACT
    assert enriched["semantic_context_fingerprint"] == "c" * 64
    assert enriched["semantic_runtime_context_fingerprint"] == "r" * 64
    assert enriched["semantic_reviewed_file_count"] == 1
    assert enriched["semantic_reused_file_count"] == 0
    assert enriched["semantic_recomputed_file_count"] == 1
    assert enriched["semantic_dependency_expanded_file_count"] == 0
    assert enriched["semantic_invalidation_reason"] == "v42-foundation"

    ledger["telemetry"]["reuse_invalidation_reason"] = ""
    refreshed = v42_hooks._review_context_payload_with_ledger(enriched, ledger)
    assert refreshed["semantic_invalidation_reason"] == ""


def test_v43_refreshes_non_null_review_context() -> None:
    debug: dict[str, object] = {}
    module = SimpleNamespace(
        hardened=SimpleNamespace(
            write_debug_json_artifact_safely=lambda _cfg, path, value: debug.__setitem__(
                path, value
            )
        )
    )
    gh = SimpleNamespace()
    ledger = base_ledger()
    setattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, ledger)
    state = {
        "decisions": {
            "src/a.py": {
                "path": "src/a.py",
                "decision": "reused",
                "reason": "exact-semantic-input-match",
                "reuse_key": "k" * 64,
            }
        },
        "carry_forward_decisions": {},
        "carried_forward_record_count": 0,
        "load_reason": "trusted-prior-manifest-loaded",
    }
    old_context = v42_hooks._LAST_REVIEW_CONTEXT
    old_ledger = v42_hooks._LAST_LEDGER
    try:
        v42_hooks._LAST_REVIEW_CONTEXT = {"existing": True}
        v42_hooks._LAST_LEDGER = ledger
        v43._apply_ledger_telemetry(module, gh, SimpleNamespace(), state)
        context = debug["metadata/review-context.json"]
        assert context["existing"] is True
        assert context["semantic_reused_file_count"] == 1
        assert context["semantic_recomputed_file_count"] == 0
        assert context["semantic_invalidation_reason"] == ""
        assert context["semantic_context_fingerprint"] == "c" * 64
    finally:
        v42_hooks._LAST_REVIEW_CONTEXT = old_context
        v42_hooks._LAST_LEDGER = old_ledger


def test_v44_refreshes_non_null_review_context() -> None:
    debug: dict[str, object] = {}
    module = SimpleNamespace(
        hardened=SimpleNamespace(
            result_findings=lambda result: list(result.get("findings", [])),
            write_debug_json_artifact_safely=lambda _cfg, path, value: debug.__setitem__(
                path, value
            ),
        )
    )
    gh = SimpleNamespace()
    ledger = base_ledger()
    setattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, ledger)
    plan = {
        "mode": "candidate-scoped",
        "reasons": ["near-publication-threshold"],
        "candidate_count": 1,
        "escalated_candidate_keys": [["src/a.py", 4, "candidate"]],
        "selected_paths": ["src/a.py"],
    }
    old_context = v42_hooks._LAST_REVIEW_CONTEXT
    old_ledger = v42_hooks._LAST_LEDGER
    try:
        v42_hooks._LAST_REVIEW_CONTEXT = {"existing": True}
        v42_hooks._LAST_LEDGER = ledger
        v44_telemetry.apply(
            module,
            gh,
            SimpleNamespace(),
            {"findings": []},
            plan,
            "candidate-scoped",
            1,
            1,
            False,
        )
        context = debug["metadata/review-context.json"]
        assert context["existing"] is True
        assert context["semantic_reviewed_file_count"] == 1
        assert context["semantic_reused_file_count"] == 0
        assert context["semantic_recomputed_file_count"] == 1
        assert context["semantic_context_fingerprint"] == "c" * 64
        assert context["semantic_runtime_context_fingerprint"] == "r" * 64
        assert debug["metadata/v44-candidate-escalation.json"]["mode"] == "candidate-scoped"
    finally:
        v42_hooks._LAST_REVIEW_CONTEXT = old_context
        v42_hooks._LAST_LEDGER = old_ledger


def main() -> None:
    test_helper_contract()
    test_v43_refreshes_non_null_review_context()
    test_v44_refreshes_non_null_review_context()
    print("dcoir_review_review_context_ledger_integration_selftest passed")


if __name__ == "__main__":
    main()
