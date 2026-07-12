"""Fourth required-coverage layer for DCOIR Review.

This final connector-sized layer owns the deterministic user-facing shape for
hard-required findings. Earlier layers may detect, synthesize, and repair, but
v4 is the last authority for required semantic templates, exact remove blocks,
rendered-output safety, final dedupe, and required refill before optional
findings are allowed to consume review budget.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v2 as v2
import dcoir_review_required_runtime_patch_v3 as v3
import dcoir_review_required_runtime_patches as required

YAML_PULL_REQUEST_TARGET = "yaml_pull_request_target"
YAML_BROAD_WRITE = "yaml_broad_write"
YAML_UNTRUSTED_CHECKOUT = "yaml_untrusted_checkout"
YAML_SHELL_PIPE = "yaml_shell_pipe"
YAML_METADATA_SHELL = v3.YAML_METADATA_SHELL_KIND
PS_ACL = v2.PS_ACL_KIND
PS_PROCESS_LAUNCH = v3.PS_PROCESS_KIND
PYTHON_SHELL_EXEC = "python_shell_exec"
PYTHON_YAML_LOAD = "python_yaml_load"
PYTHON_SSRF = "python_ssrf"
PS_OUTBOUND_TOKEN = "ps_outbound_token"

HARD_REQUIRED_KIND_TITLES = {
    YAML_PULL_REQUEST_TARGET: "Privileged `pull_request_target` workflow context",
    YAML_BROAD_WRITE: "GitHub Actions workflow grants write permissions",
    YAML_UNTRUSTED_CHECKOUT: "Privileged workflow checks out untrusted PR code",
    YAML_SHELL_PIPE: "Workflow pipes a network installer into a shell",
    PS_ACL: "PowerShell broad ACL grant exposes collector output",
    PS_PROCESS_LAUNCH: "PowerShell caller-controlled process launch",
}
OPTIONAL_KIND_TITLES = {
    YAML_METADATA_SHELL: "Workflow executes pull request metadata in a shell",
}
HARD_REQUIRED_KIND_ORDER = (
    YAML_PULL_REQUEST_TARGET,
    YAML_BROAD_WRITE,
    YAML_UNTRUSTED_CHECKOUT,
    YAML_SHELL_PIPE,
    PS_ACL,
    PS_PROCESS_LAUNCH,
)
RANK_KIND_ORDER = (
    *HARD_REQUIRED_KIND_ORDER,
    PYTHON_YAML_LOAD,
    PYTHON_SHELL_EXEC,
    PYTHON_SSRF,
    PS_OUTBOUND_TOKEN,
    "python_dynamic_exec",
    "python_pickle",
    "python_archive_extract",
    "ps_dynamic_exec",
    "ps_archive_extract",
    YAML_METADATA_SHELL,
)

WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?:permissions\s*:\s*write-all|"
    r"(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\s*:\s*write)\b",
    re.IGNORECASE,
)
SHELL_PIPE_RE = re.compile(r"\b(?:curl|wget)\b[^\n]*(?:\|\s*(?:bash|sh)\b)", re.IGNORECASE)
PR_METADATA_RE = re.compile(r"github\.event\.pull_request\.(?:body|title|head\.ref|head\.sha)", re.IGNORECASE)
SHELL_EXEC_RE = re.compile(r"(?:\|\s*(?:bash|sh)\b|\b(?:bash|sh)\s+-c\b|\b(?:bash|sh)\b)", re.IGNORECASE)
PS_START_PROCESS_RE = re.compile(r"\bStart-Process\b", re.IGNORECASE)
PS_ACL_RE = re.compile(r"\b(?:Set-Acl|FileSystemAccessRule|FullControl|Everyone)\b", re.IGNORECASE)
ENV_TOKEN_RE = re.compile(
    r"(?:os\.environ|os\.getenv|\$env:|process\.env|Environment::GetEnvironmentVariable|DCOIR_TOKEN)",
    re.IGNORECASE,
)
OUTBOUND_RE = re.compile(
    r"(?:callback|Authorization|Bearer|Invoke-WebRequest|Invoke-RestMethod|requests\.(?:get|post|put|request)|urlopen)",
    re.IGNORECASE,
)
COMMAND_START_RE = re.compile(r"^\s*(?:python3?|pytest|bandit|pwsh|powershell|grep|rg|yamllint|npm|npx|node|bash|sh)\b")
PROSE_VALIDATION_RE = re.compile(r"\b(?:scan for|without validatation|without validation|manually verify|guidance|expected after fix|assert text\.strip)\b", re.IGNORECASE)
YAML_CODE_LINE_RE = re.compile(r"^\s*(?:[-?]\s+)?[A-Za-z0-9_.${}/ -]+\s*:")
POWERSHELL_CODE_LINE_RE = re.compile(r"^\s*(?:#|\$[A-Za-z_][A-Za-z0-9_]*\b|[A-Za-z]+-[A-Za-z]+(?:\s|$)|(?:if|foreach|for|while|try|catch|finally|param|function)\b)", re.IGNORECASE)
PYTHON_CODE_LINE_RE = re.compile(r"^\s*(?:#|from\s+\S+\s+import\s+|import\s+|def\s+|class\s+|if\s+|elif\s+|else:|for\s+|while\s+|try:|except\b|finally:|with\s+|return\b|raise\b|assert\b|[A-Za-z_][A-Za-z0-9_]*\s*=)")
BANNED_ENV_PROSE_RE = re.compile(
    r"\b(?:static credential|secret exposure|environment token value|hard[- ]?coded|literal bearer|literal token|inline secret|redacted[-_ ]?secret|rotate exposed credential|authentication secrets)\b",
    re.IGNORECASE,
)
DUPLICATE_WHITESPACE_RE = re.compile(r"\n{3,}")


def _normalize(value: Any) -> str:
    return required._normalize(value)


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _language_hint(path: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    return {
        ".cjs": "javascript",
        ".js": "javascript",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".sh": "bash",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def _metadata_shell_line(text: str) -> bool:
    line = str(text or "")
    return PR_METADATA_RE.search(line) is not None and SHELL_EXEC_RE.search(line) is not None


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    line = str(text or "")
    normalized = _normalize(line)
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in normalized:
            return YAML_PULL_REQUEST_TARGET
        if WRITE_PERMISSION_RE.search(line):
            return YAML_BROAD_WRITE
        if "github.event.pull_request.head" in normalized or "github.head_ref" in normalized:
            return YAML_UNTRUSTED_CHECKOUT
        if SHELL_PIPE_RE.search(line):
            return YAML_SHELL_PIPE
        if _metadata_shell_line(line):
            return YAML_METADATA_SHELL
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if PS_START_PROCESS_RE.search(line):
            return PS_PROCESS_LAUNCH
        if PS_ACL_RE.search(line):
            return PS_ACL
    return v3._line_kind(path, text)


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
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in text:
            return YAML_PULL_REQUEST_TARGET
        if "write-all" in text or ("permissions" in text and " write" in text) or "broad write" in text:
            return YAML_BROAD_WRITE
        if "github.event.pull_request.head" in text or "github.head_ref" in text or ("untrusted" in text and "checkout" in text):
            return YAML_UNTRUSTED_CHECKOUT
        if ("curl" in text or "wget" in text) and ("|" in text or "pipe" in text) and ("bash" in text or " sh" in text):
            return YAML_SHELL_PIPE
        if "pull request metadata" in text or ("github.event.pull_request" in text and "bash" in text):
            return YAML_METADATA_SHELL
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "start-process" in text:
            return PS_PROCESS_LAUNCH
        if "set-acl" in text or "filesystemaccessrule" in text or "fullcontrol" in text or "everyone" in text:
            return PS_ACL
        if "invoke-webrequest" in text or "invoke-restmethod" in text or "bearer" in text:
            return PS_OUTBOUND_TOKEN
    if suffix == ".py":
        if "yaml.load" in text or "yaml.loader" in text:
            return PYTHON_YAML_LOAD
        if "shell=true" in text or "subprocess" in text and "shell" in text:
            return PYTHON_SHELL_EXEC
        if "requests." in text or "callback" in text or "ssrf" in text:
            return PYTHON_SSRF
    return v3._semantic_kind(finding)


def _sentinel_kind(sentinel: Any) -> str:
    path = str(getattr(sentinel, "path", "") or "")
    text = str(getattr(sentinel, "text", "") or "")
    line_kind = _line_kind(path, text)
    if line_kind:
        return line_kind
    return v3._sentinel_kind(sentinel)


def _sentinel_line(sentinel: Any) -> int:
    return _line_number(getattr(sentinel, "line", 0))


def _finding_line(finding: dict[str, Any]) -> int:
    return _line_number(finding.get("line", 0))


def _is_env_token_callback(finding: dict[str, Any]) -> bool:
    haystack = "\n".join(
        str(value or "")
        for value in (
            finding.get("title"),
            finding.get("body"),
            finding.get("validation"),
            finding.get("_anchored_line_text"),
        )
    )
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    haystack += "\n" + "\n".join(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes"))
    return ENV_TOKEN_RE.search(haystack) is not None and OUTBOUND_RE.search(haystack) is not None
