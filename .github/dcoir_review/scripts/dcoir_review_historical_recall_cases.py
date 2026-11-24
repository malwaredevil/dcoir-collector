"""Source-backed historical positives and repaired safe controls for Issue #618.

Evaluates real PR617 snapshots, not hypothetical model-visible source. Scoring
labels remain outside review prompts. Never runs git or calls GitHub at runtime.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "evaluation" / "historical_pr617_cross_file_gap_v1.json"
SOURCE_PATH = "project_sources/collector/tools/powershell_analyzer_inventory.py"
ORIGINAL_CASE = "historical-pr617-omitted-tracked-powershell-p1"
SAFE_CASE = "historical-pr617-verified-inventory-control"
BAD_SHA = "50c69b9eb72779b43dd70b2c2e4b316db4f7d83f"
SAFE_SHA = "13ef93fe52851a5800bcdf6714733abecc1ce76a"
SCRIPT = "project_sources/collector/tools/run_powershell_analyzer.py"
VERIFIER = "project_sources/collector/tools/verify_powershell_surface_inventory_ci.py"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cases() -> list[dict[str, Any]]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    history = fixture["historical_reference"]
    repaired = fixture["safe_after_repair"]
    action = fixture["action"]
    assert fixture["schema_version"] == "dcoir_historical_cross_file_gap_v1"
    assert history["reviewed_head"] == BAD_SHA and repaired["commit"] == SAFE_SHA
    assert history["per_file_review_record_count"] == 44
    assert history["dependency_expanded_record_count"] == 0
    assert not history["original_action_review_findings"]
    assert _digest(action["head_content"]) == action["head_source_sha256"]
    assert _digest(action["patch"]) == action["patch_sha256"]
    assert _digest(repaired["head_content"]) == repaired["head_source_sha256"]
    assert _digest(repaired["patch_from_original_head"]) == repaired["patch_sha256"]
    assert "verify_powershell_surface_inventory_ci.py" not in action["head_content"]
    assert repaired["head_content"].index("verify_powershell_surface_inventory_ci.py") < repaired["head_content"].index("run_powershell_analyzer.py")
    for sha, files, hashes in (
        (BAD_SHA, fixture["original_full_dependency_sources"],
         fixture["original_full_dependency_sources_sha256"]),
        (SAFE_SHA, fixture["safe_full_dependency_sources"],
         fixture["safe_full_dependency_sources_sha256"]),
    ):
        assert SCRIPT in files and SOURCE_PATH in files and len(sha) == 40
        assert set(files) == set(hashes)
        assert all(_digest(value) == hashes[path] for path, value in files.items())
    assert VERIFIER in fixture["safe_full_dependency_sources"]
    assert "git ls-files -z" in fixture["safe_full_dependency_sources"][VERIFIER]

    metadata = fixture["changed_path_metadata"]
    assert len(metadata) >= 40
    changed_path_diff_headers = "".join(
        f"diff --git a/{row['path']} b/{row['path']}\n"
        for row in metadata if row["path"] != action["path"]
    )
    common = {
        "focus_path": action["path"],
        "related_path": SOURCE_PATH,
        "historical_provenance": True,
        "provenance_url": "https://github.com/malwaredevil/dcoir-collector/pull/617",
        "match_groups": None,
        "supporting_contract": "HIDDEN_TRUTH_NEVER_APPEARS_IN_MODEL_PROMPTS",
        "counterexample": "HIDDEN_COUNTEREXAMPLE_NEVER_APPEARS_IN_MODEL_PROMPTS",
    }
    defective = {
        **common,
        "id": ORIGINAL_CASE,
        "expected": "finding",
        "severity": "P1",
        "focus_source": action["head_content"],
        "changed_diff": action["patch"] + "\n" + changed_path_diff_headers,
        "expected_anchor": "python project_sources/collector/tools/run_powershell_analyzer.py",
        "match_groups": [
            ["inventory", "manifest", "enumerat"],
            ["tracked", "omitted", "missing", "stale", "unlisted", "not included", "coverage"],
            ["scan", "analy", "verify", "check", "gate", "detect"],
        ],
        "reviewed_head": BAD_SHA,
        "dependency_sources": fixture["original_full_dependency_sources"],
        "caller_sources": {path: item["source"] for path, item in fixture["original_caller_graph_sources"].items()},
        "historical_case_type": "actual-original-review-head",
    }
    safe = {
        **common,
        "id": SAFE_CASE,
        "expected": "clean",
        "severity": None,
        "focus_source": repaired["head_content"],
        "changed_diff": repaired["patch_from_original_head"],
        "expected_anchor": "verify_powershell_surface_inventory_ci.py",
        "reviewed_head": SAFE_SHA,
        "dependency_sources": fixture["safe_full_dependency_sources"],
        "caller_sources": {path: item["source"] for path, item in fixture["safe_caller_graph_sources"].items()},
        "historical_case_type": "actual-repaired-control",
    }
    return [defective, safe]


__all__ = ["cases", "ORIGINAL_CASE", "SAFE_CASE", "BAD_SHA", "SAFE_SHA"]
