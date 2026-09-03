#!/usr/bin/env python3
"""State-safety regression checks for Architecture-B semantic-result reuse (v43)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v41_scope as v41_scope
import dcoir_review_required_runtime_patch_v43 as v43
import dcoir_review_required_runtime_patch_v43_reuse as reuse


def _record(path: str, head: str) -> dict[str, object]:
    return {
        "contract": reuse.REUSE_CONTRACT,
        "runtime_version": reuse.VERSION,
        "path": path,
        "outcome": "complete",
        "result": {"summary": f"result for {path}", "findings": []},
        "reuse_key": f"reuse:{path}",
        "origin_reviewed_head": head,
        "carried_forward_head": head,
    }


def _state(prior_head: str) -> dict[str, object]:
    return {
        "prior_records": {
            "src/unchanged.py": _record("src/unchanged.py", prior_head),
            "src/changed.py": _record("src/changed.py", prior_head),
            "src/old_name.py": _record("src/old_name.py", prior_head),
        },
        "trusted_prior_head": prior_head,
        "load_reason": "trusted-prior-manifest-loaded",
        "decisions": {},
        "carry_forward_decisions": {},
        "records": {},
        "carried_forward_record_count": 0,
        "lock": __import__("threading").Lock(),
    }


def _scope(prior_head: str, current_head: str) -> dict[str, object]:
    return {
        "source": "incremental-reviewed-head",
        "fallback_reason": "",
        "compare_status": "ahead",
        "prior_reviewed_head_sha": prior_head,
        "current_head_sha": current_head,
        "files": [
            {"filename": "src/changed.py", "status": "modified"},
            {
                "filename": "src/new_name.py",
                "previous_filename": "src/old_name.py",
                "status": "renamed",
            },
        ],
    }


def _assert_persistence_refuses_rewritten_semantics() -> None:
    config = SimpleNamespace(debug=False)
    manifest = {
        "contract": reuse.REUSE_CONTRACT,
        "outcome": "complete",
        "reviewed_head": "1" * 40,
        "records": [
            {
                "path": "src/a.py",
                "result": {"summary": "literal @identity must remain exact", "findings": []},
            }
        ],
    }
    module = SimpleNamespace(
        base=SimpleNamespace(
            sanitize_debug_json_value=lambda value, _config: {
                **value,
                "records": [
                    {
                        **value["records"][0],
                        "result": {"summary": "rewritten", "findings": []},
                    }
                ],
            }
        )
    )
    old_dir = os.environ.get(reuse.ARTIFACT_DIR_ENV)
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ[reuse.ARTIFACT_DIR_ENV] = temp_dir
            assert reuse.persist_manifest(module, config, manifest) is False
            assert not Path(temp_dir, reuse.MANIFEST_PATH).exists()
    finally:
        if old_dir is None:
            os.environ.pop(reuse.ARTIFACT_DIR_ENV, None)
        else:
            os.environ[reuse.ARTIFACT_DIR_ENV] = old_dir


def _assert_incremental_carry_forward_is_exact() -> None:
    prior_head = "1" * 40
    current_head = "2" * 40
    gh = SimpleNamespace()
    setattr(gh, v41_scope.SCOPE_CACHE_ATTR, _scope(prior_head, current_head))
    state = _state(prior_head)
    carried = v43._carry_forward_unchanged_records(
        gh, {"head": {"sha": current_head}}, state
    )
    assert carried == 1
    assert set(state["records"]) == {"src/unchanged.py"}
    carried_record = state["records"]["src/unchanged.py"]
    assert carried_record["carried_forward_head"] == current_head
    assert carried_record["carry_forward_reason"] == "unchanged-in-incremental-frontier"
    assert state["carry_forward_decisions"]["src/unchanged.py"]["decision"] == "carried-forward"
    assert "src/changed.py" not in state["records"]
    assert "src/old_name.py" not in state["records"]


def _assert_untrusted_scopes_never_carry() -> None:
    prior_head = "1" * 40
    current_head = "2" * 40
    mutations = (
        None,
        {**_scope(prior_head, current_head), "source": "cumulative-full-pr"},
        {**_scope(prior_head, current_head), "fallback_reason": "unsafe fallback"},
        {**_scope(prior_head, current_head), "compare_status": "behind"},
        {**_scope(prior_head, current_head), "prior_reviewed_head_sha": "9" * 40},
        {**_scope(prior_head, current_head), "current_head_sha": "9" * 40},
    )
    for scope in mutations:
        gh = SimpleNamespace()
        if scope is not None:
            setattr(gh, v41_scope.SCOPE_CACHE_ATTR, scope)
        state = _state(prior_head)
        assert v43._carry_forward_unchanged_records(
            gh, {"head": {"sha": current_head}}, state
        ) == 0
        assert state["records"] == {}
        assert state["carry_forward_decisions"] == {}


def _assert_invalid_prior_records_never_carry() -> None:
    prior_head = "1" * 40
    current_head = "2" * 40
    gh = SimpleNamespace()
    setattr(gh, v41_scope.SCOPE_CACHE_ATTR, _scope(prior_head, current_head))
    invalid = {
        "bad-contract.py": {**_record("bad-contract.py", prior_head), "contract": "old"},
        "partial.py": {**_record("partial.py", prior_head), "outcome": "partial"},
        "bad-result.py": {**_record("bad-result.py", prior_head), "result": []},
        "stale.py": {**_record("stale.py", prior_head), "carried_forward_head": "9" * 40},
    }
    state = _state(prior_head)
    state["prior_records"] = invalid
    assert v43._carry_forward_unchanged_records(
        gh, {"head": {"sha": current_head}}, state
    ) == 0
    assert state["records"] == {}


def main() -> None:
    _assert_persistence_refuses_rewritten_semantics()
    _assert_incremental_carry_forward_is_exact()
    _assert_untrusted_scopes_never_carry()
    _assert_invalid_prior_records_never_carry()
    print("dcoir_review_required_runtime_patch_v43_state_selftest passed")


if __name__ == "__main__":
    main()
