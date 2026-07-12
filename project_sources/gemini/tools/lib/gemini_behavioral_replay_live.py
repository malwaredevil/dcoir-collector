from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_schema import EXPECTED_RESPONSE_PACK_SCHEMA_VERSION

def live_prompt(fixture: Dict[str, Any], turn: Dict[str, Any]) -> str:
    evidence = fixture.get("available_evidence_by_turn", {}).get(turn.get("turn_id"), [])
    required = turn.get("required_markers", fixture.get("required_markers", []))
    forbidden = turn.get("forbidden_markers", fixture.get("forbidden_markers", []))
    return "\n\n".join([
        "You are producing the next operator-facing answer for a governed DCOIR Gemini behavioral replay.",
        "Return only the assistant answer text. Do not include JSON, scoring notes, hidden reasoning, or meta commentary.",
        "Evidence discipline is mandatory: say what is checked, what is not checked, and avoid conclusions that are not supported by the listed evidence.",
        "When a required phrase is true and natural, include it exactly so the replay can measure operator-facing behavior without weakening evidence boundaries.",
        "Do not include any forbidden phrase unless you are clearly rejecting or negating that claim.",
        f"Fixture: {fixture.get('fixture_id')}", f"Scenario: {fixture.get('title')}",
        "Available evidence for this turn:\n" + ("\n".join(f"- {x}" for x in evidence) or "- No additional evidence is available."),
        "Allowed assumptions:\n" + ("\n".join(f"- {x}" for x in turn.get("allowed_assumptions", [])) or "- None."),
        "Disallowed assumptions:\n" + ("\n".join(f"- {x}" for x in turn.get("disallowed_assumptions", [])) or "- None."),
        "Expected behavior tags: " + (", ".join(turn.get("expected_behavior_tags", [])) or "none"),
        "Required behavior markers to satisfy when accurate: " + (", ".join(required) or "none"),
        "Forbidden claims to avoid or explicitly reject: " + (", ".join(forbidden) or "none"),
        "User turn:\n" + str(turn.get("content", "")).strip(),
    ])

def extract_text(payload: Dict[str, Any]) -> str:
    out: List[str] = []
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                out.append(str(part["text"]))
    return "\n".join(out).strip()

def call_gemini(api_key: str, args: argparse.Namespace, model: str, prompt: str) -> Dict[str, Any]:
    endpoint = f"{args.api_base}/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": args.temperature, "candidateCount": 1}}).encode()
    attempts = []
    for attempt in range(1, args.max_retries + 1):
        start = time.monotonic()
        try:
            req = urllib.request.Request(
                endpoint,
                data=body,
                headers={"Content-Type": "application/json", "X-goog-api-key": api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
                attempts.append({"attempt": attempt, "status_code": response.status, "latency_ms": round((time.monotonic() - start) * 1000, 2)})
                return {"ok": True, "attempts": attempts, "payload": payload, "response_text": extract_text(payload)}
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore")
            attempts.append({"attempt": attempt, "status_code": exc.code, "latency_ms": round((time.monotonic() - start) * 1000, 2), "error_body_excerpt": body_text[:1000]})
            if exc.code == 429 and attempt < args.max_retries:
                time.sleep(args.retry_base_seconds * attempt); continue
            return {"ok": False, "attempts": attempts, "error": f"http_{exc.code}", "error_body": body_text[:4000]}
        except Exception as exc:
            attempts.append({"attempt": attempt, "latency_ms": round((time.monotonic() - start) * 1000, 2), "error": str(exc)})
            if attempt < args.max_retries:
                time.sleep(args.retry_base_seconds * attempt); continue
            return {"ok": False, "attempts": attempts, "error": str(exc)}
    return {"ok": False, "attempts": attempts, "error": "unknown"}

def runtime_unavailable_reason(call: Dict[str, Any]) -> str:
    text_parts = [str(call.get("error", "")), str(call.get("error_body", ""))]
    for attempt in call.get("attempts", []):
        text_parts.append(str(attempt.get("error_body_excerpt", "")))
    text = "\n".join(part for part in text_parts if part)
    low = text.lower()
    markers = ("no longer available", '"status": "not_found"', "not_found", "not found", "model not found", "not available to new users")
    if call.get("ok"):
        return ""
    if call.get("error") == "http_404" and any(marker in low for marker in markers):
        return text.strip()[:500] or "model unavailable at runtime"
    return ""

def unavailable_matrix_row(pack: Dict[str, Any]) -> Dict[str, Any]:
    calls = pack.get("metadata", {}).get("turn_calls", [])
    reason = next((str(call.get("unavailable_reason", "")) for call in calls if call.get("unavailable_reason")), "model unavailable at runtime")
    reason = re.sub(r"\s+", " ", reason).replace("|", "/")[:240]
    return {
        "model": pack.get("model_name"), "fixture_id": pack.get("fixture_id"), "mode": pack.get("mode"),
        "api_ok": f"0/{len(calls)}", "turns": f"0/{len(pack.get('turns', []))}", "required_ratio": "unavailable",
        "forbidden_hits": 0, "anomalies": 0, "absolute_gate": "unavailable", "validation_errors": 0,
        "scorer": "unavailable", "baseline_relative": "unavailable", "workflow": "success", "meaning": f"Unavailable: {reason}",
    }

def make_pack(fixture: Dict[str, Any], args: argparse.Namespace, model: str, mode: str, api_key: str, reason: str) -> Dict[str, Any]:
    turns, calls = [], []
    for turn in fixture.get("turns", []):
        if mode == "live":
            call = call_gemini(api_key, args, model, live_prompt(fixture, turn))
            unavailable_reason = runtime_unavailable_reason(call)
            if call.get("ok"):
                response = call.get("response_text")
            elif unavailable_reason:
                response = f"MODEL_UNAVAILABLE: {model} is unavailable for live replay. {unavailable_reason}"
            else:
                response = f"LIVE_REPLAY_CALL_FAILED: {call.get('error', 'unknown')}"
            calls.append({
                "fixture_id": fixture.get("fixture_id"), "model_name": model, "turn_id": turn.get("turn_id"),
                "ok": call.get("ok"), "attempts": call.get("attempts", []), "error": call.get("error"),
                "unavailable": bool(unavailable_reason), "unavailable_reason": unavailable_reason,
            })
        else:
            response = f"Live Gemini replay evidence was not produced because {reason}. Rerun with live API access and read back the generated artifacts."
        turns.append({"turn_id": turn.get("turn_id"), "assistant_response": response})
    return {
        "schema_version": EXPECTED_RESPONSE_PACK_SCHEMA_VERSION, "fixture_id": fixture.get("fixture_id"),
        "mode": "live_gemini" if mode == "live" else "fallback_emulation", "model_name": model, "turns": turns,
        "metadata": {"live_execution": mode == "live", "fallback_reason": reason if mode != "live" else "", "turn_calls": calls},
    }
