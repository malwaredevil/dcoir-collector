#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_runner import repo_root_from_script
from lib.gemini_behavioral_replay_selection import resolve_fixtures
from lib.gemini_behavioral_replay_utils import mkdir, safe
from lib.gemini_behavioral_replay_workflow_report import score_pack, write_reports
from lib.openai_dcoir_replay_live import DEFAULT_API_BASE, make_pack
from lib.openai_dcoir_replay_package import load_governed_openai_package

REPORT_NAME = "openai_dcoir_behavioral_replay_run_report.json"
REPORT_LABEL = "OpenAI DCOIR Behavioral Replay"


def main() -> int:
    p = argparse.ArgumentParser(description="Run automated live GPT-5.6 Terra behavioral replay for the governed AFRICOM DCOIR Analyst package.")
    p.add_argument("--fixtures-root", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--custom-fixtures-csv", default="")
    p.add_argument("--run-all-active-fixtures", action="store_true")
    p.add_argument("--api-key-env", default="DCOIR_OPENAI_API_KEY")
    p.add_argument("--fallback-api-key-env", default="OPENAI_API_KEY")
    p.add_argument("--project-id-env", default="DCOIR_OPENAI_PROJECT_ID")
    p.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh", "max"], default="medium")
    p.add_argument("--max-output-tokens", type=int, default=8192)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--retry-base-seconds", type=float, default=5.0)
    args = p.parse_args()
    args.api_base = DEFAULT_API_BASE
    if not 1024 <= args.max_output_tokens <= 32768:
        p.error("--max-output-tokens must be between 1024 and 32768")
    args.mode = "openai_live"
    args.fixture_ids_csv = None
    args.fixture_id = None

    output_dir = Path(args.output_dir).resolve()
    fixtures_root = Path(args.fixtures_root).resolve()
    mkdir(output_dir)
    repo_root = repo_root_from_script(Path(__file__))

    metadata: Dict[str, Any] = {
        "workflow_verdict": "success",
        "replay_mode": "live_openai_api",
        "baseline_model": "gpt-5.6-terra",
        "validation_messages": [],
        "checked_evidence": ["fixture index", "fixture definitions"],
        "unchecked_evidence": ["Custom GPT WebUI host behavior", "Custom GPT proprietary Knowledge retrieval behavior"],
        "runtime_unavailable_results": [],
        "model_resolution": {
            "selection_source": "governed_openai_package",
            "catalog_ok": None,
            "catalog_error": "not_required_fixed_model",
            "hardcoded_models": ["gpt-5.6-terra"],
            "governed_pair_models": ["gpt-5.6-terra"],
            "baseline_model": "gpt-5.6-terra",
            "selected_models_to_run": ["gpt-5.6-terra"],
            "rejected_selected_models": [],
            "hardcoded_and_viable": ["gpt-5.6-terra"],
            "viable_missing_from_hardcoded": [],
            "hardcoded_not_currently_viable": [],
        },
        "fixture_resolution": {},
    }
    try:
        package = load_governed_openai_package(repo_root)
        metadata["checked_evidence"].append("governed AFRICOM DCOIR Analyst package hashes")
        metadata["package_evidence"] = {
            "model_id": package["model_id"],
            "runtime_name": package["runtime_name"],
            "instructions_path": package["instructions_path"],
            "instructions_sha256": package["instructions_sha256"],
            "knowledge_files": package["knowledge_files"],
            "package_manifest_sha256": package["package_manifest_sha256"],
            "configuration_sha256": package["configuration_sha256"],
            "behavior_source_snapshot_sha256": package["behavior_source_snapshot_sha256"],
            "source_base_commit": package["source_base_commit"],
            "capabilities": package["capabilities"],
        }
    except Exception as exc:
        metadata["workflow_verdict"] = "failure"
        metadata["validation_messages"].append({"level": "error", "message": f"Governed OpenAI package validation failed: {exc}"})
        write_reports(output_dir, [], metadata, report_label=REPORT_LABEL, report_filename=REPORT_NAME, report_markdown_filename="openai_dcoir_behavioral_replay_run_report.md")
        return 1

    fixtures, fixture_resolution = resolve_fixtures(args, fixtures_root, Path(__file__))
    metadata["fixture_resolution"] = fixture_resolution
    metadata["fixture_count"] = len(fixtures)
    rejected = fixture_resolution.get("rejected_selected_fixtures") or []
    if rejected:
        metadata["validation_messages"].append({"level": "error", "message": "One or more selected OpenAI replay fixtures were rejected."})
    if not fixtures:
        metadata["validation_messages"].append({"level": "error", "message": "No active live_openai_api fixtures were selected."})

    api_key = os.environ.get(args.api_key_env, "").strip() or os.environ.get(args.fallback_api_key_env, "").strip()
    project_id = os.environ.get(args.project_id_env, "").strip()
    if not api_key:
        metadata["workflow_verdict"] = "failure"
        metadata["validation_messages"].append({"level": "error", "message": "OpenAI replay credentials are not configured."})
        metadata["unchecked_evidence"].append("live OpenAI Responses API output")
        write_reports(output_dir, [], metadata, report_label=REPORT_LABEL, report_filename=REPORT_NAME, report_markdown_filename="openai_dcoir_behavioral_replay_run_report.md")
        return 1

    results: List[Dict[str, Any]] = []
    calls: List[Dict[str, Any]] = []
    for row in fixtures:
        fixture = row["fixture"]
        pack = make_pack(fixture, args, package, api_key, project_id)
        calls.extend(pack.get("metadata", {}).get("turn_calls", []))
        (output_dir / f"{safe(fixture.get('fixture_id'))}_{package['model_id']}_live_openai_response_pack.json").write_text(
            json.dumps(pack, indent=2), encoding="utf-8"
        )
        result, messages = score_pack(pack, fixture)
        metadata["validation_messages"].extend(messages)
        if result is not None:
            results.append(result)

    ok = sum(1 for call in calls if call.get("ok"))
    failed = len(calls) - ok
    if failed:
        metadata["validation_messages"].append({"level": "error", "message": f"{failed} live OpenAI Responses API call(s) failed."})
    metadata.update({
        "model_name": package["model_id"],
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "live_execution": bool(calls),
        "api_call_count": len(calls),
        "api_call_success_count": ok,
        "api_call_failure_count": failed,
        "live_response_complete": bool(calls) and failed == 0,
        "production_prompt_equivalent": "exact governed Instructions plus exact generated Knowledge projection and fixture replay prompt",
        "live_environment_fidelity_gap": "Real GPT-5.6 Terra Responses API evidence with exact repository package; does not prove Custom GPT WebUI host or proprietary Knowledge-retrieval parity.",
    })
    if bool(calls) and failed == 0:
        metadata["checked_evidence"].append("live OpenAI Responses API output")
    elif "live OpenAI Responses API output" not in metadata["unchecked_evidence"]:
        metadata["unchecked_evidence"].append("live OpenAI Responses API output")

    has_errors = any(message.get("level") == "error" for message in metadata["validation_messages"])
    if has_errors or not results:
        metadata["workflow_verdict"] = "failure"
    write_reports(output_dir, results, metadata, report_label=REPORT_LABEL, report_filename=REPORT_NAME, report_markdown_filename="openai_dcoir_behavioral_replay_run_report.md")
    return 1 if metadata["workflow_verdict"] == "failure" else 0


if __name__ == "__main__":
    raise SystemExit(main())
