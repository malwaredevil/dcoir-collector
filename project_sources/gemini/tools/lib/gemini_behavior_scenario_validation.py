from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from lib.gemini_behavior_scenario_catalog import SCENARIOS

MANIFEST_NAME = "Gemini_Bundle_Source_Manifest.json"
QUICK_START = "00_START_HERE/Gemini_Build_Quick_Start.md.txt"


def load_manifest(source_root: Path) -> Dict:
    return json.loads((source_root / MANIFEST_NAME).read_text(encoding="utf-8"))


def gather_text(paths: List[Path]) -> str:
    parts: List[str] = []
    for path in paths:
        if path.exists() and path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="ignore").lower())
    return "\n".join(parts)


def evaluate_scenario(combined_text: str, config: Dict[str, object]) -> Dict[str, object]:
    all_markers = list(config.get("all_markers", []))
    any_marker_groups = list(config.get("any_marker_groups", []))
    missing_all = [marker for marker in all_markers if marker not in combined_text]
    group_results: List[Dict[str, object]] = []
    for group in any_marker_groups:
        present = [marker for marker in group if marker in combined_text]
        group_results.append({
            "expected_any_of": group,
            "present": present,
            "passed": len(present) > 0,
        })
    success = len(missing_all) == 0 and all(group["passed"] for group in group_results)
    return {
        "success": success,
        "description": config.get("description"),
        "missing_all_markers": missing_all,
        "group_results": group_results,
    }


def validate_behavior_scenarios(source_root: Path, output_dir: Path) -> int:
    source_root = source_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(source_root)
    topology = manifest.get("topology", {})

    source_paths: List[Path] = [source_root / QUICK_START]
    if topology.get("prime_agent_file"):
        source_paths.append(source_root / topology["prime_agent_file"])
    if topology.get("prime_agent_runtime_mode") == "generated_from_chunks":
        for rel in topology.get("prime_agent_chunk_sources", []):
            source_paths.append(source_root / rel)
    for rel in topology.get("sub_agent_files", []):
        source_paths.append(source_root / rel)
    repo_root = source_root.parent.parent.parent
    for rel in manifest.get("knowledge_attachment_sources", []):
        source_paths.append(repo_root / rel)

    discovered_files = sorted({path.as_posix() for path in source_paths if path.exists()})
    combined_text = gather_text(source_paths)

    scenario_results: Dict[str, object] = {}
    errors: List[str] = []
    for name, config in SCENARIOS.items():
        result = evaluate_scenario(combined_text, config)
        scenario_results[name] = result
        if not result["success"]:
            errors.append(f"{name} markers did not satisfy the required scenario expectations")

    report = {
        "success": len(errors) == 0,
        "source_root": str(source_root),
        "bundle_name": manifest.get("bundle_name"),
        "bundle_version": manifest.get("bundle_version"),
        "topology_source": topology.get("topology_source_of_truth", "missing"),
        "scenario_source_files": discovered_files,
        "scenario_count": len(SCENARIOS),
        "scenario_results": scenario_results,
        "errors": errors,
    }
    report_path = output_dir / "validate_dcoir_gemini_behavior_scenarios_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1
