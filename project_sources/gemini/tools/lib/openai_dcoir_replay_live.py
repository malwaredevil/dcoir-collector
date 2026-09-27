from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_prompt import behavioral_replay_prompt
from lib.gemini_behavioral_replay_schema import EXPECTED_RESPONSE_PACK_SCHEMA_VERSION
from lib.gemini_behavioral_replay_utils import safe_attempts, safe_error

DEFAULT_API_BASE = "https://api.openai.com/v1/responses"


def replay_prompt(fixture: Dict[str, Any], turn: Dict[str, Any]) -> str:
    return behavioral_replay_prompt(fixture, turn, replay_label="DCOIR behavioral replay")


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


def call_openai_body(
    api_key: str,
    project_id: str,
    args: argparse.Namespace,
    body_payload: Dict[str, Any],
) -> Dict[str, Any]:
    body = json.dumps(body_payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if project_id:
        headers["OpenAI-Project"] = project_id
    attempts: List[Dict[str, Any]] = []
    for attempt in range(1, args.max_retries + 1):
        started = time.monotonic()

        def elapsed_ms() -> float:
            return round((time.monotonic() - started) * 1000, 2)

        try:
            req = urllib.request.Request(args.api_base, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=180) as response:
                status_code = response.status
                raw = response.read()
        except urllib.error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="ignore")
            attempts.append({"attempt": attempt, "status_code": exc.code, "latency_ms": elapsed_ms(), "error_body_excerpt": error_text[:1000]})
            if exc.code in {429, 500, 502, 503, 504} and attempt < args.max_retries:
                time.sleep(args.retry_base_seconds * attempt)
                continue
            return {"ok": False, "attempts": attempts, "error": f"http_{exc.code}", "error_body": error_text[:4000]}
        except urllib.error.URLError as exc:
            # urllib raises URLError only while sending the request, before any response
            # exists, so the server has not produced a billable generation; retrying is safe.
            attempts.append({"attempt": attempt, "latency_ms": elapsed_ms(), "error": str(exc.reason)})
            if attempt < args.max_retries:
                time.sleep(args.retry_base_seconds * attempt)
                continue
            return {"ok": False, "attempts": attempts, "error": "connection_error"}
        except TimeoutError:
            # The request was sent and may already be generating (and billed); re-POSTing
            # would create a duplicate generation that no logged response_id describes.
            attempts.append({"attempt": attempt, "latency_ms": elapsed_ms(), "error": "read_timeout"})
            return {"ok": False, "attempts": attempts, "error": "read_timeout"}
        except Exception as exc:
            attempts.append({"attempt": attempt, "latency_ms": elapsed_ms(), "error": str(exc)})
            return {"ok": False, "attempts": attempts, "error": str(exc)}

        attempts.append({"attempt": attempt, "status_code": status_code, "latency_ms": elapsed_ms()})
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": False, "attempts": attempts, "error": "invalid_json"}
        text = extract_text(payload)
        if payload.get("status", "completed") != "completed":
            return {"ok": False, "attempts": attempts, "error": "incomplete_output", "response_id": payload.get("id")}
        if not text:
            return {"ok": False, "attempts": attempts, "error": "empty_output", "response_id": payload.get("id")}
        return {"ok": True, "attempts": attempts, "response_text": text, "response_id": payload.get("id")}
    return {"ok": False, "attempts": attempts, "error": "unknown"}



def call_openai(
    api_key: str,
    project_id: str,
    args: argparse.Namespace,
    package: Dict[str, Any],
    fixture: Dict[str, Any],
    turn: Dict[str, Any],
    history: List[Dict[str, str]],
) -> Dict[str, Any]:
    return call_openai_body(
        api_key,
        project_id,
        args,
        build_request_body(package, fixture, turn, history, args),
    )

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
    prior_failure = False
    for turn in fixture.get("turns", []):
        if prior_failure:
            # Later turns would be conditioned on a failure placeholder, so skip the call.
            turns.append({"turn_id": turn.get("turn_id"), "assistant_response": "LIVE_OPENAI_REPLAY_NOT_ATTEMPTED: not_attempted_after_prior_failure"})
            continue
        call = call_openai(api_key, project_id, args, package, fixture, turn, history)
        if call.get("ok"):
            response = str(call.get("response_text") or "")
            if api_key and api_key in response:
                response = "[redacted-secret-output]"
        else:
            response = f"LIVE_OPENAI_REPLAY_CALL_FAILED: {safe_error(call.get('error')) or 'unknown'}"
            prior_failure = True
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
            {"role": "user", "content": replay_prompt(fixture, turn)},
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
