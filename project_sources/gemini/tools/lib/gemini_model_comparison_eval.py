from __future__ import annotations

import json
import statistics
from typing import Any, Dict, List, Tuple

ANOMALY_TERMS = ["routing_state", "planner_payloads", "readiness_confirmed", "enterprise_web_search_status", "missing_minimum_evidence"]

CONTRADICTION_PAIRS = [("wait", "kill"), ("rerun", "leave it alone"), ("cleanup now", "do not clean up yet")]

def parse_model_json(response_text: str) -> Tuple[bool, Dict[str, Any], str | None]:
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        return False, {}, f"json_decode_error: {exc}"
    required = {"protocol_version", "decision_summary", "state_gaps", "recommended_actions", "caution_notes", "final_response_markdown"}
    missing = sorted(required - set(parsed))
    if missing:
        return False, parsed, f"missing_keys: {', '.join(missing)}"
    return True, parsed, None

def evaluate_case_output(case: Dict[str, Any], parsed_response: Dict[str, Any]) -> Dict[str, Any]:
    final_markdown = str(parsed_response.get("final_response_markdown", ""))
    lowered = final_markdown.lower()
    required_markers = list(case.get("required_markers", []))
    forbidden_markers = list(case.get("forbidden_markers", []))
    any_groups = list(case.get("any_marker_groups", []))
    matched_required = [marker for marker in required_markers if marker.lower() in lowered]
    missing_required = [marker for marker in required_markers if marker.lower() not in lowered]
    matched_forbidden = [marker for marker in forbidden_markers if marker.lower() in lowered]
    group_results = []
    for group in any_groups:
        matched = [marker for marker in group if marker.lower() in lowered]
        group_results.append({"expected_any_of": group, "matched": matched, "passed": bool(matched)})
    anomalies = [term for term in ANOMALY_TERMS if term in lowered]
    contradictions = [f"{left} <-> {right}" for left, right in CONTRADICTION_PAIRS if left in lowered and right in lowered]
    traits: Dict[str, bool] = {}
    for marker in required_markers:
        traits[f"required::{marker}"] = marker.lower() in lowered
    for marker in forbidden_markers:
        traits[f"forbidden::{marker}"] = marker.lower() in lowered
    for index, group in enumerate(any_groups, start=1):
        traits[f"any_group::{index}"] = any(marker.lower() in lowered for marker in group)
    for term in ANOMALY_TERMS:
        traits[f"anomaly::{term}"] = term in lowered
    for pair in contradictions:
        traits[f"contradiction::{pair}"] = True
    total_checks = len(required_markers) + len(any_groups) + max(1, len(forbidden_markers))
    passed_checks = len(matched_required) + sum(1 for group in group_results if group["passed"]) + (len(forbidden_markers) - len(matched_forbidden))
    rubric_score = round((passed_checks / total_checks) * 100, 2) if total_checks else 100.0
    case_pass = rubric_score >= float(case.get("minimum_rubric_score", 75.0)) and not matched_forbidden and not anomalies and not contradictions and all(group["passed"] for group in group_results)
    return {
        "final_response_markdown": final_markdown,
        "matched_required_markers": matched_required,
        "missing_required_markers": missing_required,
        "matched_forbidden_markers": matched_forbidden,
        "group_results": group_results,
        "anomaly_terms": anomalies,
        "contradictions": contradictions,
        "traits": traits,
        "rubric_score": rubric_score,
        "case_pass": case_pass,
    }

def compare_traits(reference_traits: Dict[str, bool], candidate_traits: Dict[str, bool]) -> float:
    keys = sorted(set(reference_traits) | set(candidate_traits))
    if not keys:
        return 100.0
    matches = sum(1 for key in keys if reference_traits.get(key, False) == candidate_traits.get(key, False))
    return round((matches / len(keys)) * 100, 2)

