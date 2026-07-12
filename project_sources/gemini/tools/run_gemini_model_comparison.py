#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_model_comparison_api import (
    DEFAULT_API_BASE,
    DEFAULT_CANDIDATES,
    DEFAULT_REFERENCE_MODEL,
    build_case_prompt,
    call_model,
    ensure_dir,
    estimate_tokens,
    list_models,
    load_json,
    resolve_requested_models,
)
from lib.gemini_model_comparison_eval import (
    compare_traits,
    evaluate_case_output,
    parse_model_json,
    summarize_model_run,
)
from lib.gemini_behavioral_replay_workflow_report import redact_report_value

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-profile-path", default=None)
    parser.add_argument("--api-key-env", default="DCOIR_GEMINI_API")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--reference-model", default=DEFAULT_REFERENCE_MODEL)
    parser.add_argument("--candidate-models", default=",".join(DEFAULT_CANDIDATES))
    parser.add_argument("--repeat-count", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--inter-request-delay-seconds", type=float, default=3.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--retry-base-seconds", type=float, default=5.0)
    parser.add_argument("--minimum-case-score", type=float, default=75.0)
    parser.add_argument("--minimum-behavior-score", type=float, default=80.0)
    parser.add_argument("--critical-case-ids", default="GEM-PHASE1-STATE-001,GEM-PHASE1-CHUNKS-001")
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print("Required Gemini API credential is not configured.", file=sys.stderr)
        return 1
    fixture_path = Path(args.fixtures).resolve()
    output_dir = Path(args.output_dir).resolve()
    ensure_dir(output_dir)
    fixtures = load_json(fixture_path)
    model_profiles = load_json(Path(args.model_profile_path).resolve()) if args.model_profile_path else {"models": {}}
    requested_models = []
    for name in [args.reference_model, *[part.strip() for part in args.candidate_models.split(",") if part.strip()]]:
        if name not in requested_models:
            requested_models.append(name)
    available_models = list_models(api_key, args.api_base)
    resolved_models = resolve_requested_models(requested_models, available_models)
    cases = list(fixtures.get("cases", []))
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    critical_case_ids = [part.strip() for part in args.critical_case_ids.split(",") if part.strip()]
    all_case_records: List[Dict[str, Any]] = []
    trait_baselines: Dict[str, Dict[str, bool]] = {}
    for model_name in requested_models:
        resolved_model = resolved_models.get(model_name)
        if resolved_model is None:
            for case in cases:
                all_case_records.append({"requested_model": model_name, "resolved_model_name": None, "case_id": case["id"], "protocol_ok": False, "protocol_error": "model_not_available", "rubric_score": 0.0, "case_pass": False, "closeness_to_reference": 0.0, "attempt_count": 0, "latency_ms": None, "anomaly_terms": [], "contradictions": []})
            continue
        for case in cases:
            for repetition in range(1, args.repeat_count + 1):
                prompt = build_case_prompt(case)
                call = call_model(api_key, args.api_base, resolved_model, prompt, args.temperature, args.max_retries, args.retry_base_seconds)
                protocol_ok = False
                parsed_response: Dict[str, Any] = {}
                protocol_error = None
                evaluation: Dict[str, Any] = {"rubric_score": 0.0, "case_pass": False, "traits": {}, "anomaly_terms": [], "contradictions": [], "matched_required_markers": [], "missing_required_markers": list(case.get("required_markers", [])), "matched_forbidden_markers": [], "group_results": [], "final_response_markdown": ""}
                usage = call.get("usage_metadata", {})
                if call.get("ok"):
                    protocol_ok, parsed_response, protocol_error = parse_model_json(call["response_text"])
                    if protocol_ok:
                        evaluation = evaluate_case_output(case, parsed_response)
                        if model_name == args.reference_model:
                            trait_baselines[case["id"]] = evaluation["traits"]
                if call.get("ok") and not protocol_ok:
                    protocol_error = protocol_error or "protocol_parse_failed"
                if not call.get("ok"):
                    protocol_error = call.get("error", "model_call_failed")
                all_case_records.append({
                    "requested_model": model_name,
                    "resolved_model_name": resolved_model.get("name"),
                    "case_id": case["id"],
                    "case_description": case.get("description"),
                    "repeat_index": repetition,
                    "protocol_ok": protocol_ok,
                    "protocol_error": protocol_error,
                    "decision_summary": parsed_response.get("decision_summary") if parsed_response else None,
                    "recommended_actions": parsed_response.get("recommended_actions") if parsed_response else None,
                    "rubric_score": evaluation["rubric_score"],
                    "case_pass": evaluation["case_pass"],
                    "matched_required_markers": evaluation["matched_required_markers"],
                    "missing_required_markers": evaluation["missing_required_markers"],
                    "matched_forbidden_markers": evaluation["matched_forbidden_markers"],
                    "group_results": evaluation["group_results"],
                    "anomaly_terms": evaluation["anomaly_terms"],
                    "contradictions": evaluation["contradictions"],
                    "traits": evaluation["traits"],
                    "final_response_markdown": evaluation["final_response_markdown"],
                    "attempt_count": len(call.get("attempts", [])),
                    "attempts": call.get("attempts", []),
                    "latency_ms": call.get("attempts", [{}])[-1].get("latency_ms") if call.get("attempts") else None,
                    "usage_metadata": usage,
                    "estimated_prompt_tokens": estimate_tokens(prompt),
                    "error_body": call.get("error_body"),
                })
                time.sleep(args.inter_request_delay_seconds)
    for record in all_case_records:
        baseline = trait_baselines.get(record["case_id"])
        if baseline and record["protocol_ok"]:
            record["closeness_to_reference"] = compare_traits(baseline, record["traits"])
        elif record["requested_model"] == args.reference_model and record["protocol_ok"]:
            record["closeness_to_reference"] = 100.0
        else:
            record["closeness_to_reference"] = 0.0
    model_summaries = [
        summarize_model_run(model_name, resolved_models.get(model_name), [record for record in all_case_records if record["requested_model"] == model_name], model_profiles.get("models", {}).get(model_name), args.minimum_case_score, args.minimum_behavior_score, critical_case_ids)
        for model_name in requested_models
    ]
    rankings = sorted(model_summaries, key=lambda item: (-item["composite_score"], -item["behavior_score"], -item["closeness_score"]))
    qualified = [item for item in rankings if item["behavior_pass"]]
    report = {
        "success": bool(qualified),
        "fixture_path": str(fixture_path),
        "requested_models": requested_models,
        "resolved_models": {name: model.get("name") for name, model in resolved_models.items()},
        "reference_model": args.reference_model,
        "repeat_count": args.repeat_count,
        "case_count": len(cases),
        "available_model_catalog_size": len(available_models),
        "minimum_case_score": args.minimum_case_score,
        "minimum_behavior_score": args.minimum_behavior_score,
        "critical_case_ids": critical_case_ids,
        "best_relative_model": rankings[0]["requested_model"] if rankings else None,
        "recommended_model": qualified[0]["requested_model"] if qualified else None,
        "model_summaries": model_summaries,
        "rankings": rankings,
        "case_results": all_case_records,
    }
    report = redact_report_value(report)
    # The report is recursively redacted above before it reaches disk or stdout.
    (output_dir / "gemini_model_comparison_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Gemini model comparison summary", "", f"- reference_model: {args.reference_model}", f"- fixture_path: {fixture_path.as_posix()}", f"- repeat_count: {args.repeat_count}", f"- case_count: {len(cases)}", f"- minimum_case_score: {args.minimum_case_score}", f"- minimum_behavior_score: {args.minimum_behavior_score}", f"- best_relative_model: {report['best_relative_model']}", f"- recommended_model: {report['recommended_model'] or 'none'}", "", "## Ranking", ""]
    for rank, summary in enumerate(rankings, start=1):
        lines.append(f"{rank}. `{summary['requested_model']}` -> composite={summary['composite_score']}, behavior={summary['behavior_score']}, closeness={summary['closeness_score']}, operational_fit={summary['operational_fit_score']}, protocol={summary['protocol_score']}, behavior_pass={str(summary['behavior_pass']).lower()}, status={summary['recommendation_status']}")
        if summary.get("failed_cases"):
            lines.append(f"   failed_cases: {', '.join(summary['failed_cases'])}")
    lines.extend(["", "## Availability", ""])
    for name in requested_models:
        resolved = resolved_models.get(name)
        lines.append(f"- `{name}` -> `{resolved.get('name')}`" if resolved else f"- `{name}` -> unavailable")
    (output_dir / "gemini_model_comparison_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
