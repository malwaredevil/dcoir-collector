"""Sixth required-coverage layer for DCOIR Review.

This layer adds a guarded OpenRouter Auto prompt-review pass before Pareto
model calls, while fixing the PR #329 deterministic failures around helper
compatibility, env-token redaction provenance, YAML metadata-shell semantics,
and required-coverage debug readback.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v2 as v2
import dcoir_review_required_runtime_patch_v3 as v3
import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5

PROMPT_REVIEW_MODEL = "openrouter/auto"
PROMPT_REVIEW_MAX_ADDENDUM_CHARS = 1800
PROMPT_REVIEW_MAX_INPUT_CHARS = 90000
PROMPT_REVIEW_SECTION_TITLE = "Prompt-review supplemental guidance"

ENV_PROVENANCE_LINE_RE = re.compile(
    r"(?m)^.*(?:os\.environ(?:\.get)?|os\.getenv|\$env:|process\.env\.|Environment::GetEnvironmentVariable)[^\n]*$"
)
SAFE_BEARER_EXPR_RE = re.compile(
    r"(?P<prefix>[fFrRbBuU]*)(?P<quote>[\"'])(?P<body>Bearer\s+(?:\{[^}\n]+\}|\$env:[A-Za-z_][A-Za-z0-9_]*|\$\{[^}\n]+\}|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%))(?P=quote)"
)
SENTINEL_ANCHOR_RE = re.compile(r"(?m)^- (?P<anchor>[^:\n]+:\d+ \[[^\]\n]+\])")
ENV_PROVENANCE_TOKEN_RE = re.compile(
    r"os\.environ(?:\.get)?\([^\n)]*\)|os\.environ\[[^\n\]]+\]|os\.getenv\([^\n)]*\)|\$env:[A-Za-z_][A-Za-z0-9_]*|process\.env\.[A-Za-z_][A-Za-z0-9_]*|Environment::GetEnvironmentVariable\([^\n)]*\)"
)
FORBIDDEN_ADDENDUM_RE = re.compile(
    r"```|\b(?:remove|delete|omit|ignore|weaken|downgrade)\b[^.\n]{0,80}\b(?:sentinel|anchor|finding|schema|changed line|diff|code block)\b|\bsummary-only\b|\bredacted-secret\b",
    re.IGNORECASE,
)

PROMPT_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["use_original", "supplemental_instructions", "risk_notes", "preserved_constraints", "rejected_changes"],
    "properties": {
        "use_original": {"type": "boolean"},
        "supplemental_instructions": {"type": "string"},
        "risk_notes": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "preserved_constraints": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
        "rejected_changes": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    },
}

_prompt_review_lock = threading.Lock()
_prompt_review_counter = 0
_prompt_review_cache: dict[str, tuple[str, dict[str, Any]]] = {}


def _next_prompt_review_id() -> int:
    global _prompt_review_counter
    with _prompt_review_lock:
        _prompt_review_counter += 1
        return _prompt_review_counter


def _sha12(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


def _prompt_kind(prompt: str) -> str:
    lower = prompt.lower()
    if "per-file detector pass" in lower:
        return "per-file-detector"
    if "review quality retry" in lower:
        return "quality-retry"
    if "fix synthesis" in lower or "structured repair data" in lower:
        return "fix-synthesis"
    if "context mode:" in lower:
        return "whole-pr-detector"
    return "model-prompt"


def _protect_env_provenance(text: str) -> tuple[str, list[str]]:
    protected: list[str] = []

    def store(value: str) -> str:
        protected.append(value)
        return f"__DCOIR_ENV_PROVENANCE_{len(protected) - 1}__"

    def stash(match: re.Match[str]) -> str:
        return store(match.group(0))

    result = ENV_PROVENANCE_LINE_RE.sub(stash, text)
    protected_lines: list[str] = []
    for line in result.splitlines(keepends=True):
        if not SAFE_BEARER_EXPR_RE.search(line):
            protected_lines.append(line)
            continue
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        value = line[: -len(ending)] if ending else line
        protected_lines.append(store(value) + ending)
    result = "".join(protected_lines)
    return result, protected


def _restore_env_provenance(text: str, protected: list[str]) -> str:
    result = text
    for index, value in enumerate(protected):
        result = result.replace(f"__DCOIR_ENV_PROVENANCE_{index}__", value)
    return result


def _extract_sentinel_anchors(prompt: str) -> list[str]:
    return [match.group("anchor") for match in SENTINEL_ANCHOR_RE.finditer(prompt)]


def _extract_env_provenance(prompt: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in ENV_PROVENANCE_TOKEN_RE.finditer(prompt):
        value = match.group(0)
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _review_enabled(config: Any) -> bool:
    env_value = os.environ.get("DCOIR_PROMPT_REVIEW", "").strip().lower()
    if env_value in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(getattr(config, "prompt_review_enabled", True))


def _should_review_model(model: str, config: Any) -> bool:
    if str(model or "") == PROMPT_REVIEW_MODEL:
        return False
    if not _review_enabled(config):
        return False
    if bool(getattr(config, "prompt_review_all_models", False)):
        return True
    return "pareto" in str(model or "").lower()


def _prompt_review_prompt(original_prompt: str, prompt_kind: str) -> str:
    clipped = original_prompt
    if len(clipped) > PROMPT_REVIEW_MAX_INPUT_CHARS:
        clipped = clipped[:PROMPT_REVIEW_MAX_INPUT_CHARS] + "\n\n[prompt clipped for prompt-review preflight]"
    return f"""
