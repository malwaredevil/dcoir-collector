"""Required-coverage runtime patches for DCOIR Review.

This module runs after the broader runtime and strict fix-synthesis patches. It
keeps the final review output deterministic while tightening the places where
live testing still showed required findings could be crowded out or softened.
"""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path
from typing import Any


CURL_SHELL_RE = re.compile(r"\b(?:curl|wget)\b[^\n]*(?:\|\s*(?:bash|sh)\b|\bbash\b|\bsh\b)", re.IGNORECASE)
GH_WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?:permissions\s*:\s*write-all|"
    r"(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\s*:\s*write)\b",
    re.IGNORECASE,
)
GH_UNTRUSTED_CHECKOUT_RE = re.compile(r"github\.event\.pull_request\.head\.(?:ref|sha)|github\.head_ref", re.IGNORECASE)
PY_DYNAMIC_EXEC_RE = re.compile(r"\b(?:eval|exec)\s*\(")
PY_SHELL_EXEC_RE = re.compile(r"\bsubprocess\.\w+\([^#\n]*\bshell\s*=\s*True\b", re.IGNORECASE)
PY_SSRF_TOKEN_RE = re.compile(
    r"\b(?:requests\.(?:get|post|put|request)|urllib\.request\.(?:Request|urlopen)|httpx\.(?:get|post|request))\b|"
    r"\b(?:Authorization|Bearer|callback_url|callback|os\.environ|TOKEN|SECRET)\b",
    re.IGNORECASE,
)
PS_ACL_RE = re.compile(r"\b(?:FileSystemAccessRule|Set-Acl|Everyone|FullControl)\b", re.IGNORECASE)
PS_OUTBOUND_RE = re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod|iwr)\b|\b(?:Authorization|Bearer)\b", re.IGNORECASE)
INTERNAL_VALIDATION_RE = re.compile(
    r"(?:provider_pr_review|openrouter_pr_review|dcoir_review_.*selftest|reviewer runner selftest|run the relevant)",
    re.IGNORECASE,
)
HARDCODED_SECRET_RE = re.compile(r"\b(?:hard[- ]?coded|redacted)\s+(?:secret|token|credential|api key)\b", re.IGNORECASE)
REDACTED_SECRET_RE = re.compile(r"\[redacted[-_ ]?(?:secret|token|credential|api key)\]", re.IGNORECASE)
MARKDOWN_DUNDER_RE = re.compile(r"(?<![`\\])\b(__[A-Za-z][A-Za-z0-9_]*__)\b(?!`)")

YAML_REQUIRED_KIND_TITLES = {
    "yaml_pull_request_target": "Privileged `pull_request_target` workflow context",
    "yaml_broad_write": "GitHub Actions workflow grants write permissions",
    "yaml_untrusted_checkout": "Privileged workflow checks out untrusted PR code",
    "yaml_shell_pipe": "Workflow pipes a network installer into a shell",
}

YAML_SENTINEL_METADATA = {
    "yaml_pull_request_target": (
        "DCOIR YAML pull_request_target",
        "pull_request_target runs with base-repository privileges and must not execute untrusted PR code",
    ),
    "yaml_broad_write": (
        "DCOIR YAML broad write permission",
        "workflow token permissions grant write privileges and must be narrowed to required scopes",
    ),
    "yaml_untrusted_checkout": (
        "DCOIR YAML untrusted checkout ref",
        "privileged workflows must not check out PR-controlled refs or head SHAs before executing code",
    ),
    "yaml_shell_pipe": (
        "DCOIR YAML shell pipe installer",
        "network-fetched installer content is piped directly into a shell without pinning or verification",
    ),
}

COLLAPSE_TO_FILE_KINDS = {"python_ssrf", "ps_acl"}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _clean_public_text(value: Any) -> str:
    text = str(value or "")
    text = "\n".join(line for line in text.splitlines() if "deterministic risk sentinel" not in line.lower())
    return MARKDOWN_DUNDER_RE.sub(r"`\1`", text.strip())


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


