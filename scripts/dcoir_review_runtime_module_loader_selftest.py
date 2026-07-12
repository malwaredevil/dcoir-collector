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

EXPECTED_EXPORTS = {
    "openrouter_pr_review": ("Config", "GitHubClient", "ProgressReporter", "sanitize_text"),
    "openrouter_pr_review_hardened": ("RISK_SENTINEL_RULES", "build_prompt", "openrouter_review"),
    "openrouter_pr_review_pareto_context": (
        "detect_risk_sentinels",
        "rank_findings_for_required_budget",
        "openrouter_review_with_hybrid_first_pass",
    ),
}


def main() -> None:
    for layer, pairs in EXPECTED_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        paths = RuntimeSegmentLoader(layer).segment_paths()
        assert all(path.is_file() for path in paths), layer
        assert all(path.stat().st_size <= 15_000 for path in paths), layer
        for first, second in pairs:
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for module_name, exports in EXPECTED_EXPORTS.items():
        module = importlib.import_module(module_name)
        missing = [name for name in exports if not hasattr(module, name)]
        assert not missing, (module_name, missing)

    print("DCOIR Review runtime module-loader selftest passed")


if __name__ == "__main__":
    main()
