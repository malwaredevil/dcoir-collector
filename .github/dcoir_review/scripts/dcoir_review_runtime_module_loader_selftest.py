#!/usr/bin/env python3
"""Regression checks for connector-sized DCOIR Review runtime segments."""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import dcoir_review_architecture_inventory as architecture_inventory
from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review.module_loader import LAYER_SEGMENTS, RuntimeSegmentLoader

MAX_SEGMENT_SOURCE_BYTES = 15_000
MAX_NUMBERED_PRODUCTION_PATCH_VERSION = 58
NUMBERED_PRODUCTION_PATCH_RE = re.compile(
    r"^dcoir_review_required_runtime_patch_v(?P<version>\d+)(?:$|_)"
)

# One pre-existing provider segment is already tracked as architecture debt in
# #550. Keep the exception explicit and size-frozen while the consolidated
# provider architecture replaces it; all other runtime segments stay subject
# to the normal connector-safe limit.
LEGACY_OVERSIZE_SEGMENT_MAX_BYTES = {
    "hardened/part_04a_provider.py": 19_159,
}

# Every maintained Python module under scripts/dcoir_review has one explicit
# ownership mode: concatenated runtime segment, ordinary direct-import module,
# or package marker (__init__.py). This keeps orphan detection fail-closed
# without forcing ordinary helper/selftest modules into LAYER_SEGMENTS.
DIRECT_IMPORT_MODULES = (
    "entrypoint.py",
    "module_loader.py",
    "status.py",
    "pareto_context/credit_aware_concurrency.py",
    "selftests/provider_transport/fixtures.py",
    "selftests/provider_transport/http_errors.py",
)

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

PRODUCTION_PATCH_GROUPS = (
    "patch_module_names",
    "terminal_patch_module_names",
    "post_terminal_patch_module_names",
    "candidate_integrity_patch_module_names",
    "stage_local_patch_module_names",
    "execution_policy_patch_module_names",
    "telemetry_patch_module_names",
    "post_telemetry_patch_module_names",
)


def normalized_source_size(path: Path) -> int:
    """Measure source bytes independent of Git checkout line-ending conversion."""
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def production_patch_module_names() -> tuple[str, ...]:
    """Return the complete currently registered production patch sequence."""
    entrypoint = DcoirReviewEntrypoint()
    names: list[str] = []
    for group_name in PRODUCTION_PATCH_GROUPS:
        names.extend(getattr(entrypoint, group_name))
    return tuple(names)


def assert_numbered_patch_freeze_before_cutover() -> None:
    """Enforce the #550 no-v59 production freeze until the chain is retired."""
    numbered: dict[str, int] = {}
    for module_name in production_patch_module_names():
        match = NUMBERED_PRODUCTION_PATCH_RE.match(module_name)
        if match is not None:
            numbered[module_name] = int(match.group("version"))

    assert numbered, "expected historical numbered production patches before #550 cutover"
    observed_max = max(numbered.values())
    assert observed_max == MAX_NUMBERED_PRODUCTION_PATCH_VERSION, {
        "numbered_patch_freeze_violation": sorted(
            name
            for name, version in numbered.items()
            if version > MAX_NUMBERED_PRODUCTION_PATCH_VERSION
        ),
        "expected_max_version": MAX_NUMBERED_PRODUCTION_PATCH_VERSION,
        "observed_max_version": observed_max,
    }
    assert "dcoir_review_required_runtime_patch_v58" in numbered


def assert_patch_inventory_is_source_complete() -> None:
    """Require the #550 static inventory to cover every active patch root."""
    inventory = architecture_inventory.build_inventory()
    assert tuple(inventory["production_patch_sequence"]) == production_patch_module_names()
    assert inventory["production_patch_count"] == len(production_patch_module_names())
    assert inventory["inventory_module_count"] >= inventory["production_patch_count"]
    assert not inventory["missing_modules"], inventory["missing_modules"]
    assert inventory["max_numbered_version"] == MAX_NUMBERED_PRODUCTION_PATCH_VERSION


def assert_segment_source_sizes(paths: tuple[Path, ...], layer: str) -> None:
    """Enforce the normal size cap plus narrowly frozen legacy debt."""
    loader_root = SCRIPTS / "dcoir_review"
    for path in paths:
        relative_path = path.relative_to(loader_root).as_posix()
        source_bytes = normalized_source_size(path)
        legacy_cap = LEGACY_OVERSIZE_SEGMENT_MAX_BYTES.get(relative_path)
        if legacy_cap is None:
            assert source_bytes <= MAX_SEGMENT_SOURCE_BYTES, (
                layer,
                relative_path,
                source_bytes,
                MAX_SEGMENT_SOURCE_BYTES,
            )
            continue
        assert source_bytes > MAX_SEGMENT_SOURCE_BYTES, {
            "stale_legacy_oversize_waiver": relative_path,
            "source_bytes": source_bytes,
        }
        assert source_bytes <= legacy_cap, {
            "legacy_oversize_segment_grew": relative_path,
            "source_bytes": source_bytes,
            "legacy_cap": legacy_cap,
        }


def assert_segment_registry_is_complete() -> None:
    """Reject missing, duplicate, or unowned maintained Python modules."""
    loader_root = SCRIPTS / "dcoir_review"
    registered = [segment for segments in LAYER_SEGMENTS.values() for segment in segments]
    direct_imports = list(DIRECT_IMPORT_MODULES)
    actual = []
    for path in loader_root.rglob("*.py"):
        relative_path = path.relative_to(loader_root).as_posix()
        if path.name == "__init__.py":
            continue
        actual.append(relative_path)

    assert len(registered) == len(set(registered)), "duplicate module-loader segment registration"
    assert len(direct_imports) == len(set(direct_imports)), "duplicate direct-import module ownership"
    overlap = set(registered) & set(direct_imports)
    assert not overlap, {"ambiguous_ownership": sorted(overlap)}

    legacy_oversize = set(LEGACY_OVERSIZE_SEGMENT_MAX_BYTES)
    assert legacy_oversize <= set(registered), {
        "legacy_oversize_waiver_not_registered": sorted(legacy_oversize - set(registered)),
    }
    assert not (legacy_oversize & set(direct_imports)), {
        "legacy_oversize_waiver_direct_import_overlap": sorted(legacy_oversize & set(direct_imports)),
    }

    declared = set(registered) | set(direct_imports)
    assert declared == set(actual), {
        "missing": sorted(declared - set(actual)),
        "orphaned": sorted(set(actual) - declared),
    }


def main() -> None:
    assert_numbered_patch_freeze_before_cutover()
    assert_patch_inventory_is_source_complete()
    assert_segment_registry_is_complete()

    for layer in LAYER_SEGMENTS:
        paths = RuntimeSegmentLoader(layer).segment_paths()
        assert all(path.is_file() for path in paths), layer
        assert_segment_source_sizes(paths, layer)

    for layer, pairs in EXPECTED_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        for first, second in pairs:
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for layer, pairs in PATCH_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        directory = Path(segments[0]).parent.as_posix()
        for first_name, second_name in pairs:
            first = f"{directory}/{first_name}"
            second = f"{directory}/{second_name}"
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for layer, pairs in SELFTEST_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
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
