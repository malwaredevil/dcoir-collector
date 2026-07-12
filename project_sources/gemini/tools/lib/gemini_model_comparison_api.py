from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_REFERENCE_MODEL = "gemini-3.1-pro-preview"

DEFAULT_CANDIDATES = ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-2.5-pro", "gemini-2.5-flash"]

JSON_ONLY_INSTRUCTION = (
    "Return exactly one JSON object and no surrounding prose. Use these keys only: "
    "protocol_version, decision_summary, state_gaps, recommended_actions, caution_notes, final_response_markdown."
)

def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def normalize_model_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered.startswith("models/"):
        lowered = lowered.split("/", 1)[1]
    for token in ("-preview", "-latest"):
        lowered = lowered.replace(token, "")
    return lowered

def list_models(api_key: str, api_base: str) -> List[Dict[str, Any]]:
    url = f"{api_base}/models"
    request = urllib.request.Request(url, headers={"X-goog-api-key": api_key}, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8")).get("models", [])

def resolve_requested_models(requested: List[str], available_models: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    exact: Dict[str, Dict[str, Any]] = {}
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for model in available_models:
        raw_name = model.get("name", "")
        model_id = raw_name.split("/", 1)[1] if raw_name.startswith("models/") else raw_name
        exact[model_id.lower()] = model
        normalized.setdefault(normalize_model_name(model_id), []).append(model)
    resolved: Dict[str, Dict[str, Any]] = {}
    for requested_name in requested:
        candidate = exact.get(requested_name.lower())
        if candidate is None:
            matches = normalized.get(normalize_model_name(requested_name), [])
            if matches:
                candidate = sorted(matches, key=lambda item: item.get("name", ""))[0]
        if candidate is not None:
            resolved[requested_name] = candidate
    return resolved

def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))

def build_case_prompt(case: Dict[str, Any]) -> str:
    conversation_lines = []
    for turn in case.get("turns", []):
        role = str(turn.get("role", "user")).upper()
        text = str(turn.get("text", "")).strip()
        conversation_lines.append(f"{role}:\n{text}")
    sections = [
        "You are simulating the next assistant turn for a governed DCOIR Gemini agent evaluation.",
        JSON_ONLY_INSTRUCTION,
        f"Case ID: {case['id']}",
        f"Case goal: {case.get('goal', '')}",
        "Available evidence constraints:",
        str(case.get("allowed_evidence", "")).strip(),
        "Conversation so far:",
        "\n\n".join(conversation_lines).strip(),
    ]
    if case.get("notes"):
        sections.extend(["Evaluator notes:", str(case["notes"]).strip()])
    return "\n\n".join(section for section in sections if section)

def extract_response_text(payload: Dict[str, Any]) -> str:
    text_parts: List[str] = []
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                text_parts.append(str(part["text"]))
    return "\n".join(text_parts).strip()

def call_model(api_key: str, api_base: str, resolved_model: Dict[str, Any], prompt: str, temperature: float, max_retries: int, retry_base_seconds: float) -> Dict[str, Any]:
    endpoint = f"{api_base}/{resolved_model.get('name', '')}:generateContent"
    request_body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
    ).encode("utf-8")
    attempts: List[Dict[str, Any]] = []
    for attempt_index in range(1, max_retries + 1):
        start = time.monotonic()
        request = urllib.request.Request(endpoint, data=request_body, headers={"Content-Type": "application/json", "X-goog-api-key": api_key}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                payload = json.loads(response.read().decode("utf-8"))
                attempts.append({"attempt": attempt_index, "status_code": response.status, "latency_ms": latency_ms})
                return {"ok": True, "attempts": attempts, "payload": payload, "response_text": extract_response_text(payload), "usage_metadata": payload.get("usageMetadata", {})}
        except urllib.error.HTTPError as exc:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            error_body = exc.read().decode("utf-8", errors="ignore")
            attempts.append({"attempt": attempt_index, "status_code": exc.code, "latency_ms": latency_ms, "error_body_excerpt": error_body[:1000]})
            if exc.code == 429 and attempt_index < max_retries:
                time.sleep(retry_base_seconds * attempt_index)
                continue
            return {"ok": False, "attempts": attempts, "error": f"http_{exc.code}", "error_body": error_body[:4000]}
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            attempts.append({"attempt": attempt_index, "latency_ms": latency_ms, "error": str(exc)})
            if attempt_index < max_retries:
                time.sleep(retry_base_seconds * attempt_index)
                continue
            return {"ok": False, "attempts": attempts, "error": str(exc)}
    return {"ok": False, "attempts": attempts, "error": "unknown"}
