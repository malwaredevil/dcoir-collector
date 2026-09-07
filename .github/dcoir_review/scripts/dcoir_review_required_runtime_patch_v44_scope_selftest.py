#!/usr/bin/env python3
"""Offline regressions for v44 candidate-scoped escalation context."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v44_scope as v44
from dcoir_review.entrypoint import DcoirReviewEntrypoint

ROOT = Path(__file__).resolve().parent.parent


def _config(**overrides):
    defaults = {
        "candidate_scoped_escalation_review": True,
        "candidate_escalation_confidence_margin": 0.10,
        "candidate_escalation_max_paths": 4,
        "candidate_escalation_file_chars": 12000,
        "candidate_escalation_total_context_chars": 48000,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _scope(files: list[dict], *, source: str = "incremental-reviewed-head") -> dict:
    return {
        "source": source,
        "files": files,
        "current_head_sha": "b" * 40,
        "prior_reviewed_head_sha": "a" * 40,
        "compare_status": "ahead",
        "fallback_reason": "",
    }


def test_candidate_path_selection_is_bounded() -> None:
    candidates = [
        {"path": "src/a.py", "line": 1},
        {"path": "src/b.py", "line": 2},
        {"path": "src/a.py", "line": 3},
        {"path": "src/c.py", "line": 4},
    ]
    assert v44._candidate_paths(candidates, 2) == ["src/a.py", "src/b.py"]


def test_scope_subset_requires_changed_paths() -> None:
    scope = _scope(
        [
            {"filename": "src/a.py", "status": "modified"},
            {"filename": "src/b.py", "status": "modified"},
        ]
    )
    subset, reason = v44._candidate_scope_subset(
        scope,
        [{"path": "src/a.py", "line": 1}],
        4,
    )
    assert reason == ""
    assert subset == {"src/a.py"}

    missing, reason = v44._candidate_scope_subset(
        scope,
        [{"path": "src/missing.py", "line": 1}],
        4,
    )
    assert missing is None and reason == "candidate-path-outside-current-scope"


def test_scope_subset_rejects_non_incremental_and_overflow() -> None:
    scope = _scope(
        [{"filename": "src/a.py", "status": "modified"}], source="cumulative-fallback"
    )
    subset, reason = v44._candidate_scope_subset(
        scope,
        [{"path": "src/a.py", "line": 1}],
        4,
    )
    assert subset is None and reason == "candidate-scope-not-incremental-reviewed-head"

    scope = _scope(
        [
            {"filename": "src/a.py", "status": "modified"},
            {"filename": "src/b.py", "status": "modified"},
        ]
    )
    subset, reason = v44._candidate_scope_subset(
        scope,
        [
            {"path": "src/a.py", "line": 1},
            {"path": "src/b.py", "line": 1},
        ],
        1,
    )
    assert subset is None and reason == "candidate-path-cap-exceeded"


def test_selected_head_context_stays_inside_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src"
        src.mkdir()
        (src / "app.py").write_text("print('ok')\n", encoding="utf-8")
        module = SimpleNamespace(
            root_path=lambda value: root / value,
            base=SimpleNamespace(read_text=lambda value: (root / value).read_text(encoding="utf-8")),
        )
        selected, reason = v44._selected_head_context(
            module,
            {"src/app.py"},
            _config(),
        )
        assert reason == ""
        assert selected == {"src/app.py": "print('ok')\n"}


def test_selected_head_context_rejects_unavailable_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        module = SimpleNamespace(
            root_path=lambda value: root / value,
            base=SimpleNamespace(read_text=lambda _value: (_ for _ in ()).throw(FileNotFoundError())),
        )
        missing, reason = v44._selected_head_context(
            module,
            {"src/app.py"},
            _config(),
        )
        assert missing is None and reason == "selected-head-context-unavailable"


def test_config_and_registration() -> None:
    parsed = {
        "candidate_scoped_escalation_review": True,
        "candidate_escalation_confidence_margin": 0.08,
        "candidate_escalation_max_paths": 3,
        "candidate_escalation_file_chars": 9000,
        "candidate_escalation_total_context_chars": 30000,
    }
    module = SimpleNamespace(
        load_pareto_context_config=lambda _path: SimpleNamespace(),
        hardened=SimpleNamespace(
            parse_yaml_like_data=lambda _path: parsed,
            bool_value=lambda data, key, default: data.get(key, default),
        ),
    )
    v44._patch_config_loader(module)
    loaded = module.load_pareto_context_config("unused.yml")
    assert loaded.candidate_scoped_escalation_review is True
    assert loaded.candidate_escalation_confidence_margin == 0.08
    assert loaded.candidate_escalation_max_paths == 3
    assert loaded.candidate_escalation_file_chars == 9000
    assert loaded.candidate_escalation_total_context_chars == 30000

    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names == (
        "dcoir_review_required_runtime_patch_v44",
        "dcoir_review_required_runtime_patch_v45",
        "dcoir_review_required_runtime_patch_v46",
        "dcoir_review_required_runtime_patch_v50",
    )
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "candidate_scoped_escalation_review: true" in production
    assert "dcoir_review_required_runtime_patch_v44_scope_selftest.py" in production
    assert "dcoir_review_required_runtime_patch_v44_selftest.py" in production
    review_module = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(review_module)
    production_config = review_module.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )
    assert production_config.candidate_scoped_escalation_review is True
    assert production_config.candidate_escalation_confidence_margin == 0.10
    assert production_config.candidate_escalation_max_paths == 4
    assert production_config.candidate_escalation_file_chars == 12000
    assert production_config.candidate_escalation_total_context_chars == 48000


def main() -> None:
    test_candidate_path_selection_is_bounded()
    test_scope_subset_requires_changed_paths()
    test_scope_subset_rejects_non_incremental_and_overflow()
    test_selected_head_context_stays_inside_repo()
    test_selected_head_context_rejects_unavailable_file()
    test_config_and_registration()
    print("dcoir_review_required_runtime_patch_v44_scope_selftest passed")


if __name__ == "__main__":
    main()
