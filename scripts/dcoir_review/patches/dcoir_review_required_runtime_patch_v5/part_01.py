"""Fifth required-coverage layer for DCOIR Review.

This layer fixes the PR #328 failure mode: valid model findings existed under
``result.findings``, but final required-coverage/refill logic rejected several
required sentinel classes and aborted before posting inline review comments.

The patch keeps model review and Markdown rendering deterministic by enforcing a
single required-signal contract keyed by path, right-side line, and semantic kind.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4

PYTHON_YAML_LOAD = v4.PYTHON_YAML_LOAD
PYTHON_SHELL_EXEC = v4.PYTHON_SHELL_EXEC
PYTHON_ENV_TOKEN = "python_env_token_callback"
PS_ENV_TOKEN = "ps_env_token_callback"

REQUIRED_KIND_TITLES = {
    **v4.HARD_REQUIRED_KIND_TITLES,
    v4.YAML_METADATA_SHELL: "Workflow executes pull request metadata in a shell",
    PYTHON_YAML_LOAD: "Unsafe YAML deserialization with `yaml.Loader`",
    PYTHON_SHELL_EXEC: "Python shell execution with caller-controlled command",
    PYTHON_ENV_TOKEN: "Environment token forwarded to request-controlled callback",
    PS_ENV_TOKEN: "Environment token forwarded to request-controlled callback",
}
REQUIRED_KIND_ORDER = (
    v4.YAML_PULL_REQUEST_TARGET,
    v4.YAML_BROAD_WRITE,
    v4.YAML_UNTRUSTED_CHECKOUT,
    v4.YAML_SHELL_PIPE,
    v4.YAML_METADATA_SHELL,
    v4.PS_ACL,
    v4.PS_PROCESS_LAUNCH,
    PS_ENV_TOKEN,
    PYTHON_YAML_LOAD,
    PYTHON_SHELL_EXEC,
    PYTHON_ENV_TOKEN,
)
RANK_KIND_ORDER = (
    *REQUIRED_KIND_ORDER,
    "python_dynamic_exec",
    "python_pickle",
    "python_archive_extract",
    "python_ssrf",
    "ps_dynamic_exec",
    "ps_archive_extract",
    "ps_outbound_token",
)

PY_YAML_LOAD_RE = re.compile(r"\byaml\.load\s*\([^\n]*(?:Loader\s*=\s*yaml\.Loader|yaml\.Loader)", re.IGNORECASE)
PY_SHELL_EXEC_RE = re.compile(r"\bsubprocess\.(?:Popen|run|call|check_call|check_output)\s*\([^\n]*shell\s*=\s*True", re.IGNORECASE)
PY_ENV_RE = re.compile(r"\b(?:os\.environ|os\.getenv)\b|DCOIR_TOKEN", re.IGNORECASE)
PS_ENV_RE = re.compile(r"\$env:|DCOIR_TOKEN|Environment::GetEnvironmentVariable", re.IGNORECASE)
OUTBOUND_RE = re.compile(r"callback|Authorization|Bearer|Invoke-WebRequest|Invoke-RestMethod|requests\.|urlopen|urllib\.request", re.IGNORECASE)
TOKEN_BAD_RE = re.compile(r"\b(?:hard[- ]?coded|literal|redacted|static credential|secret exposure|inline secret|rotate exposed credential|authentication secrets|hardcoded bearer|bearer token hardcoded)\b", re.IGNORECASE)
COMMAND_START_RE = re.compile(r"^\s*(?:python3?|pytest|bandit|pwsh|powershell|grep|rg|yamllint|npm|npx|node|bash|sh)\b")


def _normalize(value: Any) -> str:
    return v4._normalize(value)


def findings_from_result(result: Any) -> list[dict[str, Any]]:
    """Return findings from either top-level findings or nested result.findings."""
    if not isinstance(result, dict):
        return []
    nested = result.get("result")
    if isinstance(nested, dict) and isinstance(nested.get("findings"), list):
        return [finding for finding in nested["findings"] if isinstance(finding, dict)]
    if isinstance(result.get("findings"), list):
        return [finding for finding in result["findings"] if isinstance(finding, dict)]
    return []


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    line = str(text or "")
    if suffix == ".py":
        if PY_YAML_LOAD_RE.search(line):
            return PYTHON_YAML_LOAD
        if PY_SHELL_EXEC_RE.search(line):
            return PYTHON_SHELL_EXEC
        if PY_ENV_RE.search(line) and OUTBOUND_RE.search(line):
            return PYTHON_ENV_TOKEN
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if PS_ENV_RE.search(line) and OUTBOUND_RE.search(line):
            return PS_ENV_TOKEN
    return v4._line_kind(path, text)


def _finding_text(finding: dict[str, Any]) -> str:
    parts = [
        str(finding.get("title", "") or ""),
        str(finding.get("body", "") or ""),
        str(finding.get("validation", "") or ""),
        str(finding.get("_anchored_line_text", "") or ""),
    ]
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    parts.extend(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes"))
    return _normalize("\n".join(parts))


def _semantic_kind(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "")
    anchored = str(finding.get("_anchored_line_text", "") or "")
    anchored_kind = _line_kind(path, anchored)
    if anchored_kind:
        return anchored_kind
    text = _finding_text(finding)
    suffix = Path(path.lower()).suffix
    if suffix == ".py":
        if "yaml.load" in text or "yaml.loader" in text:
            return PYTHON_YAML_LOAD
        if "shell=true" in text or ("subprocess" in text and "shell" in text):
            return PYTHON_SHELL_EXEC
        if ("os.getenv" in text or "os.environ" in text or "dcoir_token" in text) and ("callback" in text or "authorization" in text or "urlopen" in text):
            return PYTHON_ENV_TOKEN
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if ("$env:" in text or "dcoir_token" in text) and ("invoke-webrequest" in text or "invoke-restmethod" in text or "authorization" in text or "callback" in text):
            return PS_ENV_TOKEN
    return v4._semantic_kind(finding)


def _sentinel_kind(sentinel: Any) -> str:
    path = str(getattr(sentinel, "path", "") or "")
    text = str(getattr(sentinel, "text", "") or "")
    line_kind = _line_kind(path, text)
    if line_kind:
        return line_kind
    label_text = _normalize("\n".join(str(getattr(sentinel, key, "") or "") for key in ("label", "detail", "text")))
    if "python" in path.lower():
        if "unsafe deserialization" in label_text or "yaml.loader" in label_text:
            return PYTHON_YAML_LOAD
        if "shell=true" in label_text or "subprocess" in label_text:
            return PYTHON_SHELL_EXEC
    if "metadata" in label_text and "shell" in label_text:
        return v4.YAML_METADATA_SHELL
    return v4._sentinel_kind(sentinel)


def _sentinel_line(sentinel: Any) -> int:
    return v4._sentinel_line(sentinel)


def _finding_line(finding: dict[str, Any]) -> int:
    return v4._finding_line(finding)


def _is_env_kind(kind: str) -> bool:
    return kind in {PYTHON_ENV_TOKEN, PS_ENV_TOKEN, v4.PYTHON_SSRF, v4.PS_OUTBOUND_TOKEN}


def _validation_for_path(path: str, kind: str) -> str:
    lower = str(path or "").lower()
    if lower.endswith(".py"):
        return f"python3 -m py_compile {shlex.quote(str(path or ''))}"
    return v4._validation_for_path(path, kind)


def _template_fields(kind: str, path: str, line_text: str) -> dict[str, Any]:
    if kind in v4.HARD_REQUIRED_KIND_TITLES or kind == v4.YAML_METADATA_SHELL:
        return v4._template_fields(kind, path, line_text)
    notes = {
        PYTHON_YAML_LOAD: "Use `yaml.safe_load(profile_text)` or `yaml.load(..., Loader=yaml.SafeLoader)` when no Python object tags are expected.",
        PYTHON_SHELL_EXEC: "Pass an argument list to `subprocess` with `shell=False`; do not send caller-controlled strings through a shell.",
        PYTHON_ENV_TOKEN: "Keep the token server-side and allowlist callback destinations before adding authorization headers.",
        PS_ENV_TOKEN: "Keep the token server-side and allowlist callback destinations before adding authorization headers.",
    }
    bodies = {
        PYTHON_YAML_LOAD: "This line deserializes YAML with `yaml.Loader`, which can construct unsafe Python objects from untrusted input.",
        PYTHON_SHELL_EXEC: "This line invokes a system shell with caller-controlled command text. Use argument-vector execution without `shell=True`.",
        PYTHON_ENV_TOKEN: "Environment token read from env and forwarded to request-controlled callback. Keep collector tokens server-side and allowlist outbound destinations before sending authorization headers.",
        PS_ENV_TOKEN: "Environment token read from env and forwarded to request-controlled callback. Keep collector tokens server-side and allowlist outbound destinations before sending authorization headers.",
    }
    return {
        "title": REQUIRED_KIND_TITLES.get(kind, "Required DCOIR Review finding"),
        "body": bodies.get(kind, "Review this changed line before merging."),
        "validation": _validation_for_path(path, kind),
        "suggested_replacement": "",
        "fix_guidance": {"language": v4._language_hint(path), "notes": notes.get(kind, "Apply a minimal, evidence-backed fix.")},
    }