def _line_semantic_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    normalized = _normalize(text)
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in normalized:
            return "yaml_pull_request_target"
        if GH_WRITE_PERMISSION_RE.search(text):
            return "yaml_broad_write"
        if GH_UNTRUSTED_CHECKOUT_RE.search(text):
            return "yaml_untrusted_checkout"
        if CURL_SHELL_RE.search(text):
            return "yaml_shell_pipe"
    if suffix == ".py":
        if PY_SHELL_EXEC_RE.search(text):
            return "python_shell_exec"
        if "extractall" in normalized or "tarfile" in normalized or "shutil.unpack_archive" in normalized:
            return "python_archive_extract"
        if PY_SSRF_TOKEN_RE.search(text):
            return "python_ssrf"
        if PY_DYNAMIC_EXEC_RE.search(text):
            return "python_dynamic_exec"
        if "pickle.loads" in normalized or "pickle.load" in normalized:
            return "python_pickle"
        if "yaml.load" in normalized or "yaml.loader" in normalized:
            return "python_yaml_load"
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in normalized:
            return "ps_dynamic_exec"
        if "expand-archive" in normalized:
            return "ps_archive_extract"
        if PS_ACL_RE.search(text):
            return "ps_acl"
        if PS_OUTBOUND_RE.search(text):
            return "ps_outbound_token"
        if "start-process" in normalized:
            return "ps_process_launch"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        if "exec(" in normalized or "execsync(" in normalized or "spawn(" in normalized:
            return "ts_command_exec"
    return ""


def _semantic_kind(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "")
    anchored = str(finding.get("_anchored_line_text", "") or "")
    line_kind = _line_semantic_kind(path, anchored)
    if line_kind:
        return line_kind
    text = _finding_text(finding)
    suffix = Path(path.lower()).suffix
    if suffix in {".yml", ".yaml"}:
        if "shell pipe" in text or (("curl" in text or "wget" in text) and ("bash" in text or " sh" in text)):
            return "yaml_shell_pipe"
        if "untrusted checkout" in text or "github.event.pull_request.head" in text or "github.head_ref" in text or "head ref" in text or "head sha" in text:
            return "yaml_untrusted_checkout"
        if "write-all" in text or ("permissions" in text and "write" in text):
            return "yaml_broad_write"
        if "pull_request_target" in text:
            return "yaml_pull_request_target"
    if suffix == ".py":
        if "shell=true" in text or "shell true" in text or "subprocess" in text and "shell" in text:
            return "python_shell_exec"
        if "extractall" in text or "tarfile" in text or "archive extraction" in text:
            return "python_archive_extract"
        if "ssrf" in text or "callback" in text or "urlopen" in text or "authorization" in text or "bearer" in text or "token exfil" in text:
            return "python_ssrf"
        if "eval" in text or "exec" in text or "dynamic code" in text:
            return "python_dynamic_exec"
        if "pickle" in text:
            return "python_pickle"
        if "yaml.load" in text or "yaml.loader" in text:
            return "python_yaml_load"
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in text:
            return "ps_dynamic_exec"
        if "expand-archive" in text:
            return "ps_archive_extract"
        if "acl" in text or "everyone" in text or "fullcontrol" in text or "set-acl" in text:
            return "ps_acl"
        if "invoke-webrequest" in text or "invoke-restmethod" in text or "bearer" in text:
            return "ps_outbound_token"
        if "start-process" in text:
            return "ps_process_launch"
    return ""


def _sentinel_kind(sentinel: Any) -> str:
    path = str(getattr(sentinel, "path", "") or "")
    text = str(getattr(sentinel, "text", "") or "")
    line_kind = _line_semantic_kind(path, text)
    if line_kind:
        return line_kind
    label = _normalize(getattr(sentinel, "label", ""))
    detail = _normalize(getattr(sentinel, "detail", ""))
    combined = f"{label}\n{detail}\n{_normalize(text)}"
    if "shell pipe" in combined or "curl" in combined and ("bash" in combined or " sh" in combined):
        return "yaml_shell_pipe"
    if "untrusted checkout" in combined or "head ref" in combined or "head sha" in combined or "github.event.pull_request.head" in combined:
        return "yaml_untrusted_checkout"
    if "broad write" in combined or "write permission" in combined or "write-all" in combined:
        return "yaml_broad_write"
    if "pull_request_target" in combined:
        return "yaml_pull_request_target"
    return _semantic_kind({"path": path, "title": combined, "body": combined})


def _candidate_kind(candidate: Any) -> str:
    return _line_semantic_kind(str(getattr(candidate, "path", "") or ""), str(getattr(candidate, "text", "") or ""))
