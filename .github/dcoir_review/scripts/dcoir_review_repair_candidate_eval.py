#!/usr/bin/env python3
"""No-publication live benchmark for DCOIR Review repair author/critic routing.

Plan mode makes no network calls. Live mode runs a tiny controlled repair corpus
through the production repair-set author -> deterministic validation ->
independent critic path. It never publishes a GitHub review or mutates a branch.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import statistics
import time
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_first_pass_candidate_eval as first_pass


REPORT_SCHEMA = "dcoir_review_repair_candidate_eval_report_v1"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "openrouter-pr-review-pareto.yml"


def _single_line_fixture() -> dict[str, Any]:
    path = "evaluation/repair_probe.py"
    file_text = (
        "def is_recent(age_minutes: int) -> bool:\n"
        "    \"\"\"Return True when age_minutes is between 0 and 60 inclusive.\"\"\"\n"
        "    return age_minutes >= 0 and age_minutes >= 60\n"
    )
    return {
        "id": "repair-upper-bound-one-line",
        "path": path,
        "line": 3,
        "files": {path: file_text},
        "title": "Upper-bound comparison is inverted",
        "body": "The documented inclusive 0..60 range is contradicted by a >= 60 upper-bound comparison.",
        "evidence": "The docstring requires 0 through 60 inclusive, but the changed line uses age_minutes >= 60.",
        "validation": "python -m py_compile evaluation/repair_probe.py",
        "expected_edits": [
            {
                "path": path,
                "start_line": 3,
                "end_line": 3,
                "replacement": "    return age_minutes >= 0 and age_minutes <= 60",
            }
        ],
        "diff": (
            "diff --git a/evaluation/repair_probe.py b/evaluation/repair_probe.py\n"
            "--- a/evaluation/repair_probe.py\n"
            "+++ b/evaluation/repair_probe.py\n"
            "@@ -1,3 +1,3 @@\n"
            " def is_recent(age_minutes: int) -> bool:\n"
            "     \"\"\"Return True when age_minutes is between 0 and 60 inclusive.\"\"\"\n"
            "+    return age_minutes >= 0 and age_minutes >= 60\n"
        ),
    }


def _coordinated_fixture() -> dict[str, Any]:
    path = "evaluation/repair_pair.py"
    file_text = (
        "def cache_is_recent(age_minutes: int) -> bool:\n"
        "    \"\"\"Return True when cache age is between 0 and 60 inclusive.\"\"\"\n"
        "    return age_minutes >= 0 and age_minutes >= 60\n"
        "\n"
        "def retry_is_recent(age_minutes: int) -> bool:\n"
        "    \"\"\"Return True when retry age is between 0 and 60 inclusive.\"\"\"\n"
        "    return age_minutes >= 0 and age_minutes >= 60\n"
    )
    return {
        "id": "repair-coordinated-two-edit",
        "path": path,
        "line": 3,
        "files": {path: file_text},
        "title": "Both recent-age upper bounds are inverted",
        "body": (
            "The two changed helpers implement the same documented inclusive 0..60 contract, "
            "but both use >= 60 for the upper bound. A complete repair must correct both changed comparisons."
        ),
        "evidence": (
            "Both docstrings require 0 through 60 inclusive, while the changed cache and retry lines "
            "each use age_minutes >= 60 as the upper-bound term."
        ),
        "validation": "python -m py_compile evaluation/repair_pair.py",
        "expected_edits": [
            {
                "path": path,
                "start_line": 3,
                "end_line": 3,
                "replacement": "    return age_minutes >= 0 and age_minutes <= 60",
            },
            {
                "path": path,
                "start_line": 7,
                "end_line": 7,
                "replacement": "    return age_minutes >= 0 and age_minutes <= 60",
            },
        ],
        "diff": (
            "diff --git a/evaluation/repair_pair.py b/evaluation/repair_pair.py\n"
            "--- a/evaluation/repair_pair.py\n"
            "+++ b/evaluation/repair_pair.py\n"
            "@@ -1,7 +1,7 @@\n"
            " def cache_is_recent(age_minutes: int) -> bool:\n"
            "     \"\"\"Return True when cache age is between 0 and 60 inclusive.\"\"\"\n"
            "+    return age_minutes >= 0 and age_minutes >= 60\n"
            " \n"
            " def retry_is_recent(age_minutes: int) -> bool:\n"
            "     \"\"\"Return True when retry age is between 0 and 60 inclusive.\"\"\"\n"
            "+    return age_minutes >= 0 and age_minutes >= 60\n"
        ),
    }


def _historical_false_positive_fixture() -> dict[str, Any]:
    path = "project_sources/gemini/tools/lib/openai_dcoir_replay_live.py"
    file_text = "from __future__ import annotations\n\nimport argparse\nimport json\nimport re\nimport time\nimport urllib.error\nimport urllib.request\nfrom typing import Any, Dict, List\n\nfrom lib.gemini_behavioral_replay_prompt import behavioral_replay_prompt\nfrom lib.gemini_behavioral_replay_schema import EXPECTED_RESPONSE_PACK_SCHEMA_VERSION\nfrom lib.gemini_behavioral_replay_utils import safe_attempts, safe_error\n\nDEFAULT_API_BASE = \"https://api.openai.com/v1/responses\"\n_RESPONSE_ID = re.compile(r\"^resp_[A-Za-z0-9_-]+$\")\n\n\ndef replay_prompt(fixture: Dict[str, Any], turn: Dict[str, Any]) -> str:\n    return behavioral_replay_prompt(fixture, turn, replay_label=\"DCOIR behavioral replay\")\n\n\ndef build_request_body(\n    package: Dict[str, Any],\n    fixture: Dict[str, Any],\n    turn: Dict[str, Any],\n    history: List[Dict[str, str]],\n    args: argparse.Namespace,\n) -> Dict[str, Any]:\n    messages: List[Dict[str, str]] = [\n        {\"role\": \"developer\", \"content\": package[\"knowledge_context\"]},\n        *history,\n        {\"role\": \"user\", \"content\": replay_prompt(fixture, turn)},\n    ]\n    return {\n        \"model\": package[\"model_id\"],\n        \"instructions\": package[\"instructions\"],\n        \"input\": messages,\n        \"reasoning\": {\"effort\": args.reasoning_effort},\n        \"max_output_tokens\": args.max_output_tokens,\n        \"store\": False,\n    }\n\n\ndef _extract_text_with_shape(payload: Any) -> tuple[str, bool]:\n    if not isinstance(payload, dict):\n        return \"\", False\n\n    direct = payload.get(\"output_text\")\n    if direct is not None and not isinstance(direct, str):\n        return \"\", False\n    direct_text = direct.strip() if isinstance(direct, str) else \"\"\n\n    raw_output = payload.get(\"output\")\n    nested_parts: List[str] = []\n    if raw_output is not None:\n        if not isinstance(raw_output, list):\n            return \"\", False\n        for item in raw_output:\n            if not isinstance(item, dict):\n                return \"\", False\n            if item.get(\"type\") != \"message\":\n                continue\n            raw_content = item.get(\"content\")\n            if not isinstance(raw_content, list):\n                return \"\", False\n            for content in raw_content:\n                if not isinstance(content, dict):\n                    return \"\", False\n                if content.get(\"type\") == \"output_text\":\n                    text = content.get(\"text\")\n                    if not isinstance(text, str):\n                        return \"\", False\n                    nested_parts.append(text)\n    nested_text = \"\\n\".join(nested_parts).strip()\n\n    # When both representations are populated, they must agree. A convenience\n    # field must never shelter malformed or conflicting nested provider output.\n    if direct_text and nested_text and direct_text != nested_text:\n        return \"\", False\n    return direct_text or nested_text, True\n\n\ndef extract_text(payload: Dict[str, Any]) -> str:\n    text, _ = _extract_text_with_shape(payload)\n    return text\n\n\ndef call_openai_body(\n    api_key: str,\n    project_id: str,\n    args: argparse.Namespace,\n    body_payload: Dict[str, Any],\n) -> Dict[str, Any]:\n    body = json.dumps(body_payload).encode(\"utf-8\")\n    headers = {\"Content-Type\": \"application/json\", \"Authorization\": f\"Bearer {api_key}\"}\n    if project_id:\n        headers[\"OpenAI-Project\"] = project_id\n    attempts: List[Dict[str, Any]] = []\n    for attempt in range(1, args.max_retries + 1):\n        started = time.monotonic()\n\n        def elapsed_ms() -> float:\n            return round((time.monotonic() - started) * 1000, 2)\n\n        try:\n            req = urllib.request.Request(args.api_base, data=body, headers=headers, method=\"POST\")\n            with urllib.request.urlopen(req, timeout=180) as response:\n                status_code = response.status\n                raw = response.read()\n        except urllib.error.HTTPError as exc:\n            error_text = exc.read().decode(\"utf-8\", errors=\"ignore\")\n            attempts.append({\"attempt\": attempt, \"status_code\": exc.code, \"latency_ms\": elapsed_ms(), \"error_body_excerpt\": error_text[:1000]})\n            if exc.code in {429, 500, 502, 503, 504} and attempt < args.max_retries:\n                time.sleep(args.retry_base_seconds * attempt)\n                continue\n            return {\"ok\": False, \"attempts\": attempts, \"error\": f\"http_{exc.code}\", \"error_body\": error_text[:4000]}\n        except urllib.error.URLError as exc:\n            # urllib raises URLError only while sending the request, before any response\n            # exists, so the server has not produced a billable generation; retrying is safe.\n            attempts.append({\"attempt\": attempt, \"latency_ms\": elapsed_ms(), \"error\": str(exc.reason)})\n            if attempt < args.max_retries:\n                time.sleep(args.retry_base_seconds * attempt)\n                continue\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"connection_error\"}\n        except TimeoutError:\n            # The request was sent and may already be generating (and billed); re-POSTing\n            # would create a duplicate generation that no logged response_id describes.\n            attempts.append({\"attempt\": attempt, \"latency_ms\": elapsed_ms(), \"error\": \"read_timeout\"})\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"read_timeout\"}\n        except Exception as exc:\n            attempts.append({\"attempt\": attempt, \"latency_ms\": elapsed_ms(), \"error\": str(exc)})\n            return {\"ok\": False, \"attempts\": attempts, \"error\": str(exc)}\n\n        attempts.append({\"attempt\": attempt, \"status_code\": status_code, \"latency_ms\": elapsed_ms()})\n        try:\n            payload = json.loads(raw.decode(\"utf-8\"))\n        except (UnicodeDecodeError, json.JSONDecodeError):\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"invalid_json\"}\n        if not isinstance(payload, dict):\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"invalid_response_shape\"}\n        response_id = payload.get(\"id\")\n        status = payload.get(\"status\")\n        if not isinstance(status, str):\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"invalid_response_shape\"}\n        if status != \"completed\":\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"incomplete_output\", \"response_id\": response_id if isinstance(response_id, str) else None}\n        if not isinstance(response_id, str) or not _RESPONSE_ID.fullmatch(response_id):\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"invalid_response_shape\"}\n        text, response_shape_ok = _extract_text_with_shape(payload)\n        if not response_shape_ok:\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"invalid_response_shape\", \"response_id\": response_id}\n        if not text:\n            return {\"ok\": False, \"attempts\": attempts, \"error\": \"empty_output\", \"response_id\": response_id}\n        return {\"ok\": True, \"attempts\": attempts, \"response_text\": text, \"response_id\": response_id}\n    return {\"ok\": False, \"attempts\": attempts, \"error\": \"unknown\"}\n\n\n\ndef call_openai(\n    api_key: str,\n    project_id: str,\n    args: argparse.Namespace,\n    package: Dict[str, Any],\n    fixture: Dict[str, Any],\n    turn: Dict[str, Any],\n    history: List[Dict[str, str]],\n) -> Dict[str, Any]:\n    return call_openai_body(\n        api_key,\n        project_id,\n        args,\n        build_request_body(package, fixture, turn, history, args),\n    )\n\ndef make_pack(\n    fixture: Dict[str, Any],\n    args: argparse.Namespace,\n    package: Dict[str, Any],\n    api_key: str,\n    project_id: str,\n) -> Dict[str, Any]:\n    turns: List[Dict[str, str]] = []\n    calls: List[Dict[str, Any]] = []\n    history: List[Dict[str, str]] = []\n    prior_failure = False\n    for turn in fixture.get(\"turns\", []):\n        if prior_failure:\n            # Later turns would be conditioned on a failure placeholder, so skip the call.\n            turns.append({\"turn_id\": turn.get(\"turn_id\"), \"assistant_response\": \"LIVE_OPENAI_REPLAY_NOT_ATTEMPTED: not_attempted_after_prior_failure\"})\n            continue\n        call = call_openai(api_key, project_id, args, package, fixture, turn, history)\n        if call.get(\"ok\"):\n            response = str(call.get(\"response_text\") or \"\")\n            if api_key and api_key in response:\n                response = \"[redacted-secret-output]\"\n        else:\n            response = f\"LIVE_OPENAI_REPLAY_CALL_FAILED: {safe_error(call.get('error')) or 'unknown'}\"\n            prior_failure = True\n        calls.append({\n            \"fixture_id\": fixture.get(\"fixture_id\"),\n            \"model_name\": package[\"model_id\"],\n            \"turn_id\": turn.get(\"turn_id\"),\n            \"ok\": bool(call.get(\"ok\")),\n            \"attempts\": safe_attempts(call.get(\"attempts\", [])),\n            \"error\": safe_error(call.get(\"error\")),\n            \"response_id\": call.get(\"response_id\"),\n        })\n        turns.append({\"turn_id\": turn.get(\"turn_id\"), \"assistant_response\": str(response)})\n        history.extend([\n            {\"role\": \"user\", \"content\": replay_prompt(fixture, turn)},\n            {\"role\": \"assistant\", \"content\": str(response)},\n        ])\n    return {\n        \"schema_version\": EXPECTED_RESPONSE_PACK_SCHEMA_VERSION,\n        \"fixture_id\": fixture.get(\"fixture_id\"),\n        \"mode\": \"live_openai_api\",\n        \"model_name\": package[\"model_id\"],\n        \"turns\": turns,\n        \"metadata\": {\"live_execution\": True, \"turn_calls\": calls, \"reasoning_effort\": args.reasoning_effort},\n    }\n"
    diff = (
        "diff --git a/" + path + " b/" + path + "\n"
        "--- /dev/null\n"
        "+++ b/" + path + "\n"
        "@@ -0,0 +1," + str(len(file_text.splitlines())) + " @@\n"
        + "".join("+" + line + "\n" for line in file_text.splitlines())
    )
    return {
        "id": "repair-pr581-urlopen-false-positive",
        "path": path,
        "line": 108,
        "files": {path: file_text},
        "title": "Python writes to a request-controlled filesystem path",
        "body": (
            "Historical PR #581 finding: This write may use a request-controlled path. "
            "Resolve and verify the destination is inside the governed output directory."
        ),
        "evidence": (
            "Historical DCOIR Review discussion r4085149271 anchored this finding at line 108 "
            "of reviewed commit 4c142c3b06648d41887768271f9745fd27e0aadf."
        ),
        "validation": (
            "python3 -m py_compile project_sources/gemini/tools/lib/openai_dcoir_replay_live.py; "
            "bandit -r project_sources/gemini/tools/lib/openai_dcoir_replay_live.py"
        ),
        "expected_edits": [],
        "expected_outcome": "defect-absent-suppressed",
        "historical_review_comment_id": 4085149271,
        "historical_reviewed_commit": "4c142c3b06648d41887768271f9745fd27e0aadf",
        "diff": diff,
    }


def load_cases() -> list[dict[str, Any]]:
    return [_single_line_fixture(), _coordinated_fixture(), _historical_false_positive_fixture()]


def select_cases(requested: list[str]) -> list[dict[str, Any]]:
    cases = load_cases()
    if not requested:
        return cases
    by_id = {case["id"]: case for case in cases}
    selected: list[dict[str, Any]] = []
    for case_id in requested:
        if case_id not in by_id:
            raise ValueError(f"Unknown repair benchmark case id: {case_id}")
        selected.append(dict(by_id[case_id]))
    if len({case["id"] for case in selected}) != len(selected):
        raise ValueError("Repair case selection contains duplicate ids")
    return selected


def _candidate_config(review: Any, candidate: dict[str, Any]) -> Any:
    model = str(candidate.get("model", "") or "").strip()
    if not model or model.startswith("openrouter/"):
        raise ValueError(f"Repair benchmark requires a pinned direct model id: {candidate.get('id')}")
    if candidate.get("tools") or candidate.get("plugins"):
        raise ValueError(f"Repair benchmark does not enable candidate tools/plugins: {candidate.get('id')}")
    config = copy.copy(review.load_pareto_context_config(str(CONFIG_PATH)))
    config.model = model
    config.model_stack = [model]
    effort = str(candidate.get("reasoning_effort", "") or "").strip()
    if effort:
        config.review_reasoning_effort = effort
    config.openrouter_session_id_prefix = "dcoir-review-repair-benchmark"
    config.debug = False
    return config


def _candidate_payload_builder(base_builder: Any, candidate: dict[str, Any]) -> Any:
    """Apply only the selected candidate's benchmark request-shape overrides."""
    candidate_model = str(candidate.get("model", "") or "").strip()
    candidate_temperature = candidate.get("temperature")

    def build(prompt: str, schema: dict[str, Any], config: Any, ignored_providers: Any, model: Any) -> dict[str, Any]:
        payload = base_builder(prompt, schema, config, ignored_providers, model)
        if str(model or "").strip() != candidate_model:
            return payload
        if candidate_temperature is None:
            payload.pop("temperature", None)
        else:
            value = float(candidate_temperature)
            if not 0.0 <= value <= 2.0:
                raise ValueError(f"Candidate {candidate.get('id')} temperature must be between 0 and 2")
            payload["temperature"] = value
        return payload

    return build


