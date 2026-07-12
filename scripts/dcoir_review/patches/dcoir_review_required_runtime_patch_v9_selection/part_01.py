"""Required sentinel fallback and ranking hooks for DCOIR Review v9."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5

from dcoir_review_required_runtime_patch_v9_core import (
    PS_DYNAMIC_EXEC,
    PYTHON_PICKLE_LABEL,
    PYTHON_PICKLE_LOAD,
    PYTHON_PICKLE_DETAIL,
    SELECTION_SUMMARY,
    SentinelKey,
    _dedupe,
    _expected_by_line,
    _key_text,
    _line_number,
    _normalize,
    _postable_key,
    _required_sentinels,
    _rewrite_validation,
    _semantic_mismatch,
    _sentinel_key,
    _spare_priority,
    _validation_for_key,
    _yaml_load_arg,
)
from dcoir_review_required_runtime_patch_v9_prompting import _ensure_prompt_review

def _iter_added_diff_lines(diff: str) -> list[tuple[str, int, str]]:
    result: list[tuple[str, int, str]] = []
    current_path = ""
    new_line = 0
    for raw_line in str(diff or "").splitlines():
        if raw_line.startswith("+++ b/"):
            current_path = raw_line[6:]
        elif raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw_line)
            new_line = int(match.group(1)) if match else 0
        elif current_path and new_line:
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                result.append((current_path, new_line, raw_line[1:]))
                new_line += 1
            elif raw_line.startswith(" ") or raw_line == "":
                new_line += 1
    return result


def _patch_pickle_sentinels(owner: Any, sentinel_owner: Any | None = None) -> None:
    original = getattr(owner, "_dcoir_required_v9_original_detect_risk_sentinels", None)
    if original is None:
        original = getattr(owner, "detect_risk_sentinels", None)
        owner._dcoir_required_v9_original_detect_risk_sentinels = original
    if not callable(original):
        return

    def detect_risk_sentinels(diff: str, *args: Any, **kwargs: Any) -> list[Any]:
        sentinels = list(original(diff, *args, **kwargs))
        existing = {_sentinel_key(item) for item in sentinels}
        risk_sentinel_type = getattr(owner, "RiskSentinel", None) or getattr(sentinel_owner, "RiskSentinel", None)
        if risk_sentinel_type is None:
            return sentinels
        for path, line, text in _iter_added_diff_lines(diff):
            if Path(path.lower()).suffix != ".py":
                continue
            if "pickle.loads" not in _normalize(text) and "pickle.load(" not in _normalize(text):
                continue
            comment_checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)
            if callable(comment_checker) and comment_checker(path, text):
                continue
            key = (path, line, PYTHON_PICKLE_LOAD)
            if key in existing:
                continue
            sentinels.append(risk_sentinel_type(path=path, line=line, label=PYTHON_PICKLE_LABEL, detail=PYTHON_PICKLE_DETAIL, text=text))
            existing.add(key)
        return sentinels

    owner.detect_risk_sentinels = detect_risk_sentinels


def _fallback_for_sentinel(hardened: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    fallback = _known_fallback_for_key(key, str(getattr(sentinel, "text", "") or ""))
    if not fallback:
        fallback_fn = getattr(hardened, "risk_sentinel_fallback_finding", None)
        fallback = fallback_fn(sentinel, config) if callable(fallback_fn) else {}
    if not isinstance(fallback, dict) or not fallback:
        fallback = {
            "title": f"Required changed-line risk: {getattr(sentinel, 'label', key[2])}",
            "severity": "high",
            "confidence": 0.99,
            "path": key[0],
            "line": key[1],
            "body": str(getattr(sentinel, "detail", "") or "This changed line matched a required deterministic risk sentinel."),
            "suggested_replacement": "",
            "validation": getattr(hardened, "primary_validation_command", lambda _config: "")(config),
        }
    fallback["_risk_sentinel_key"] = [key[0], key[1], key[2]]
    fallback["_risk_sentinel_kind"] = key[2]
    fallback["_anchored_line_text"] = str(getattr(sentinel, "text", "") or "")
    return fallback


def _priority_bucket_for_sentinel(key: SentinelKey, required_keys: set[SentinelKey]) -> str:
    path, _line, kind = key
    suffix = Path(path.lower()).suffix
    if key in required_keys:
        return "hard-required"
    if kind in {PYTHON_PICKLE_LOAD, PS_DYNAMIC_EXEC}:
        return "required-adjacent"
    if suffix in {".py", ".ps1", ".psm1", ".psd1", ".yml", ".yaml"}:
        return "high-risk"
    return "optional"


def _sentinel_summary_record(sentinel: Any, required_keys: set[SentinelKey], selected_keys: set[SentinelKey], limit: int) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    reason = "omitted_due_to_inline_budget" if len(selected_keys) >= limit else "not_selected"
    return {
        "path": key[0],
        "line": key[1],
        "kind": key[2],
        "priority_bucket": _priority_bucket_for_sentinel(key, required_keys),
        "reason": reason,
        "label": str(getattr(sentinel, "label", "") or ""),
        "detail": str(getattr(sentinel, "detail", "") or "")[:240],
        "text": str(getattr(sentinel, "text", "") or "")[:240],
    }


def _known_fallback_for_key(key: SentinelKey, line_text: str) -> dict[str, Any]:
    path, line, kind = key
    titles = {
        v4.YAML_PULL_REQUEST_TARGET: "Privileged `pull_request_target` workflow context",
        v4.YAML_BROAD_WRITE: "GitHub Actions workflow grants write permissions",
        v4.YAML_UNTRUSTED_CHECKOUT: "Privileged workflow checks out untrusted PR code",
        v4.YAML_SHELL_PIPE: "Workflow pipes a network installer into a shell",
        v4.YAML_METADATA_SHELL: "Workflow executes pull request metadata in a shell",
        v4.PS_ACL: "PowerShell broad ACL grant exposes collector output",
        v4.PS_PROCESS_LAUNCH: "PowerShell caller-controlled process launch",
        v5.PS_ENV_TOKEN: "Environment token forwarded to request-controlled callback",
        PYTHON_PICKLE_LOAD: "Unsafe pickle deserialization",
        v5.PYTHON_YAML_LOAD: "Unsafe YAML deserialization",
        v5.PYTHON_SHELL_EXEC: "Python shell execution with caller-controlled command",
        v5.PYTHON_ENV_TOKEN: "Environment token forwarded to request-controlled callback",
    }
    bodies = {
        v4.YAML_PULL_REQUEST_TARGET: "`pull_request_target` runs with base-repository privileges. Do not execute untrusted PR code in this workflow context.",
        v4.YAML_BROAD_WRITE: "This workflow grants broad write token permissions. Narrow `permissions` to the minimum scopes required.",
        v4.YAML_UNTRUSTED_CHECKOUT: "This privileged workflow checks out PR-controlled code. Do not combine privileged workflow context with PR-controlled refs or head SHAs.",
        v4.YAML_SHELL_PIPE: "This workflow pipes network-fetched content directly into a shell. Download the content to a file, verify a pinned checksum or signature, and execute only verified content.",
        v4.YAML_METADATA_SHELL: "This workflow passes pull request metadata to a shell. Pull request title, body, and head metadata are attacker-controlled and must not be executed.",
        v4.PS_ACL: "This PowerShell change grants broad filesystem ACL rights. Narrow the identity and rights to the minimum collector path access required.",
        v4.PS_PROCESS_LAUNCH: "This line launches a caller-controlled executable or argument string. Use an allowlisted command table or remove the launch from the collector path.",
        v5.PS_ENV_TOKEN: "Environment token read from env and forwarded to request-controlled callback. Keep collector tokens server-side and allowlist outbound destinations before sending authorization headers.",
        PYTHON_PICKLE_LOAD: "Pickle deserialization can execute code. Replace pickle input with a safe serialization format, or only load signed data from a trusted source.",
        v5.PYTHON_YAML_LOAD: "This line uses unsafe YAML deserialization. Use `yaml.safe_load(...)` unless trusted Python object tags are required.",
        v5.PYTHON_SHELL_EXEC: "This line invokes a system shell with caller-controlled command text. Use argument-vector execution without `shell=True`.",
        v5.PYTHON_ENV_TOKEN: "Environment token read from env and forwarded to request-controlled callback. Keep collector tokens server-side and allowlist outbound destinations before sending authorization headers.",
    }
    notes = {
        v4.YAML_UNTRUSTED_CHECKOUT: "Use a trusted base ref or avoid checkout in privileged `pull_request_target` jobs.",
        v5.PYTHON_YAML_LOAD: f"Use `yaml.safe_load({_yaml_load_arg(line_text)})` when no Python object tags are expected.",
        PYTHON_PICKLE_LOAD: "Prefer JSON, YAML safe loading, or another data format that does not execute code during parsing.",
    }
    if kind not in titles:
        return {}
    return {
        "_dcoir_v9_known_fallback": True,
        "title": titles[kind],
        "severity": "critical" if kind in {v4.YAML_PULL_REQUEST_TARGET, v4.YAML_SHELL_PIPE, v4.PS_PROCESS_LAUNCH, PYTHON_PICKLE_LOAD} else "high",
        "confidence": 0.99,
        "path": path,
        "line": line,
        "body": bodies[kind],
        "suggested_replacement": "",
        "validation": _validation_for_key(kind, path, line),
        "fix_guidance": {
            "language": "yaml" if Path(path.lower()).suffix in {".yml", ".yaml"} else "powershell" if Path(path.lower()).suffix in {".ps1", ".psm1", ".psd1"} else "python" if Path(path.lower()).suffix == ".py" else "text",
            "notes": notes.get(kind, "Apply a minimal, evidence-backed fix for the changed line."),
        },
    }
