from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_utils import csv

DEFAULT_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_MODEL = "gemini-3.5-flash"

DEFAULT_BASELINE_MODEL = "gemini-3.1-pro-preview"

RETIRED_TEXT_MODEL_NAMES = {"gemini-3-pro-preview"}

RETIRED_TEXT_MODEL_PREFIXES = (
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
)

HARDCODED_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-pro-preview-customtools",
    "gemini-3.5-flash",
]

GOVERNED_PAIR_MODELS = ["gemini-3.5-flash", DEFAULT_BASELINE_MODEL]

EXCLUDED_MODEL_SUBSTRINGS = [
    "antigravity",
    "aqa",
    "computer-use",
    "deep-research",
    "embedding",
    "imagen",
    "image-generation",
    "-image",
    "native-audio",
    "robotics",
    "tts",
    "veo",
]

def normalize_model_name(model_name: str) -> str:
    return str(model_name or "").split("/")[-1].lower()

def is_retired_text_model(model_name: str) -> bool:
    low = normalize_model_name(model_name)
    return low in RETIRED_TEXT_MODEL_NAMES or any(low == prefix or low.startswith(f"{prefix}-") for prefix in RETIRED_TEXT_MODEL_PREFIXES)

def model_exclusion_reason(model: Dict[str, Any]) -> str:
    name = str(model.get("name", "")).split("/")[-1]
    low = name.lower()
    if not low.startswith("gemini-"):
        return "not a Gemini model"
    if low.endswith("-latest"):
        return "alias/latest indirection is not a pinned replay model"
    for token in EXCLUDED_MODEL_SUBSTRINGS:
        if token in low:
            return f"excluded non-text replay family: {token}"
    methods = model.get("supportedGenerationMethods") or []
    return "" if not methods or "generateContent" in methods else "does not advertise generateContent"

def fetch_catalog(api_key: str, api_base: str) -> Dict[str, Any]:
    if not api_key:
        return {"ok": False, "error": "missing API key", "viable_models": [], "excluded_models": []}
    endpoint = f"{api_base}/models"
    try:
        request = urllib.request.Request(endpoint, headers={"X-goog-api-key": api_key}, method="GET")
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}: {exc.read().decode('utf-8', errors='ignore')[:500]}", "viable_models": [], "excluded_models": []}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "viable_models": [], "excluded_models": []}
    viable, excluded = [], []
    for model in payload.get("models", []):
        name = str(model.get("name", "")).split("/")[-1]
        reason = model_exclusion_reason(model)
        if reason:
            excluded.append({"model": name, "reason": reason})
        else:
            viable.append(name)
    return {"ok": True, "error": "", "viable_models": sorted(set(viable)), "excluded_models": excluded}

def resolve_models(args: argparse.Namespace, api_key: str) -> Dict[str, Any]:
    catalog = fetch_catalog(api_key, args.api_base)
    catalog_viable = catalog["viable_models"]
    viable = [model for model in catalog_viable if not is_retired_text_model(model)]
    retired_viable = sorted(model for model in catalog_viable if is_retired_text_model(model))
    checked = csv(args.models_csv)
    if args.models_csv is None and not checked:
        checked = [args.model] if args.model else []
    custom = csv(args.custom_models_csv)
    rejected: List[Dict[str, str]] = []
    if args.run_all_viable_catalog_models:
        selected, source = viable, "all_viable_text_replay_catalog_models"
    elif custom:
        selected, source = [], "custom_models_csv"
        for model in custom:
            if catalog["ok"] and model not in viable:
                rejected.append({"model": model, "reason": "not in currently viable replay text model set"})
            else:
                selected.append(model)
    else:
        selected, source = [], "checkbox_models"
        for model in checked:
            if model not in HARDCODED_MODELS:
                rejected.append({"model": model, "reason": "not present in hard-coded checkbox model list"})
            elif catalog["ok"] and model not in viable:
                rejected.append({"model": model, "reason": "not in currently viable replay text model set"})
            else:
                selected.append(model)
    selected = sorted(dict.fromkeys(selected))
    retired_entries = [{"model": model, "reason": "deprecated or shut-down text model removed from replay selector"} for model in retired_viable]
    return {
        "selection_source": source, "catalog_ok": catalog["ok"], "catalog_error": catalog["error"],
        "hardcoded_models": HARDCODED_MODELS, "governed_pair_models": GOVERNED_PAIR_MODELS,
        "baseline_model": args.baseline_model, "selected_models_to_run": selected,
        "rejected_selected_models": rejected,
        "hardcoded_and_viable": sorted(set(HARDCODED_MODELS).intersection(viable)),
        "viable_missing_from_hardcoded": sorted(set(viable).difference(HARDCODED_MODELS)),
        "hardcoded_not_currently_viable": sorted(set(HARDCODED_MODELS).difference(viable)) if catalog["ok"] else [],
        "excluded_catalog_models": catalog["excluded_models"] + retired_entries,
    }
