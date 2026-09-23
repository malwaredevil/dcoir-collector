from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_schema import EXPECTED_RESPONSE_PACK_SCHEMA_VERSION
from lib.gemini_behavioral_replay_utils import safe_attempts, safe_error

DEFAULT_API_BASE = "https://api.openai.com/v1/responses"


def replay_prompt(fixture: Dict[str, Any], turn: Dict[str, Any]) -> str:
    evidence = fixture.get("available_evidence_by_turn", {}).get(turn.get("turn_id"), [])
    required = turn.get("required_markers", fixture.get("required_markers", []))
    forbidden = turn.get("forbidden_markers", fixture.get("forbidden_markers", []))
    return "\n\n".join([
        "You are producing the next operator-facing answer for a governed DCOIR behavioral replay.",
        "Return only the assistant answer text. Do not include JSON, scoring notes, hidden reasoning, or meta commentary.",
        "Evidence discipline is mandatory: say what is checked, what is not checked, and avoid conclusions unsupported by listed evidence.",
        "When a required phrase is true and natural, include it exactly so the replay can measure operator-facing behavior without weakening evidence boundaries.",
        "Do not include any forbidden phrase unless you are clearly rejecting or negating that claim.",
        f"Fixture: {fixture.get('fixture_id')}",
        f"Scenario: {fixture.get('title')}",
        "Available evidence for this turn:\n" + ("\n".join(f"- {x}" for x in evidence) or "- No additional evidence is available."),
        "Allowed assumptions:\n" + ("\n".join(f"- {x}" for x in turn.get("allowed_assumptions", [])) or "- None."),
        "Disallowed assumptions:\n" + ("\n".join(f"- {x}" for x in turn.get("disallowed_assumptions", [])) or "- None."),
        "Expected behavior tags: " + (", ".join(turn.get("expected_behavior_tags", [])) or "none"),
        "Required behavior markers to satisfy when accurate: " + (", ".join(required) or "none"),
        "Forbidden claims to avoid or explicitly reject: " + (", ".join(forbidden) or "none"),
        "User turn:\n" + str(turn.get("content", "")).strip(),
    ])


def build_request_body(
    package: Dict[str, Any],
    fixture: Dict[str, Any],
    turn: Dict[str, Any],
    history: List[Dict[str, str]],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    messages: List[Dict[str, str]] = [
        {"role": "developer", "content": package["knowledge_context"]},
        *history,
        {"role": "user", "content": replay_prompt(fixture, turn)},
    ]
    return {
        "model": package["model_id"],
        "instructions": package["instructions"],
        "input": messages,
        "reasoning": {"effort": args.reasoning_effort},
        "max_output_tokens": args.max_output_tokens,
        "store": False,
    }


def extract_text(payload: Dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    out: List[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                out.append(content["text"])
    return "\n".join(out).strip()


def call_openai(
    api_key: str,
    project_id: str,
    args: argparse.Namespace,
    package: Dict[str, Any],
    fixture: Dict[str, Any],
    turn: Dict[str, Any],
    history: List[Dict[str, str]],
) -> Dict[str, Any]:
    body = json.dumps(build_request_body(package, fixture, turn, history, args)).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if project_id:
        headers["OpenAI-Project"] = project_id
    attempts: List[Dict[str, Any]] = []
    for attempt in range(1, args.max_retries + 1):
        started = time.monotonic()
        try:
            req = urllib.request.Request(args.api_base, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=180) as response:
                payload = json.loads(response.read().decode("utf-8"))
                text = extract_text(payload)
                attempts.append({"attempt": attempt, "status_code": response.status, "latency_ms": round((time.monotonic() - started) * 1000, 2)})
                if not text:
                    return {"ok": False, "attempts": attempts, "error": "empty_output", "response_id": payload.get("id")}
                return {"ok": True, "attempts": attempts, "response_text": text, "response_id": payload.get("id")}
        except urllib.error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="ignore")
            attempts.append({"attempt": attempt, "status_code": exc.code, "latency_ms": round((time.monotonic() - started) * 1000, 2), "error_body_excerpt": error_text[:1000]})
            if exc.code in {429, 500, 502, 503, 504} and attempt < args.max_retries:
                time.sleep(args.retry_base_seconds * attempt)
                continue
            return {"ok": False, "attempts": attempts, "error": f"http_{exc.code}", "error_body": error_text[:4000]}
        except Exception as exc:
            attempts.append({"attempt": attempt, "latency_ms": round((time.monotonic() - started) * 1000, 2), "error": str(exc)})
            if attempt < args.max_retries:
                time.sleep(args.retry_base_seconds * attempt)
                continue
            return {"ok": False, "attempts": attempts, "error": str(exc)}
    return {"ok": False, "attempts": attempts, "error": "unknown"}


def make_pack(
    fixture: Dict[str, Any],
    args: argparse.Namespace,
    package: Dict[str, Any],
    api_key: str,
    project_id: str,
) -> Dict[str, Any]:
    turns: List[Dict[str, str]] = []
    calls: List[Dict[str, Any]] = []
    history: List[Dict[str, str]] = []
    for turn in fixture.get("turns", []):
        call = call_openai(api_key, project_id, args, package, fixture, turn, history)
        if call.get("ok"):
            response = str(call.get("response_text") or "")
            if api_key and api_key in response:
                response = "[redacted-secret-output]"
        else:
            response = f"LIVE_OPENAI_REPLAY_CALL_FAILED: {safe_error(call.get('error')) or 'unknown'}"
        calls.append({
            "fixture_id": fixture.get("fixture_id"),
            "model_name": package["model_id"],
            "turn_id": turn.get("turn_id"),
            "ok": bool(call.get("ok")),
            "attempts": safe_attempts(call.get("attempts", [])),
            "error": safe_error(call.get("error")),
            "response_id": call.get("response_id"),
        })
        turns.append({"turn_id": turn.get("turn_id"), "assistant_response": str(response)})
        history.extend([
            {"role": "user", "content": str(turn.get("content", "")).strip()},
            {"role": "assistant", "content": str(response)},
        ])
    return {
        "schema_version": EXPECTED_RESPONSE_PACK_SCHEMA_VERSION,
        "fixture_id": fixture.get("fixture_id"),
        "mode": "live_openai_api",
        "model_name": package["model_id"],
        "turns": turns,
        "metadata": {"live_execution": True, "turn_calls": calls, "reasoning_effort": args.reasoning_effort},
    }
