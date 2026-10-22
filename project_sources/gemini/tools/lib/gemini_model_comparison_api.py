from __future__ import annotations

import json
import math
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_models import model_exclusion_reason

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

def list_models(api_key: str, api_base: str) -> List[Dict[str, Any]]:
    url = f"{api_base}/models"
    request = urllib.request.Request(url, headers={"X-goog-api-key": api_key}, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8")).get("models", [])

def _canonical_model_id(model_name: Any) -> str:
    name = str(model_name or "")
    if name.startswith("models/"):
        name = name.removeprefix("models/")
        if not name or "/" in name:
            return ""
    elif "/" in name:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        return ""
    return name.lower()

def resolve_requested_models(
    requested: List[str], available_models: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Select only exactly named, pinned, text-capable models.

    In particular, never replace a requested preview or stable model with a
    '-latest' alias or a different preview/stable variant.
    """
    exact: Dict[str, Dict[str, Any]] = {}
    for model in sorted(available_models, key=lambda item: str(item.get("name", ""))):
        model_id = _canonical_model_id(model.get("name", ""))
        if not model_id or model_exclusion_reason(model):
            continue
        exact.setdefault(model_id, model)
    resolved: Dict[str, Dict[str, Any]] = {}
    for requested_name in requested:
        model_id = _canonical_model_id(requested_name)
        if not model_id.endswith("-latest") and model_id in exact:
            resolved[requested_name] = exact[model_id]
    return resolved


def model_resolution_warning(requested_name: str, available_models: List[Dict[str, Any]]) -> str:
    """Describe a tempting unpinned match without silently selecting it."""
    model_id = _canonical_model_id(requested_name)
    if not model_id:
        return ""
    if model_id.endswith("-latest"):
        return "unpinned_latest_alias_rejected"
    stem = model_id.removesuffix("-preview").removesuffix("-latest")
    for model in available_models:
        available_id = _canonical_model_id(model.get("name", ""))
        if available_id != model_id and available_id.removesuffix("-preview").removesuffix("-latest") == stem:
            return "similar_model_alias_not_selected"
    return ""

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
