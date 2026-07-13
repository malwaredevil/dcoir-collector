"""Sixteenth required-coverage layer for DCOIR Review.

v16 addresses the #342 live-test selector failure. The previous layers could
run successfully, but they still treated a full 12-comment review as success
while hard/core YAML, Python, and PowerShell risks were omitted. This overlay
keeps Kubernetes optional/bonus, makes workflow and PowerShell aggregate
coverage explicit, detects token-to-PR-metadata URLs, and reports every core
sentinel as posted, aggregate-covered, omitted, duplicate-covered, or
suppressed.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v9_core as core
import dcoir_review_required_runtime_patch_v9_selection as selection
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v12 as v12
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v14 as v14
import dcoir_review_required_runtime_patch_v15 as v15

SentinelKey = tuple[str, int, str]

VERSION = "v16"
PYTHON_DYNAMIC_EXEC = "python_dynamic_exec"

CORE_REQUIRED_KINDS = set(getattr(v12, "REQUIRED_KINDS", set())) | {
    PYTHON_DYNAMIC_EXEC,
    getattr(v13, "PS_PLAINTEXT_SECURE_STRING", "ps_plaintext_secure_string"),
    getattr(v13, "PS_RUN_KEY_PERSISTENCE", "ps_run_key_persistence"),
}

TRACKED_KINDS = set(getattr(v13, "TRACKED_HIGH_RISK_KINDS", set())) | CORE_REQUIRED_KINDS
OPTIONAL_PRESSURE_KINDS = {
    getattr(v13, "TS_INNER_HTML", "ts_inner_html"),
    getattr(v13, "TS_DYNAMIC_EXECUTION", "ts_dynamic_execution"),
}

_ORIGINAL_V13_LINE_KIND = getattr(v13, "_line_kind")
_ORIGINAL_V13_SENTINEL_KEY = getattr(v13, "_sentinel_key")
_ORIGINAL_V13_POSTABLE_KEY = getattr(v13, "_postable_key")
_ORIGINAL_V13_TEMPLATE_FOR_KIND = getattr(v13, "_template_for_kind")
_ORIGINAL_V13_VALIDATION_FOR_KEY = getattr(v13, "_validation_for_key")

PR_METADATA_TOKEN_RE = re.compile(
    r"(?:secrets\.github_token|github_token|authorization\s*:?|bearer)"
    r".*(?:github\.event\.pull_request\.(?:body|title|labels|head\.ref|head\.sha)|pull_request\.(?:body|title|labels|head))"
    r"|(?:github\.event\.pull_request\.(?:body|title|labels|head\.ref|head\.sha)|pull_request\.(?:body|title|labels|head))"
    r".*(?:secrets\.github_token|github_token|authorization\s*:?|bearer)",
    re.I,
)


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_workflow_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    return normalized.startswith(".github/workflows/") and normalized.endswith((".yml", ".yaml"))


def _is_optional_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    return "/optional_" in normalized or basename.startswith("optional_")


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    lower = _normalize(text)
    if _is_workflow_path(path):
        if PR_METADATA_TOKEN_RE.search(lower):
            return v10.YAML_TOKEN_TO_PR_URL
        if "pull_request_target" in lower:
            return v4.YAML_PULL_REQUEST_TARGET
        if "write-all" in lower or re.search(r"\b[a-z_-]+\s*:\s*write\b", lower):
            return v4.YAML_BROAD_WRITE
        if "github.event.pull_request.head" in lower or "github.head_ref" in lower:
            return v4.YAML_UNTRUSTED_CHECKOUT
        if ("curl" in lower or "wget" in lower) and ("| sh" in lower or "| bash" in lower):
            return v4.YAML_SHELL_PIPE
        if "github.event.pull_request" in lower and any(token in lower for token in ("bash -lc", "sh -c", "run:", "shell:")):
            return v4.YAML_METADATA_SHELL
    if suffix == ".py":
        if "pickle.loads" in lower or "pickle.load(" in lower:
            return v9.PYTHON_PICKLE_LOAD
        if "yaml.load" in lower:
            return v5.PYTHON_YAML_LOAD
        if re.search(r"\b(?:eval|exec|compile)\s*\(", lower):
            return PYTHON_DYNAMIC_EXEC
        if "shell=true" in lower or "os.system(" in lower or "os.popen(" in lower:
            return v5.PYTHON_SHELL_EXEC
        if ("requests." in lower or "urlopen" in lower) and (
            "authorization" in lower or "bearer" in lower or "dcoir_token" in lower or "callback" in lower
        ):
            return v5.PYTHON_ENV_TOKEN
        if "extractall" in lower:
            return v11.PYTHON_ARCHIVE_EXTRACT
        if any(token in lower for token in ("write_text(", "write_bytes(", ".open(", "open(")):
            return v11.PYTHON_PATH_WRITE
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in lower or re.search(r"\biex\b", lower):
            return v9.PS_DYNAMIC_EXEC
        if "convertto-securestring" in lower and "-asplaintext" in lower:
            return v13.PS_PLAINTEXT_SECURE_STRING
        if "filesystemaccessrule" in lower or "set-acl" in lower:
            return v4.PS_ACL
        if "start-process" in lower:
            return v4.PS_PROCESS_LAUNCH
        if ("invoke-webrequest" in lower or "invoke-restmethod" in lower) and (
            "authorization" in lower or "bearer" in lower or "$env:dcoir_token" in lower
        ):
            return v5.PS_ENV_TOKEN
        if "currentversion\\run" in lower:
            return v13.PS_RUN_KEY_PERSISTENCE
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        if ".innerhtml" in lower or ".outerhtml" in lower or "insertadjacenthtml" in lower:
            return v13.TS_INNER_HTML
        if "settimeout(" in lower or "setinterval(" in lower or "new function(" in lower:
            return v13.TS_DYNAMIC_EXECUTION
    return _ORIGINAL_V13_LINE_KIND(path, text)


def _sentinel_key(sentinel: Any) -> SentinelKey:
    path = str(getattr(sentinel, "path", "") or "")
    line = _line_number(getattr(sentinel, "line", 0))
    text = str(getattr(sentinel, "text", "") or "")
    kind = _line_kind(path, text) or _ORIGINAL_V13_SENTINEL_KEY(sentinel)[2]
    return path, line, kind


def _postable_key(finding: dict[str, Any]) -> SentinelKey:
    raw = finding.get("_risk_sentinel_key")
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return str(raw[0] or ""), _line_number(raw[1]), str(raw[2] or "")
    path, line, kind = _ORIGINAL_V13_POSTABLE_KEY(finding)
    text = "\n".join(str(finding.get(name, "") or "") for name in ("_anchored_line_text", "title", "body", "description"))
    return path, line, _line_kind(path, text) or kind


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind in {v4.YAML_BROAD_WRITE, v11.PYTHON_ARCHIVE_EXTRACT}:
        return path, 0, kind
    return path, line, kind


def _coverage_from_finding(finding: dict[str, Any]) -> set[SentinelKey]:
    keys = {_coverage_key(_postable_key(finding))}
    raw_keys = finding.get("covered_risk_sentinel_keys")
    if isinstance(raw_keys, list):
        for raw in raw_keys:
            if isinstance(raw, (list, tuple)) and len(raw) == 3:
                keys.add(_coverage_key((str(raw[0] or ""), _line_number(raw[1]), str(raw[2] or ""))))
    return {key for key in keys if key[0] and key[2]}


def _kind_rank(kind: str) -> int:
    order = {
        v10.YAML_TOKEN_TO_PR_URL: 0,
        v4.YAML_METADATA_SHELL: 1,
        v4.YAML_SHELL_PIPE: 2,
        v4.YAML_PULL_REQUEST_TARGET: 3,
        v4.YAML_BROAD_WRITE: 4,
        v4.YAML_UNTRUSTED_CHECKOUT: 5,
        v9.PYTHON_PICKLE_LOAD: 10,
        v5.PYTHON_YAML_LOAD: 11,
        PYTHON_DYNAMIC_EXEC: 12,
        v5.PYTHON_SHELL_EXEC: 13,
        v5.PYTHON_ENV_TOKEN: 14,
        v11.PYTHON_ARCHIVE_EXTRACT: 15,
        v11.PYTHON_PATH_WRITE: 16,
        v9.PS_DYNAMIC_EXEC: 20,
        v4.PS_PROCESS_LAUNCH: 21,
        v5.PS_ENV_TOKEN: 22,
        v13.PS_RUN_KEY_PERSISTENCE: 23,
        v4.PS_ACL: 24,
        v13.PS_PLAINTEXT_SECURE_STRING: 25,
        v13.TS_INNER_HTML: 80,
        v13.TS_DYNAMIC_EXECUTION: 81,
    }
    return order.get(str(kind or ""), 99)


def _family(kind: str) -> str:
    if kind.startswith("yaml_"):
        return "yaml"
    if kind.startswith("python_"):
        return "python"
    if kind.startswith("ps_"):
        return "powershell"
    if kind.startswith("ts_"):
        return "typescript"
    if kind.startswith("k8s_"):
        return "kubernetes"
    return "other"