def summarize_model_run(requested_model: str, resolved_model: Dict[str, Any] | None, case_results: List[Dict[str, Any]], profile_hints: Dict[str, Any] | None, minimum_case_score: float, minimum_behavior_score: float, critical_case_ids: List[str]) -> Dict[str, Any]:
    available = resolved_model is not None
    protocol_passes = [case for case in case_results if case.get("protocol_ok")]
    rubric_scores = [case.get("rubric_score", 0.0) for case in protocol_passes]
    closeness_scores = [case.get("closeness_to_reference", 0.0) for case in protocol_passes]
    latencies = [case.get("latency_ms", 0.0) for case in case_results if case.get("latency_ms") is not None]
    retries = [max(0, case.get("attempt_count", 1) - 1) for case in case_results]
    anomaly_count = sum(len(case.get("anomaly_terms", [])) + len(case.get("contradictions", [])) for case in case_results)
    failure_count = sum(1 for case in case_results if not case.get("protocol_ok"))
    failed_cases = [case["case_id"] for case in case_results if not case.get("protocol_ok") or not case.get("case_pass") or case.get("rubric_score", 0.0) < minimum_case_score]
    critical_failures = sorted(set(failed_cases) & set(critical_case_ids))
    hint_score = None
    if profile_hints:
        rpm = float(profile_hints.get("rpm", 0) or 0)
        tpm = float(profile_hints.get("tpm", 0) or 0)
        rpd = float(profile_hints.get("rpd", 0) or 0)
        throughput_score = min(100.0, round((rpm / 25.0) * 40 + min(tpm / 2000000.0, 1.0) * 40 + min(rpd / 250.0, 1.0) * 20, 2))
        cost_modifier = {"low": 10.0, "medium": 0.0, "high": -10.0, "unknown": -5.0}.get(str(profile_hints.get("cost_tier", "unknown")).lower(), -5.0)
        hint_score = max(0.0, min(100.0, throughput_score + cost_modifier))
    observed_operational = 100.0
    if latencies:
        observed_operational -= min(35.0, statistics.median(latencies) / 200.0)
    observed_operational -= min(25.0, statistics.mean(retries) * 10.0 if retries else 0.0)
    observed_operational -= min(25.0, failure_count * 10.0)
    observed_operational = round(max(0.0, observed_operational), 2)
    operational_fit = round(((hint_score if hint_score is not None else observed_operational) + observed_operational) / 2, 2) if available else 0.0
    protocol_score = round((len(protocol_passes) / len(case_results)) * 100, 2) if case_results else 0.0
    behavior_score = round(statistics.mean(rubric_scores), 2) if rubric_scores else 0.0
    closeness_score = round(statistics.mean(closeness_scores), 2) if closeness_scores else 0.0
    anomaly_penalty = min(20.0, anomaly_count * 5.0)
    composite = round(max(0.0, protocol_score * 0.25 + behavior_score * 0.45 + closeness_score * 0.20 + operational_fit * 0.10 - anomaly_penalty), 2) if available else 0.0
    behavior_pass = available and protocol_score == 100.0 and behavior_score >= minimum_behavior_score and not failed_cases and not critical_failures and anomaly_count == 0
    return {
        "requested_model": requested_model,
        "resolved_model_name": resolved_model.get("name") if resolved_model else None,
        "available": available,
        "protocol_score": protocol_score,
        "behavior_score": behavior_score,
        "closeness_score": closeness_score,
        "operational_fit_score": operational_fit,
        "observed_operational_score": observed_operational,
        "profile_hint_score": hint_score,
        "anomaly_count": anomaly_count,
        "composite_score": composite,
        "median_latency_ms": round(statistics.median(latencies), 2) if latencies else None,
        "mean_retry_count": round(statistics.mean(retries), 2) if retries else 0.0,
        "failed_cases": failed_cases,
        "critical_failures": critical_failures,
        "behavior_pass": behavior_pass,
        "recommendation_status": "recommended_for_simulated_production" if behavior_pass else "relative_only_not_behavior_qualified",
    }
