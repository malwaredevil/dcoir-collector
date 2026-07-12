"""Ninth required-coverage layer for DCOIR Review.

This connector-safe layer keeps the final reviewer boring and deterministic:
OpenRouter Auto prompt-engineering preflights are visible and enforced before
Pareto calls, inline comments do not carry model footers, selected comments must
match the semantic risk at their changed line, Python pickle sinks become
required-adjacent coverage when present, and validation snippets avoid fragile
quoting.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v8 as v8

SentinelKey = tuple[str, int, str]

PYTHON_PICKLE_LOAD = "python_pickle_load"
PYTHON_PICKLE_LABEL = "Python unsafe pickle deserialization"
PYTHON_PICKLE_DETAIL = (
    "pickle.load/pickle.loads can execute code during deserialization; use a safe serialization "
    "format or a strictly validated, signed, trusted pickle source"
)
PS_DYNAMIC_EXEC = "ps_dynamic_exec"
INLINE_MODEL_FOOTER_RE = re.compile(r"\n{0,2}(?:_|\*)?Reviewed with [^\n]+?\.?(?:_|\*)?\s*$", re.I)

PROMPT_REVIEW_EVENTS: list[dict[str, Any]] = []
PROMPT_REVIEW_CALLS: list[dict[str, Any]] = []
PARETO_CALL_EVENTS: list[dict[str, Any]] = []
PROMPT_REVIEW_FAILURES: list[dict[str, Any]] = []
SELECTION_SUMMARY: dict[str, Any] = {}
EVENT_LIMIT = 40


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize(value: Any) -> str:
    return v5._normalize(value)


def _canonical_kind(kind: str) -> str:
    if kind == getattr(v4, "PS_OUTBOUND_TOKEN", "ps_outbound_token"):
        return v5.PS_ENV_TOKEN
    return kind


def _looks_like_python_env_token_callback(value: str) -> bool:
    text = _normalize(value)
    has_env = "dcoir_token" in text or "os.environ" in text or "os.getenv" in text
    has_outbound = (
        "callback" in text
        or "authorization" in text
        or "bearer" in text
        or "request-controlled" in text
        or "requests." in text
        or "urlopen" in text
        or "urllib.request" in text
    )
    return has_env and has_outbound


def _key_text(key: SentinelKey) -> str:
    return f"{key[0]}:{key[1]} {key[2]}"


def _claim_text(finding: dict[str, Any]) -> str:
    return _normalize(
        "\n".join(
            str(part or "")
            for part in [
                finding.get("title"),
                finding.get("body"),
                finding.get("description"),
                finding.get("_anchored_line_text"),
            ]
        )
    )


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    line = str(text or "")
    line_norm = _normalize(line)
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in line_norm:
            return v4.YAML_PULL_REQUEST_TARGET
        if v4.WRITE_PERMISSION_RE.search(line):
            return v4.YAML_BROAD_WRITE
        if "github.event.pull_request.head" in line_norm or "github.head_ref" in line_norm:
            return v4.YAML_UNTRUSTED_CHECKOUT
        if v4.SHELL_PIPE_RE.search(line):
            return v4.YAML_SHELL_PIPE
        if v4._metadata_shell_line(line):
            return v4.YAML_METADATA_SHELL
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if re.search(r"\b(?:Invoke-Expression|IEX)\b", line, re.I):
            return PS_DYNAMIC_EXEC
        if v4.PS_START_PROCESS_RE.search(line):
            return v4.PS_PROCESS_LAUNCH
        if v4.PS_ACL_RE.search(line):
            return v4.PS_ACL
        if v5.PS_ENV_RE.search(line) and v5.OUTBOUND_RE.search(line):
            return v5.PS_ENV_TOKEN
    if suffix == ".py":
        if "pickle.loads" in line_norm or "pickle.load(" in line_norm:
            return PYTHON_PICKLE_LOAD
        if v5.PY_YAML_LOAD_RE.search(line):
            return v5.PYTHON_YAML_LOAD
        if v5.PY_SHELL_EXEC_RE.search(line):
            return v5.PYTHON_SHELL_EXEC
        if v5.PY_ENV_RE.search(line) and v5.OUTBOUND_RE.search(line):
            return v5.PYTHON_ENV_TOKEN
    return v5._line_kind(path, text)


def _claimed_kinds(finding: dict[str, Any]) -> set[str]:
    path = str(finding.get("path", "") or "")
    text = _claim_text(finding)
    suffix = Path(path.lower()).suffix
    kinds: set[str] = set()
    if suffix == ".py":
        if "pickle.loads" in text or "pickle.load(" in text or ("pickle" in text and "deserial" in text):
            kinds.add(PYTHON_PICKLE_LOAD)
        if "yaml.load" in text or "yaml.loader" in text:
            kinds.add(v5.PYTHON_YAML_LOAD)
        if "shell=true" in text or ("subprocess" in text and "shell" in text):
            kinds.add(v5.PYTHON_SHELL_EXEC)
        if ("os.getenv" in text or "os.environ" in text or "dcoir_token" in text) and (
            "callback" in text or "authorization" in text or "requests." in text
        ):
            kinds.add(v5.PYTHON_ENV_TOKEN)
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in text or re.search(r"\biex\b", text, re.I):
            kinds.add(PS_DYNAMIC_EXEC)
        if "start-process" in text:
            kinds.add(v4.PS_PROCESS_LAUNCH)
        if "set-acl" in text or "filesystemaccessrule" in text or "fullcontrol" in text or "everyone" in text:
            kinds.add(v4.PS_ACL)
        if ("$env:" in text or "dcoir_token" in text) and (
            "invoke-webrequest" in text or "invoke-restmethod" in text or "authorization" in text or "callback" in text
        ):
            kinds.add(v5.PS_ENV_TOKEN)
    if suffix in {".yml", ".yaml"}:
        shell_context = (
            "shell" in text
            or "command" in text
            or "bash" in text
            or re.search(r"\bsh(?:\s+-c)?\b", text) is not None
        )
        if ("metadata" in text or "pr title" in text or "pull request title" in text or "github.event.pull_request" in text) and shell_context:
            kinds.add(v4.YAML_METADATA_SHELL)
        if "github.event.pull_request.head" in text or "github.head_ref" in text or (
            "untrusted" in text and "checkout" in text
        ):
            kinds.add(v4.YAML_UNTRUSTED_CHECKOUT)
        if ("curl" in text or "wget" in text) and ("bash" in text or " sh" in text or "pipe" in text):
            kinds.add(v4.YAML_SHELL_PIPE)
        if "write-all" in text or ("permissions" in text and "write" in text) or "broad write" in text:
            kinds.add(v4.YAML_BROAD_WRITE)
        if "pull_request_target" in text:
            kinds.add(v4.YAML_PULL_REQUEST_TARGET)
    return kinds


def _semantic_kind(finding: dict[str, Any]) -> str:
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
        return _canonical_kind(str(explicit[2]))
    explicit_kind = str(finding.get("_risk_sentinel_kind", "") or "")
    if explicit_kind:
        return _canonical_kind(explicit_kind)
    claimed = _claimed_kinds(finding)
    for kind in [
        v4.YAML_METADATA_SHELL,
        v4.YAML_SHELL_PIPE,
        v4.YAML_UNTRUSTED_CHECKOUT,
        v4.YAML_BROAD_WRITE,
        v4.YAML_PULL_REQUEST_TARGET,
        v4.PS_PROCESS_LAUNCH,
        PS_DYNAMIC_EXEC,
        v4.PS_ACL,
        v5.PS_ENV_TOKEN,
        PYTHON_PICKLE_LOAD,
        v5.PYTHON_YAML_LOAD,
        v5.PYTHON_SHELL_EXEC,
        v5.PYTHON_ENV_TOKEN,
    ]:
        if kind in claimed:
            return kind
    anchored_kind = _line_kind(str(finding.get("path", "") or ""), str(finding.get("_anchored_line_text", "") or ""))
    return _canonical_kind(anchored_kind or v5._semantic_kind(finding))


def _postable_key(finding: dict[str, Any]) -> SentinelKey:
    path = str(finding.get("path", "") or "")
    line = _line_number(finding.get("line", 0))
    return path, line, _semantic_kind(finding) or str(finding.get("title", "") or "")