def _verified_finding(v21: Any, case: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": case["title"],
        "severity": "high",
        "confidence": 1.0,
        "path": case["path"],
        "line": case["line"],
        "body": case["body"],
        "suggested_replacement": "",
        "validation": case["validation"],
        v21.VERIFIER_MARKER: {
            "mode": "model-judge",
            "supported": True,
            "confidence": 0.99,
            "evidence": case["evidence"],
            "reason": case["body"],
            "model_used": "benchmark-verifier",
            "head_sha": "benchmark-head",
            "line": case["line"],
        },
    }


def score_item(item: dict[str, Any], case: dict[str, Any], repair: Any, v36: Any) -> dict[str, Any]:
    marker = item.get(repair.REPAIR_MARKER) if isinstance(item.get(repair.REPAIR_MARKER), dict) else {}
    outcome = str(marker.get("outcome", "") or "")
    edits = marker.get("edits") if isinstance(marker.get("edits"), list) else []
    expected = sorted(
        [
            {
                "path": str(edit["path"]),
                "start_line": int(edit["start_line"]),
                "end_line": int(edit["end_line"]),
                "replacement": str(edit["replacement"]),
            }
            for edit in case["expected_edits"]
        ],
        key=lambda item: (item["path"], item["start_line"], item["end_line"], item["replacement"]),
    )
    actual = sorted(
        [
            {
                "path": str(edit.get("path", "")),
                "start_line": int(edit.get("start_line", 0) or 0),
                "end_line": int(edit.get("end_line", 0) or 0),
                "replacement": str(edit.get("replacement", "") or ""),
            }
            for edit in edits
            if isinstance(edit, dict)
        ],
        key=lambda item: (item["path"], item["start_line"], item["end_line"], item["replacement"]),
    )
    expected_outcome = str(case.get("expected_outcome", v36.REPAIR_SET_OUTCOME) or v36.REPAIR_SET_OUTCOME)
    if expected_outcome == "defect-absent-suppressed":
        correct_edit = outcome == expected_outcome and not edits
        unsafe_accept = outcome == v36.REPAIR_SET_OUTCOME
    else:
        correct_edit = (
            outcome == v36.REPAIR_SET_OUTCOME
            and bool(marker.get("critic_accepted"))
            and actual == expected
        )
        unsafe_accept = outcome == v36.REPAIR_SET_OUTCOME and not correct_edit
    return {
        "correct": correct_edit,
        "unsafe_accept": unsafe_accept,
        "outcome": outcome,
        "author_model": str(marker.get("author_model", "") or ""),
        "critic_model": str(marker.get("critic_model", "") or ""),
        "critic_accepted": bool(marker.get("critic_accepted", False)),
        "reason": str(marker.get("reason", "") or "")[:800],
        "edit_count": len(edits),
        "edits": edits,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * pct
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = index - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * fraction


def _run_case(review: Any, v21: Any, repair: Any, v36: Any, candidate: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    config = _candidate_config(review, candidate)
    file_map = dict(case["files"])
    original_fetch = review.fetch_pr_file_text
    original_debug = review.hardened.write_debug_json_artifact_safely
    original_builder = review.hardened.build_openrouter_payload
    review.fetch_pr_file_text = lambda _gh, path, _head: file_map[path]
    review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
    review.hardened.build_openrouter_payload = _candidate_payload_builder(original_builder, candidate)
    started = time.monotonic()
    try:
        right_index = review.base.build_diff_line_index(case["diff"])
        item = v36._build_repair_set_for_finding(
            review,
            1,
            _verified_finding(v21, case),
            object(),
            "benchmark-head",
            case["diff"],
            right_index,
            config,
            dict(file_map),
            author_config_override=config,
        )
        score = score_item(item, case, repair, v36)
        error = ""
    except Exception as exc:
        item = {}
        detail = f"{type(exc).__name__}: {str(exc)[:500]}"
        score = {"correct": False, "unsafe_accept": False, "outcome": "request-error", "reason": detail}
        error = detail
    finally:
        review.fetch_pr_file_text = original_fetch
        review.hardened.write_debug_json_artifact_safely = original_debug
        review.hardened.build_openrouter_payload = original_builder
    elapsed = time.monotonic() - started
    return {
        "case_id": case["id"],
        "ok": not bool(error),
        "error": error,
        "latency_seconds": elapsed,
        "score": score,
        "result_marker": item.get(repair.REPAIR_MARKER, {}) if isinstance(item, dict) else {},
    }


def run_live(candidates: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        raise RuntimeError("OPENROUTER_API_KEY is required only for --execute-live")
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review.finding_verifier")
    repair = importlib.import_module("dcoir_review.repair_pipeline")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        case_results = [_run_case(review, v21, repair, v36, candidate, case) for case in cases]
        failures = [r["case_id"] for r in case_results if not r["score"].get("correct") and not r["score"].get("unsafe_accept") and not r.get("error")]
        unsafe = [r["case_id"] for r in case_results if r["score"].get("unsafe_accept")]
        errors = [r["case_id"] for r in case_results if r.get("error")]
        latencies = [float(r["latency_seconds"]) for r in case_results]
        rows.append(
            {
                "candidate": {
                    "id": candidate["id"],
                    "model": candidate["model"],
                    "benchmark_role": "repair-author-with-production-independent-critic",
                },
                "case_results": case_results,
                "quality": {
                    "acceptance_eligible_quality_floor": not failures and not unsafe and not errors,
                    "repair_failure_case_ids": failures,
                    "unsafe_accept_case_ids": unsafe,
                    "request_error_case_ids": errors,
                },
                "economics": {
                    "cost_measured": False,
                    "exact_cost_usd": 0.0,
                    "serial_wall_seconds": sum(latencies),
                    "p50_request_seconds": statistics.median(latencies) if latencies else 0.0,
                    "p95_request_seconds": _percentile(latencies, 0.95),
                },
            }
        )
    return {
        "schema_version": REPORT_SCHEMA,
        "benchmark_stage": "repair",
        "mode": "live-no-publication",
        "no_publication": True,
        "candidates": rows,
    }


def plan(candidates: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "benchmark_stage": "repair",
        "mode": "plan-no-network",
        "no_publication": True,
        "candidate_ids": [str(candidate["id"]) for candidate in candidates],
        "case_ids": [str(case["id"]) for case in cases],
        "case_counts": {
            "selected_cases": len(cases),
            "planned_total_requests": len(candidates) * len(cases) * 2,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    del args.timeout_seconds

    matrix = first_pass.load_matrix()
    candidates = first_pass.selected_candidates(matrix, args.candidate)
    cases = select_cases([str(item).strip() for item in args.case if str(item).strip()])
    report = run_live(candidates, cases) if args.execute_live else plan(candidates, cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
