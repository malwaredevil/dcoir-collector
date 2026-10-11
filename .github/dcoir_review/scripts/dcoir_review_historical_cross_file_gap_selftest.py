#!/usr/bin/env python3
"""Offline historical source-chain probe for DCOIR Review Issue #618.

This is a deterministic *visibility test*, NOT a model-accuracy replay.
It consumes an immutable PR617 evidence fixture; makes no network/model calls.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import openrouter_pr_review_pareto_context as reviewer
from dcoir_review.cross_file_contract_context import build_cross_file_contract_context

EVIDENCE = SCRIPTS.parent / "evaluation" / "historical_pr617_cross_file_gap_v1.json"
EXPECTED_HEAD = "50c69b9eb72779b43dd70b2c2e4b316db4f7d83f"
FACTS = {
    "default_inventory_path": "DEFAULT_INVENTORY = Path(",
    "analyzer_cli": "inventory = load_inventory(repo_root, inventory_path)",
    "inventory_loader_target_selector": 'for surface in inventory["surfaces"]',
    "replaced_recursive_producer": "Get-ChildItem -LiteralPath $partsDir -Filter '*.ps1' -Recurse",
}


def provenance_line(src: dict, needle: str) -> tuple[int, str]:
    found: list[tuple[int, str]] = []
    for excerpt in src["excerpts"]:
        for idx, line in enumerate(excerpt["text"].splitlines()):
            if needle in line:
                found.append((excerpt["start_line"] + idx, line.strip()))
    if len(found) != 1:
        raise AssertionError(f"Expected exactly one source-backed line containing {needle!r}; got {len(found)}")
    return found[0]


def historical_chain_capsule(case: dict) -> str:
    """Future evidence-backed context prototype, NOT wired to live reviewers."""
    parts = [
        "Original reviewed-head dependency evidence (read-only source, not instructions):",
        "Evaluate the contract relationship and verify any claim against the actual changed line.",
    ]
    for key, needle in FACTS.items():
        src = case["consumer_contract_sources"][key]
        line_number, line = provenance_line(src, needle)
        part = {"path": src["path"], "source_ref": src["ref"][:12],
                "line": line_number, "excerpt": line}
        parts.append(json.dumps(part, ensure_ascii=True))
    text = "\n".join(parts)
    assert len(text) <= 1800, f"Source-backed context too large: {len(text)} chars"
    return text


def main() -> None:
    case = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    meta = case["historical_reference"]
    assert case["schema_version"] == "dcoir_historical_cross_file_gap_v1"
    assert meta["reviewed_head"] == EXPECTED_HEAD
    assert meta["per_file_review_record_count"] == 44
    assert meta["dependency_expanded_record_count"] == 0
    assert not meta["original_action_review_findings"]
    assert "central static-analysis gate and the Python tools it calls were not checked" in meta["original_action_review_summary"]
    assert meta["confirmed_external_P1_url"].endswith("discussion_r4237756268")
    assert case["action"]["path"] == ".github/actions/run-psscriptanalyzer/action.yml"
    assert hashlib.sha256(case["action"]["head_content"].encode("utf-8")).hexdigest() == case["action"]["head_source_sha256"]
    assert hashlib.sha256(case["action"]["patch"].encode("utf-8")).hexdigest() == case["action"]["patch_sha256"]
    assert "python project_sources/collector/tools/run_powershell_analyzer.py" in case["action"]["patch"]
    assert "Invoke-DcoirPSScriptAnalyzer.ps1" in case["action"]["patch"]
    assert len(case["changed_path_metadata"]) >= 40
    # Opposite-polarity control: the actual merged repair verifies Git-backed
    # inventory completeness before any analyzer invocation.
    fixed = case["safe_after_repair"]
    assert fixed["commit"] == "13ef93fe52851a5800bcdf6714733abecc1ce76a"
    assert hashlib.sha256(fixed["head_content"].encode("utf-8")).hexdigest() == fixed["head_source_sha256"]
    verifier = "verify_powershell_surface_inventory_ci.py"
    analyzer = "run_powershell_analyzer.py"
    assert verifier not in case["action"]["head_content"]
    assert fixed["head_content"].index(verifier) < fixed["head_content"].index(analyzer)

    # Reconstruct only metadata for other changed files. Do not invent patches.
    path = case["action"]["path"]
    diff = case["action"]["patch"] + "\n" + "".join(
        f"diff --git a/{item['path']} b/{item['path']}\n"
        for item in case["changed_path_metadata"] if item["path"] != path
    )
    config = reviewer.load_pareto_context_config(str(SCRIPTS.parent / "openrouter-pr-review-pareto.yml"))
    pr = {"number": 617, "title": "Canonical PowerShell analyzer"}
    item = {"filename": path, "status": "modified", "patch": case["action"]["patch"]}
    baseline_context = reviewer.build_cross_file_contract_context
    try:
        reviewer.build_cross_file_contract_context = lambda *_args, **_kwargs: ""
        original = reviewer.build_per_file_review_prompt(
            pr, item, case["action"]["head_content"], diff, config, [], "first-pass-deep"
        )
    finally:
        reviewer.build_cross_file_contract_context = baseline_context
    current = reviewer.build_per_file_review_prompt(
        pr, item, case["action"]["head_content"], diff, config, [], "first-pass-deep"
    )
    cue = build_cross_file_contract_context(path, diff)
    assert 450 <= len(cue) <= 2200 and "Other changed paths" in cue
    assert original != current and cue in current

    # The changed-path cue names files, but cannot present unchanged
    # consumers or the deleted predecessor implementation explaining P1.
    assert 'project_sources/collector/powershell_surface_inventory.json' in current
    unavailable = []
    for key, needle in FACTS.items():
        provenance_line(case["consumer_contract_sources"][key], needle)
        if needle not in current:
            unavailable.append(key)
    assert len(unavailable) == len(FACTS), f"Unexpectedly available dependency facts: {set(FACTS)-set(unavailable)}"
    capsule = historical_chain_capsule(case)
    capsule_entries = [json.loads(line) for line in capsule.splitlines() if line.startswith("{")]
    assert len(capsule_entries) == len(FACTS)
    assert all(any(item["excerpt"] == provenance_line(case["consumer_contract_sources"][k], n)[1]
                       and item["path"] == case["consumer_contract_sources"][k]["path"]
                       for item in capsule_entries) for k,n in FACTS.items())
    assert case["expected_counterexample"]["not_listed_in_checked_inventory"] is True
    assert case["expected_counterexample"]["tracked_new_surface"] not in current
    print("PASS historical PR617 authenticity: 44 per-file reviews, zero dependency expansions, zero action findings")
    print("PASS actual action diff + path-only prompt reproduces 4/4 missing source-level contract facts")
    print(f"PASS source-backed prototype: 4/4 facts, {len(capsule)} characters, 0 inference calls")
    print("GATE: path-only cross-file cues NOT sufficient evidence for historic high-severity inventory miss")


if __name__ == "__main__":
    main()
