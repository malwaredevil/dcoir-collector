"""Blind-scenario and collector-fixture validation for the production-like harness."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.gemini_production_like_harness_common import add_message, load_json, repo_relative, sha_text
from lib.gemini_production_like_harness_prompts import build_prompt, check_prompt, check_signals


def validate_blind_scenarios(
    root: Path,
    fixtures_root: Path,
    output_dir: Path,
    messages: list[dict[str, str]],
    require_stored_artifacts: bool,
) -> dict[str, Any]:
    blind_root = fixtures_root / "blind"
    index = load_json(blind_root / "index.json")
    prompt_dir = output_dir / "model_visible_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    coverage_tags: set[str] = set()
    for legacy in index.get("matrix", []):
        if len(legacy) >= 3:
            coverage_tags.update(str(item) for item in legacy[:3] if item)

    for reference in index.get("scenarios", []):
        scenario_path = (blind_root / reference["path"]).resolve()
        if not scenario_path.is_file():
            add_message(
                messages,
                "error",
                f"listed scenario is missing: {reference.get('id')}",
                repo_relative(scenario_path, root),
            )
            continue

        scenario = load_json(scenario_path)
        scenario_id = scenario.get("id", reference.get("id"))
        scenario_dir = scenario_path.parent
        for required in ("id", "owner", "family", "visible", "hidden", "artifact_expectations"):
            if required not in scenario:
                add_message(messages, "error", f"{scenario_id} missing required field {required}", repo_relative(scenario_path, root))

        prompt, attachments = build_prompt(index, scenario, scenario_dir, root, messages)
        check_prompt(index, scenario, scenario_path, prompt, messages, root)
        signal_report = check_signals(scenario, scenario_path, prompt, messages, root)

        prompt_path = prompt_dir / f"{scenario_id}.prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        owner = str(scenario.get("owner", reference.get("owner", "")))
        family = str(scenario.get("family", reference.get("family", "")))
        tier = str(scenario.get("tier", reference.get("tier", "medium")))
        coverage_tags.update([owner, family, tier])
        rows.append(
            {
                "scenario_id": scenario_id,
                "owner": owner,
                "family": family,
                "tier": tier,
                "prompt_path": repo_relative(prompt_path, root),
                "prompt_sha256": sha_text(prompt),
                "attachment_count": len(attachments),
                "attachments": attachments,
                "expected_verdict": scenario.get("hidden", {}).get("expected_verdict", ""),
                "artifact_expectations": signal_report,
            }
        )

    stored_artifact_gap = None
    collector_bundle = index.get("collector_bundle", {})
    bundle = collector_bundle.get("path")
    if bundle:
        bundle_path = root / bundle
        if not bundle_path.exists():
            stored_artifact_gap = (
                f"stored artifact not present at {bundle}; full artifact replay remains manual/operator-supplied"
            )
            add_message(
                messages,
                "error" if require_stored_artifacts else "warning",
                stored_artifact_gap,
                "blind/index.json",
            )
        elif bundle_path.is_dir():
            sanitized_manifest = collector_bundle.get("sanitized_manifest")
            if sanitized_manifest and not (root / sanitized_manifest).is_file():
                stored_artifact_gap = (
                    f"sanitized stored artifact tree present at {bundle}, "
                    f"but sanitized manifest is missing at {sanitized_manifest}"
                )
                add_message(messages, "error", stored_artifact_gap, "blind/index.json")

    return {
        "schema": index.get("schema"),
        "legacy_matrix_count": len(index.get("matrix", [])),
        "scenario_count": len(rows),
        "coverage_tags": sorted(item for item in coverage_tags if item),
        "prompts": rows,
        "stored_artifact_gap": stored_artifact_gap,
    }


def validate_collector_fixtures(root: Path, messages: list[dict[str, str]]) -> dict[str, Any]:
    index_path = root / "project_sources/collector/fixtures/blind/index.json"
    if not index_path.is_file():
        add_message(messages, "error", "collector blind index missing", repo_relative(index_path, root))
        return {"present": False}

    index = load_json(index_path)
    rows: list[dict[str, Any]] = []
    for fixture in index.get("fixtures", []):
        manifest_path = root / fixture.get("manifest", fixture.get("manifest_path", ""))
        if not manifest_path.is_file():
            add_message(
                messages,
                "error",
                f"collector fixture manifest missing for {fixture.get('id', fixture.get('fixture_id'))}",
                repo_relative(manifest_path, root),
            )
            continue
        manifest = load_json(manifest_path)
        rows.append(
            {
                "fixture_id": fixture.get("id", fixture.get("fixture_id")),
                "manifest_path": repo_relative(manifest_path, root),
                "artifact_count": len(manifest.get("artifacts", [])),
                "derived_scenarios": manifest.get("derived_scenarios", []),
            }
        )
    return {"present": True, "fixture_count": len(index.get("fixtures", [])), "manifests": rows}
