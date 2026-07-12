from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_models import DEFAULT_BASELINE_MODEL
from lib.gemini_behavioral_replay_schema import validate_response_pack_shape
from lib.gemini_behavioral_replay_scoring import score_response_pack

_SENSITIVE_KEY_RE = re.compile(r"(api[_-]?key|secret|token|password|authorization|credential)", re.IGNORECASE)
_SENSITIVE_QUERY_RE = re.compile(r"((?:api[_-]?key|key|token|password)=)[^&\s`]+", re.IGNORECASE)


def redact_report_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            redacted[key] = "[redacted]" if _SENSITIVE_KEY_RE.search(key_text) else redact_report_value(child)
        return redacted
    if isinstance(value, list):
        return [redact_report_value(item) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_QUERY_RE.sub(r"\1[redacted]", value)
    return value


def score_pack(pack: Dict[str, Any], fixture: Dict[str, Any]) -> tuple[Dict[str, Any] | None, List[Dict[str, str]]]:
    messages = [{"level": m.level, "message": m.message} for m in validate_response_pack_shape(pack, fixture)]
    return (None, messages) if any(m["level"] == "error" for m in messages) else (score_response_pack(fixture, pack), messages)

def row_counts(result: Dict[str, Any]) -> tuple[int, int, int]:
    calls = result.get("metadata", {}).get("turn_calls", [])
    ok = sum(1 for call in calls if call.get("ok"))
    return len(calls), ok, len(calls) - ok

def absolute_gate_pass(result: Dict[str, Any]) -> bool:
    return bool(result.get("success"))

def apply_baseline_comparisons(results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
    baseline_model = metadata.get("baseline_model") or DEFAULT_BASELINE_MODEL
    baseline_by_fixture = {r.get("fixture_id"): r for r in results if r.get("model_name") == baseline_model}
    counts = {"better": 0, "equal": 0, "worse": 0, "baseline": 0, "no_baseline": 0, "absolute_gate_failed": 0}
    for result in results:
        baseline = baseline_by_fixture.get(result.get("fixture_id"))
        absolute_pass = absolute_gate_pass(result)
        if not baseline:
            verdict = "no_baseline"; delta = None; turn_delta = None
        else:
            delta = round(float(result.get("overall_required_marker_ratio", 0.0)) - float(baseline.get("overall_required_marker_ratio", 0.0)), 4)
            turn_delta = int(result.get("turn_success_count", 0)) - int(baseline.get("turn_success_count", 0))
            if result.get("model_name") == baseline_model:
                verdict = "baseline"
            elif not absolute_pass:
                verdict = "absolute_gate_failed"
            elif delta > 0 or (delta == 0 and turn_delta > 0):
                verdict = "better"
            elif delta == 0 and turn_delta == 0:
                verdict = "equal"
            else:
                verdict = "worse"
        result["absolute_safety_evidence_pass"] = absolute_pass
        result["baseline_relative"] = {
            "baseline_model": baseline_model, "baseline_present": bool(baseline), "verdict": verdict,
            "required_marker_ratio_delta": delta, "turn_success_count_delta": turn_delta,
            "candidate_absolute_safety_evidence_pass": absolute_pass,
            "baseline_absolute_success": baseline.get("success") if baseline else None,
            "baseline_required_marker_ratio": baseline.get("overall_required_marker_ratio") if baseline else None,
        }
        counts[verdict] = counts.get(verdict, 0) + 1
    return {"baseline_model": baseline_model, "baseline_fixture_count": len(baseline_by_fixture), "verdict_counts": counts}

def matrix_rows(results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = [dict(row, workflow=metadata.get("workflow_verdict", "success")) for row in metadata.get("runtime_unavailable_results", [])]
    if not results and not rows:
        return [{"model": metadata.get("model_name", ""), "fixture_id": "", "mode": metadata.get("replay_mode", "unknown"), "api_ok": "0/0", "turns": "0/0", "required_ratio": 0, "forbidden_hits": 0, "anomalies": 0, "absolute_gate": "not_scored", "validation_errors": len([m for m in metadata.get("validation_messages", []) if m.get("level") == "error"]), "scorer": "not_scored", "baseline_relative": "not_scored", "workflow": metadata.get("workflow_verdict", "success"), "meaning": "Diagnostic report produced."}]
    for result in results:
        count, ok, _ = row_counts(result)
        baseline_relative = result.get("baseline_relative", {})
        rows.append({"model": result.get("model_name"), "fixture_id": result.get("fixture_id"), "mode": result.get("mode"), "api_ok": f"{ok}/{count}", "turns": f"{result.get('turn_success_count')}/{result.get('turn_count')}", "required_ratio": result.get("overall_required_marker_ratio"), "forbidden_hits": len(result.get("forbidden_marker_hits", [])), "anomalies": result.get("anomaly_count"), "absolute_gate": "pass" if result.get("absolute_safety_evidence_pass") else "fail", "validation_errors": 0, "scorer": "pass" if result.get("success") else "fail", "baseline_relative": baseline_relative.get("verdict", "not_scored"), "workflow": metadata.get("workflow_verdict", "success"), "meaning": "Absolute safety/evidence gates remain binding; baseline-relative verdict compares coverage/style dimensions."})
    return sorted(rows, key=lambda row: (str(row.get("model") or ""), str(row.get("fixture_id") or ""), str(row.get("mode") or "")))

def write_reports(output_dir: Path, results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    metadata["baseline_relative_summary"] = apply_baseline_comparisons(results, metadata)
    report_metadata = redact_report_value(metadata)
    report_results = redact_report_value(results)
    rows = matrix_rows(report_results, report_metadata)
    summary = {"workflow_success": report_metadata.get("workflow_verdict", "success") == "success", "scorer_success": bool(results) and all(r.get("success") for r in results), "absolute_safety_evidence_success": bool(results) and all(r.get("absolute_safety_evidence_pass") for r in results), "result_count": len(results), "runtime_unavailable_count": len(report_metadata.get("runtime_unavailable_results", [])), "runtime_unavailable_models": report_metadata.get("runtime_unavailable_models", []), "matrix": rows, "baseline_relative_summary": report_metadata["baseline_relative_summary"]}
    payload = {"summary": summary, "metadata": report_metadata, "results": report_results}
    # report_metadata and report_results are recursively redacted before payload construction.
    (output_dir / "gemini_behavioral_replay_run_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = ["# Gemini Behavioral Replay Report", "", "## Summary", "", f"- workflow_verdict: `{report_metadata.get('workflow_verdict', 'success')}`", f"- aggregate_scorer_success: `{str(summary['scorer_success']).lower()}`", f"- absolute_safety_evidence_success: `{str(summary['absolute_safety_evidence_success']).lower()}`", f"- baseline_model: `{report_metadata.get('baseline_model')}`", f"- baseline_relative_summary: `{report_metadata.get('baseline_relative_summary')}`", f"- result_count: `{len(results)}`", f"- runtime_unavailable_count: `{summary['runtime_unavailable_count']}`", f"- runtime_unavailable_models: `{summary['runtime_unavailable_models']}`", f"- live_execution: `{report_metadata.get('live_execution')}`", f"- fallback_reason: `{report_metadata.get('fallback_reason', '')}`", "", "## Evidence Buckets", "", f"- checked_evidence: `{report_metadata.get('checked_evidence', [])}`", f"- unchecked_evidence: `{report_metadata.get('unchecked_evidence', [])}`", "", "## Viable Model Check", ""]
    mr = report_metadata["model_resolution"]
    for key in ("selection_source", "catalog_ok", "catalog_error", "hardcoded_models", "governed_pair_models", "baseline_model", "selected_models_to_run", "rejected_selected_models", "hardcoded_and_viable", "viable_missing_from_hardcoded", "hardcoded_not_currently_viable"):
        lines.append(f"- {key}: `{mr.get(key)}`")
    lines += ["", "## Fixture Selection", ""]
    fr = report_metadata["fixture_resolution"]
    for key in ("selection_source", "active_fixtures", "selected_fixtures_to_run", "rejected_selected_fixtures"):
        lines.append(f"- {key}: `{fr.get(key)}`")
    lines += ["", "## Pass/Fail Matrix", "", "| Model | Fixture | Mode | API OK | Turns | Required Ratio | Forbidden Hits | Anomalies | Absolute Gate | Scorer | Baseline Relative | Workflow | Meaning |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['model']} | {row['fixture_id']} | {row['mode']} | {row['api_ok']} | {row['turns']} | {row['required_ratio']} | {row['forbidden_hits']} | {row['anomalies']} | {row['absolute_gate']} | {row['scorer']} | {row['baseline_relative']} | {row['workflow']} | {row['meaning']} |")
    if results:
        lines += ["", "## Baseline-Relative Details", ""]
        for result in report_results:
            lines.append(f"- `{result.get('model_name')}` / `{result.get('fixture_id')}`: `{result.get('baseline_relative')}`")
    if report_metadata.get("runtime_unavailable_results"):
        lines += ["", "## Runtime Unavailable Models", ""]
        for row in report_metadata["runtime_unavailable_results"]:
            lines.append(f"- `{row.get('model')}` / `{row.get('fixture_id')}`: Unavailable at runtime; skipped scoring for this fixture.")
    if report_metadata.get("validation_messages"):
        lines += ["", "## Validation Messages", ""] + [f"- `{m.get('level')}`: {m.get('message')}" for m in report_metadata["validation_messages"]]
    markdown = "\n".join(lines).rstrip() + "\n"
    (output_dir / "gemini_behavioral_replay_run_report.md").write_text(markdown, encoding="utf-8")
    (output_dir / "chatgpt_workflow_report_section.md").write_text("## Source Workflow Custom Report\n\n" + markdown, encoding="utf-8")
