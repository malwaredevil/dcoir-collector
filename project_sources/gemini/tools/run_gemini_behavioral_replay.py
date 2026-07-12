#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_live import make_pack, unavailable_matrix_row
from lib.gemini_behavioral_replay_models import (
    DEFAULT_API_BASE,
    DEFAULT_BASELINE_MODEL,
    DEFAULT_MODEL,
    GOVERNED_PAIR_MODELS,
    HARDCODED_MODELS,
    resolve_models,
)
from lib.gemini_behavioral_replay_runner import load_response_pack
from lib.gemini_behavioral_replay_selection import resolve_fixtures
from lib.gemini_behavioral_replay_utils import mkdir, safe
from lib.gemini_behavioral_replay_workflow_report import score_pack, write_reports

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixtures-root", required=True); p.add_argument("--output-dir", required=True)
    p.add_argument("--fixture-id"); p.add_argument("--fixture-ids-csv", default=None); p.add_argument("--custom-fixtures-csv", default=""); p.add_argument("--run-all-active-fixtures", action="store_true")
    p.add_argument("--mode", choices=["deterministic", "live", "fallback"], default="deterministic"); p.add_argument("--response-pack")
    p.add_argument("--api-key-env", default="DCOIR_GEMINI_API"); p.add_argument("--api-base", default=DEFAULT_API_BASE)
    p.add_argument("--model", default=DEFAULT_MODEL); p.add_argument("--models-csv", default=None); p.add_argument("--custom-models-csv", default=""); p.add_argument("--run-all-viable-catalog-models", action="store_true"); p.add_argument("--selection-report-only", action="store_true")
    p.add_argument("--baseline-model", default=DEFAULT_BASELINE_MODEL)
    p.add_argument("--temperature", type=float, default=1.0); p.add_argument("--max-retries", type=int, default=4); p.add_argument("--retry-base-seconds", type=float, default=5.0); p.add_argument("--allow-fallback", action="store_true")
    args = p.parse_args()
    output_dir = Path(args.output_dir).resolve(); mkdir(output_dir)
    fixtures_root = Path(args.fixtures_root).resolve(); api_key = os.environ.get(args.api_key_env, "").strip()
    if args.mode == "deterministic":
        models = {"selection_source": "deterministic_response_pack", "catalog_ok": False, "catalog_error": "catalog not consulted for deterministic mode", "hardcoded_models": HARDCODED_MODELS, "governed_pair_models": GOVERNED_PAIR_MODELS, "baseline_model": args.baseline_model, "selected_models_to_run": [args.model], "rejected_selected_models": [], "hardcoded_and_viable": [], "viable_missing_from_hardcoded": [], "hardcoded_not_currently_viable": [], "excluded_catalog_models": []}
    else:
        models = resolve_models(args, api_key)
    fixtures, fixture_resolution = resolve_fixtures(args, fixtures_root, Path(__file__))
    metadata: Dict[str, Any] = {"workflow_verdict": "success", "replay_mode": args.mode, "model_name": ",".join(models["selected_models_to_run"]), "baseline_model": args.baseline_model, "fixture_count": len(fixtures), "model_resolution": models, "fixture_resolution": fixture_resolution, "validation_messages": [], "checked_evidence": ["fixture index", "fixture definitions"], "unchecked_evidence": [], "runtime_unavailable_results": []}
    if models["rejected_selected_models"]:
        metadata["validation_messages"].append({"level": "error", "message": "One or more selected models were rejected; see model_resolution.rejected_selected_models."})
    if args.mode != "deterministic" and args.baseline_model not in models["selected_models_to_run"]:
        metadata["validation_messages"].append({"level": "error", "message": f"Baseline model {args.baseline_model!r} is not selected for replay, so baseline-relative scoring cannot run."})
    if fixture_resolution["rejected_selected_fixtures"]:
        metadata["validation_messages"].append({"level": "error", "message": "One or more selected fixtures were rejected."})
    if not models["selected_models_to_run"]:
        metadata["validation_messages"].append({"level": "error", "message": "No models selected for replay."})
    if not fixtures:
        metadata["validation_messages"].append({"level": "error", "message": "No active fixtures selected for replay."})
    if args.selection_report_only:
        if any(message.get("level") == "error" for message in metadata.get("validation_messages", [])):
            metadata["workflow_verdict"] = "failure"; write_reports(output_dir, [], metadata); return 1
        write_reports(output_dir, [], metadata); return 0
    mode, reason = args.mode, ""
    if args.mode == "fallback":
        reason = "fallback mode requested"; metadata["unchecked_evidence"].append("live Gemini API response")
    if args.mode == "live" and not api_key:
        reason = "Required Gemini API credential is not configured."
        if args.allow_fallback:
            mode = "fallback"; metadata["unchecked_evidence"].append("live Gemini API response")
        else:
            metadata["workflow_verdict"] = "failure"; metadata["validation_messages"].append({"level": "error", "message": reason}); metadata["unchecked_evidence"].append("live Gemini API response"); write_reports(output_dir, [], metadata); return 1
    results: List[Dict[str, Any]] = []; calls: List[Dict[str, Any]] = []
    deterministic = load_response_pack(Path(args.response_pack).resolve()) if args.response_pack else None
    for row in fixtures:
        fixture = row["fixture"]
        loop_models = [args.model] if mode == "deterministic" else models["selected_models_to_run"]
        for model in loop_models:
            if mode == "deterministic":
                if deterministic is None:
                    metadata["validation_messages"].append({"level": "error", "message": "--response-pack is required in deterministic mode."}); continue
                if deterministic.get("fixture_id") and deterministic.get("fixture_id") != fixture.get("fixture_id"):
                    continue
                pack = deterministic
                if pack.get("mode") != "deterministic":
                    metadata["validation_messages"].append({"level": "error", "message": f"deterministic mode requires a deterministic response pack, got {pack.get('mode')!r}."})
                    if "response-pack schema" not in metadata["checked_evidence"]:
                        metadata["checked_evidence"].append("response-pack schema")
                    continue
            else:
                pack = make_pack(fixture, args, model, mode, api_key, reason or "fallback mode requested")
                calls.extend(pack.get("metadata", {}).get("turn_calls", []))
                suffix = "live" if mode == "live" else "fallback"
                (output_dir / f"{safe(fixture.get('fixture_id'))}_{safe(model)}_{suffix}_response_pack.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
                pack_calls = pack.get("metadata", {}).get("turn_calls", [])
                if mode == "live" and pack_calls and all(call.get("unavailable") for call in pack_calls):
                    metadata["runtime_unavailable_results"].append(unavailable_matrix_row(pack)); continue
            result, messages = score_pack(pack, fixture); metadata["validation_messages"].extend(messages)
            if "response-pack schema" not in metadata["checked_evidence"]:
                metadata["checked_evidence"].append("response-pack schema")
            if result is not None:
                if "deterministic scorer" not in metadata["checked_evidence"]:
                    metadata["checked_evidence"].append("deterministic scorer")
                results.append(result)
    ok = sum(1 for call in calls if call.get("ok")); unavailable = sum(1 for call in calls if call.get("unavailable"))
    failed = len(calls) - ok - unavailable
    runtime_unavailable_models = sorted({str(row.get("model")) for row in metadata.get("runtime_unavailable_results", [])})
    metadata["runtime_unavailable_models"] = runtime_unavailable_models
    live_complete = mode == "live" and bool(calls) and ok == len(calls)
    baseline_call_failures = [call for call in calls if call.get("model_name") == args.baseline_model and not call.get("ok")]
    if mode == "live" and baseline_call_failures:
        metadata["validation_messages"].append({"level": "error", "message": f"Baseline model {args.baseline_model!r} had one or more live API failures, so baseline-relative scoring cannot be trusted."})
    if mode == "live":
        target_bucket = metadata["checked_evidence"] if live_complete else metadata["unchecked_evidence"]
        if "live Gemini API response" not in target_bucket:
            target_bucket.append("live Gemini API response")
        if (runtime_unavailable_models or failed) and "runtime model availability" not in metadata["checked_evidence"]:
            metadata["checked_evidence"].append("runtime model availability")
    metadata.update({"replay_mode": mode, "live_execution": mode == "live" and bool(calls), "fallback_reason": reason, "api_call_count": len(calls), "api_call_success_count": ok, "api_call_failure_count": failed + unavailable, "api_call_unavailable_count": unavailable, "api_call_reported_failure_count": failed, "live_response_complete": live_complete, "prompt_profile": "behavioral_replay_operator_turn_exact_marker_tuned", "production_prompt_equivalent": "partial_fixture_replay_prompt", "live_environment_fidelity_gap": "Manual live replay uses fixture prompts and does not prove full production runtime parity."})
    has_errors = any(message.get("level") == "error" for message in metadata.get("validation_messages", []))
    scorer_failed = bool(results) and not all(result.get("success") for result in results)
    deterministic_failed = mode == "deterministic" and (has_errors or scorer_failed or not results)
    workflow_failed = has_errors or not results
    if deterministic_failed or workflow_failed:
        metadata["workflow_verdict"] = "failure"
    write_reports(output_dir, results, metadata)
    if deterministic_failed or workflow_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
