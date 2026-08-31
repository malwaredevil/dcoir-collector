#!/usr/bin/env python3
"""Regression checks for connector-sized DCOIR Review runtime segments."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dcoir_review.module_loader import LAYER_SEGMENTS, RuntimeSegmentLoader

MAX_SEGMENT_SOURCE_BYTES = 15_000

EXPECTED_ADJACENCY = {
    "base": (
        ("base/part_01_core_config_github.py", "base/part_01a_progress_diff.py"),
        ("base/part_03_redaction_shell.py", "base/part_03a_redaction_command_shell.py"),
    ),
    "hardened": (
        ("hardened/part_01_rules.py", "hardened/part_01a_finding_rules.py"),
        ("hardened/part_03_sentinels_prompt.py", "hardened/part_03a_fallback_prompt.py"),
        ("hardened/part_04_quality_provider.py", "hardened/part_04a_provider.py"),
    ),
    "pareto_context": (
        ("pareto_context/part_04_sentinels_modes_context.py", "pareto_context/part_04a_ranking_context.py"),
        ("pareto_context/part_05_ranking_per_file_review.py", "pareto_context/part_05a_hybrid_review.py"),
    ),
}

PATCH_ADJACENCY = {
    "dcoir_review_runtime_patches": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_strict_runtime_patches": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_required_runtime_patches": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_required_runtime_patch_v2": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v3": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v4": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v5": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v6": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v7": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v8": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v9_core": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v9_selection": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v10": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v11": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_required_runtime_patch_v13": (("part_02.py", "part_02a.py"),),
    "dcoir_review_required_runtime_patch_v14": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v16": (("part_01.py", "part_01a.py"),),
}

SELFTEST_ADJACENCY = {
    "base_selftest": (("part_01.py", "part_01a.py"),),
    "hardened_selftest": (("part_01.py", "part_01a.py"),),
    "pareto_context_selftest": (("part_01.py", "part_01a.py"), ("part_04.py", "part_04a.py")),
    "dcoir_review_required_runtime_patch_v14_selftest": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v9_selftest": (("part_01.py", "part_02.py"),),
    "openrouter_pr_review_pareto_context_regression_selftest": (("part_02.py", "part_02a.py"),),
}

EXPECTED_EXPORTS = {
    "openrouter_pr_review": ("Config", "GitHubClient", "ProgressReporter", "sanitize_text"),
    "openrouter_pr_review_hardened": ("RISK_SENTINEL_RULES", "build_prompt", "openrouter_review"),
    "openrouter_pr_review_pareto_context": (
        "detect_risk_sentinels",
        "rank_findings_for_required_budget",
        "openrouter_review_with_hybrid_first_pass",
    ),
}


def normalized_source_size(path: Path) -> int:
    """Measure source bytes independent of Git checkout line-ending conversion."""
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def assert_segment_registry_is_complete() -> None:
    """Reject missing, duplicate, or unregistered runtime segment files."""
    loader_root = SCRIPTS / "dcoir_review"
    registered = [segment for segments in LAYER_SEGMENTS.values() for segment in segments]
    actual = [
        path.relative_to(loader_root).as_posix()
        for path in loader_root.rglob("*.py")
        if path.name not in {"__init__.py", "entrypoint.py", "module_loader.py"}
    ]

    assert len(registered) == len(set(registered)), "duplicate module-loader segment registration"
    assert set(registered) == set(actual), {
        "missing": sorted(set(registered) - set(actual)),
        "orphaned": sorted(set(actual) - set(registered)),
    }


def main() -> None:
    assert_segment_registry_is_complete()

    for layer, pairs in EXPECTED_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        paths = RuntimeSegmentLoader(layer).segment_paths()
        assert all(path.is_file() for path in paths), layer
        assert all(normalized_source_size(path) <= MAX_SEGMENT_SOURCE_BYTES for path in paths), layer
        for first, second in pairs:
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for layer, pairs in PATCH_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        paths = RuntimeSegmentLoader(layer).segment_paths()
        assert all(path.is_file() for path in paths), layer
        assert all(normalized_source_size(path) <= MAX_SEGMENT_SOURCE_BYTES for path in paths), layer
        directory = Path(segments[0]).parent.as_posix()
        for first_name, second_name in pairs:
            first = f"{directory}/{first_name}"
            second = f"{directory}/{second_name}"
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for layer, pairs in SELFTEST_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        paths = RuntimeSegmentLoader(layer).segment_paths()
        assert all(path.is_file() for path in paths), layer
        assert all(normalized_source_size(path) <= MAX_SEGMENT_SOURCE_BYTES for path in paths), layer
        directory = Path(segments[0]).parent.as_posix()
        for first_name, second_name in pairs:
            first = f"{directory}/{first_name}"
            second = f"{directory}/{second_name}"
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for module_name, exports in EXPECTED_EXPORTS.items():
        module = importlib.import_module(module_name)
        missing = [name for name in exports if not hasattr(module, name)]
        assert not missing, (module_name, missing)

    print("DCOIR Review runtime module-loader selftest passed")


if __name__ == "__main__":
    main()