You are reviewing a DCOIR Review prompt before it is sent to a coding review model.
Your task is prompt engineering only.

Return structured JSON only. Do not rewrite the full prompt. Provide at most one supplemental instruction block that can be appended after the original prompt.

Hard constraints:
- Do not alter file paths, line numbers, changed code, diffs, code fences, full-file context, right-side changed-line maps, required risk-sentinel anchors, JSON schema rules, validation commands, repository guidance, PR metadata, or redaction placeholders.
- Do not weaken required coverage, deterministic fallback, env-token wording, or the requirement to return finding objects rather than summary-only concerns.
- If the original prompt is malformed, describe the problem in risk_notes and supplemental_instructions, but do not invent replacement source code.
- Keep supplemental_instructions concise, imperative, and directly useful to the next model.
- If no safe improvement is needed, set use_original to true and leave supplemental_instructions empty.

Prompt kind: {prompt_kind}

Original prompt:
<<<DCOIR_ORIGINAL_PROMPT
{clipped}
DCOIR_ORIGINAL_PROMPT
""".strip()


def _request_prompt_review(original_prompt: str, prompt_kind: str, config: Any, hardened: Any, base: Any) -> tuple[dict[str, Any], str, str]:
    api_key = base.env_required("OPENROUTER_API_KEY")
    payload: dict[str, Any] = {
        "model": PROMPT_REVIEW_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a prompt-engineering reviewer. Return only JSON that matches the requested schema.",
            },
            {"role": "user", "content": _prompt_review_prompt(original_prompt, prompt_kind)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "dcoir_prompt_review", "strict": True, "schema": PROMPT_REVIEW_SCHEMA},
        },
        "provider": {"allow_fallbacks": True, "require_parameters": True},
        "plugins": [{"id": "auto-router"}, {"id": "response-healing"}],
        "temperature": 0.1,
    }
    sticky_session = getattr(hardened, "session_id", lambda _config: "")(config)
    if sticky_session:
        payload["session_id"] = sticky_session
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/DCOIR-Collector/dcoir-collector",
        "X-OpenRouter-Title": base.REVIEW_DISPLAY_NAME,
    }
    if sticky_session:
        headers["X-Session-Id"] = sticky_session
    req = urllib.request.Request(hardened.OPENROUTER_API, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=90) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    model_used = str(data.get("model", PROMPT_REVIEW_MODEL))
    service_tier = str(data.get("service_tier", "") or "")
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("prompt review returned empty response")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(1))
    return parsed, model_used, service_tier


def _clean_addendum(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > PROMPT_REVIEW_MAX_ADDENDUM_CHARS:
        text = text[:PROMPT_REVIEW_MAX_ADDENDUM_CHARS].rstrip() + "\n[prompt-review addendum truncated]"
    return text


def _candidate_with_addendum(original_prompt: str, addendum: str, config: Any) -> str:
    addendum = _clean_addendum(addendum)
    if not addendum:
        return original_prompt
    block = f"{PROMPT_REVIEW_SECTION_TITLE}:\n{addendum}"
    separator = "\n\n"
    max_chars = int(getattr(config, "max_prompt_chars", len(original_prompt) + len(block) + 2) or 0)
    if max_chars and len(original_prompt) + len(separator) + len(block) > max_chars:
        available = max_chars - len(original_prompt) - len(separator) - len(f"{PROMPT_REVIEW_SECTION_TITLE}:\n")
        if available < 160:
            return original_prompt
        addendum = addendum[:available].rstrip() + "\n[prompt-review addendum truncated]"
        block = f"{PROMPT_REVIEW_SECTION_TITLE}:\n{addendum}"
    return f"{original_prompt}{separator}{block}"
