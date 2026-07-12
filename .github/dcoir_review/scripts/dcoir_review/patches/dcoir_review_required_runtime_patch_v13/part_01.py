"""Thirteenth required-coverage layer for DCOIR Review.

Connector-safe overlay for the #338 live-test failures. This layer keeps v12's
selection machinery, then tightens semantic identity, final inline rendering,
overflow reporting, validation text, and workflow/Kubernetes domain boundaries.
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

SentinelKey = tuple[str, int, str]
VERSION = "v13"

PS_PLAINTEXT_SECURE_STRING = "ps_plaintext_secure_string"
PS_RUN_KEY_PERSISTENCE = "ps_run_key_persistence"
TS_INNER_HTML = "ts_inner_html"
TS_DYNAMIC_EXECUTION = "ts_dynamic_execution"
K8S_HOST_PID = "k8s_host_pid"
K8S_HOST_NETWORK = getattr(v11, "K8S_HOST_NETWORK", "k8s_host_network")
K8S_PRIVILEGED_CONTAINER = getattr(v11, "K8S_PRIVILEGED_CONTAINER", "k8s_privileged_container")
K8S_PRIVILEGE_ESCALATION = getattr(v11, "K8S_PRIVILEGE_ESCALATION", "k8s_privilege_escalation")
K8S_HOST_PATH = getattr(v11, "K8S_HOST_PATH", "k8s_host_path")

REQUIRED_KINDS = set(getattr(v12, "REQUIRED_KINDS", set()))
TRACKED_HIGH_RISK_KINDS = REQUIRED_KINDS | {
    PS_PLAINTEXT_SECURE_STRING,
    PS_RUN_KEY_PERSISTENCE,
    TS_INNER_HTML,
    TS_DYNAMIC_EXECUTION,
    K8S_HOST_PID,
    K8S_HOST_NETWORK,
    K8S_PRIVILEGED_CONTAINER,
    K8S_PRIVILEGE_ESCALATION,
    K8S_HOST_PATH,
}


def _preserve(module: Any, name: str) -> Any:
    storage = f"_dcoir_required_v13_original_{name.lstrip('_')}"
    existing = getattr(module, storage, None)
    if callable(existing):
        return existing
    helper = getattr(module, name)
    setattr(module, storage, helper)
    return helper


_ORIGINAL_V12_SELECT_ONCE = _preserve(v12, "_select_once")
_ORIGINAL_V12_POSTABLE_KEY = _preserve(v12, "_postable_key")
_ORIGINAL_V12_SENTINEL_KEY = _preserve(v12, "_sentinel_key")
_ORIGINAL_V12_FALLBACK_FOR_SENTINEL = _preserve(v12, "_fallback_for_sentinel")
_ORIGINAL_V12_VALIDATION_FOR_KEY = _preserve(v12, "_validation_for_key")
_ORIGINAL_V12_CANONICAL_KIND = _preserve(v12, "_canonical_kind")
_ORIGINAL_V11_LINE_KIND = _preserve(v11, "_line_kind")


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _is_workflow_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith(".github/workflows/") and normalized.endswith((".yml", ".yaml"))


def _is_probable_k8s(path: str, text: str = "") -> bool:
    if _is_workflow_path(path):
        return False
    normalized_path = path.replace("\\", "/").lower()
    basename = normalized_path.rsplit("/", 1)[-1]
    if any(token in normalized_path or token in basename for token in ("/k8s/", "/kubernetes/", "_k8s", "k8s", "kubernetes", "deployment", "manifest", "pod")):
        return True
    normalized_text = _normalize(text)
    return any(token in normalized_text for token in ("apiversion:", "kind: pod", "kind: deployment", "securitycontext:", "hostpid:", "hostnetwork:", "privileged: true", "hostpath:"))


def _domain_filtered_kind(path: str, kind: str, text: str = "") -> str:
    value = str(kind or "")
    if not value:
        return ""
    if _is_workflow_path(path) and value.startswith("k8s_"):
        return ""
    if _is_probable_k8s(path, text) and value.startswith("yaml_"):
        return ""
    return value


def _workflow_line_kind(path: str, text: str) -> str:
    if not _is_workflow_path(path):
        return ""
    lower = _normalize(text)
    if "github_token" in lower and "github.event.pull_request.body" in lower:
        return v10.YAML_TOKEN_TO_PR_URL
    if "pull_request_target" in lower:
        return v4.YAML_PULL_REQUEST_TARGET
    if "write-all" in lower or re.search(r"\b[a-z_-]+\s*:\s*write\b", lower):
        return v4.YAML_BROAD_WRITE
    if "pull_request.head" in lower or "head.sha" in lower or "github.head_ref" in lower:
        return v4.YAML_UNTRUSTED_CHECKOUT
    if ("curl" in lower or "wget" in lower) and ("| sh" in lower or "| bash" in lower):
        return v4.YAML_SHELL_PIPE
    if "github.event.pull_request" in lower and any(token in lower for token in ("sh -c", "bash -lc", "shell:", "run:")):
        return v4.YAML_METADATA_SHELL
    return ""


def _python_line_kind(path: str, text: str) -> str:
    if Path(path.lower()).suffix != ".py":
        return ""
    lower = _normalize(text)
    if "pickle.load" in lower or "pickle.loads" in lower:
        return v9.PYTHON_PICKLE_LOAD
    if "yaml.load" in lower:
        return v5.PYTHON_YAML_LOAD
    if "shell=true" in lower or "os.system(" in lower or "os.popen(" in lower:
        return v5.PYTHON_SHELL_EXEC
    if "requests." in lower and "callback" in lower and ("authorization" in lower or "bearer" in lower or "dcoir_token" in lower):
        return v5.PYTHON_ENV_TOKEN
    if "extractall" in lower:
        return v11.PYTHON_ARCHIVE_EXTRACT
    if (".open(" in lower or "open(" in lower) and any(token in lower for token in ("write", "wb", "w+b", "w\"")):
        return v11.PYTHON_PATH_WRITE
    return ""


def _powershell_line_kind(path: str, text: str) -> str:
    if Path(path.lower()).suffix != ".ps1":
        return ""
    lower = _normalize(text)
    if "invoke-expression" in lower or "iex " in lower:
        return v9.PS_DYNAMIC_EXEC
    if "convertto-securestring" in lower and "-asplaintext" in lower:
        return PS_PLAINTEXT_SECURE_STRING
    if "filesystemaccessrule" in lower or "set-acl" in lower:
        return v4.PS_ACL
    if "start-process" in lower:
        return v4.PS_PROCESS_LAUNCH
    if ("invoke-webrequest" in lower or "invoke-restmethod" in lower) and ("authorization" in lower or "bearer" in lower):
        return v5.PS_ENV_TOKEN
    if "\\currentversion\\run" in lower or "currentversion\\run" in lower:
        return PS_RUN_KEY_PERSISTENCE
    return ""


def _k8s_line_kind(path: str, text: str) -> str:
    if not _is_probable_k8s(path, text):
        return ""
    lower = _normalize(text)
    if "hostpid:" in lower:
        return K8S_HOST_PID
    if "hostnetwork:" in lower:
        return K8S_HOST_NETWORK
    if "privileged: true" in lower:
        return K8S_PRIVILEGED_CONTAINER
    if "allowprivilegeescalation:" in lower:
        return K8S_PRIVILEGE_ESCALATION
    if "hostpath:" in lower:
        return K8S_HOST_PATH
    return ""


def _typescript_line_kind(path: str, text: str) -> str:
    if Path(path.lower()).suffix not in {".ts", ".tsx", ".js", ".jsx"}:
        return ""
    lower = _normalize(text)
    if ".innerhtml" in lower or ".outerhtml" in lower or "insertadjacenthtml" in lower:
        return TS_INNER_HTML
    if "settimeout(" in lower or "setinterval(" in lower or "new function(" in lower:
        return TS_DYNAMIC_EXECUTION
    return ""


def _line_kind(path: str, text: str) -> str:
    for classifier in (_workflow_line_kind, _python_line_kind, _powershell_line_kind, _k8s_line_kind, _typescript_line_kind):
        kind = classifier(path, text)
        if kind:
            return _domain_filtered_kind(path, kind, text)
    return _domain_filtered_kind(path, _ORIGINAL_V11_LINE_KIND(path, text), text)


def _canonical_kind(kind: str, text: str = "", detail: str = "", path: str = "") -> str:
    value = _ORIGINAL_V12_CANONICAL_KIND(kind, text, detail)
    context = _normalize(f"{text}\n{detail}")
    if value == getattr(v4, "PYTHON_SSRF", "python_ssrf"):
        has_token = "dcoir_token" in context or "os.environ" in context or "os.getenv" in context
        has_auth = "authorization" in context and ("bearer" in context or "token" in context)
        if ("callback" in context or "requests." in context) and (has_token or has_auth):
            value = v5.PYTHON_ENV_TOKEN
    return _domain_filtered_kind(path, value, context) if path else value


def _trusted_key_from_finding(finding: dict[str, Any]) -> SentinelKey | None:
    raw = finding.get("_risk_sentinel_key")
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        return None
    path = str(raw[0] or "")
    line = core._line_number(raw[1])
    kind = str(raw[2] or "")
    anchored_text = str(finding.get("_anchored_line_text", "") or "")
    if not path or not line or not kind or not anchored_text:
        return None
    if _line_kind(path, anchored_text) != kind:
        return None
    filtered = _domain_filtered_kind(path, kind, anchored_text)
    return (path, line, filtered) if filtered else None


def _sentinel_key(sentinel: Any) -> SentinelKey:
    path, line, base_kind = _ORIGINAL_V12_SENTINEL_KEY(sentinel)
    text = str(getattr(sentinel, "text", "") or "")
    detail = "\n".join(str(getattr(sentinel, name, "") or "") for name in ("label", "detail"))
    kind = _line_kind(path, text) or _canonical_kind(base_kind, text, detail, path)
    return path, line, _domain_filtered_kind(path, kind, text)


def _postable_key(finding: dict[str, Any]) -> SentinelKey:
    trusted = _trusted_key_from_finding(finding)
    if trusted:
        return trusted
    path, line, base_kind = _ORIGINAL_V12_POSTABLE_KEY(finding)
    text = "\n".join(str(finding.get(name, "") or "") for name in ("_anchored_line_text", "title", "body", "description"))
    kind = _line_kind(path, text) or _canonical_kind(base_kind, text, text, path)
    return path, line, _domain_filtered_kind(path, kind, text)


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind == v4.YAML_BROAD_WRITE:
        return path, 0, kind
    if kind == v11.PYTHON_ARCHIVE_EXTRACT:
        return path, 0, kind
    return path, line, kind


def _kind_rank(kind: str) -> int:
    order = {
        v10.YAML_TOKEN_TO_PR_URL: 0,
        v4.YAML_METADATA_SHELL: 1,
        v4.YAML_SHELL_PIPE: 3,
        v4.YAML_UNTRUSTED_CHECKOUT: 4,
        v4.YAML_PULL_REQUEST_TARGET: 5,
        v4.YAML_BROAD_WRITE: 6,
        v9.PS_DYNAMIC_EXEC: 10,
        v4.PS_ACL: 11,
        v4.PS_PROCESS_LAUNCH: 12,
        v5.PS_ENV_TOKEN: 13,
        PS_PLAINTEXT_SECURE_STRING: 14,
        PS_RUN_KEY_PERSISTENCE: 15,
        v9.PYTHON_PICKLE_LOAD: 20,
        v5.PYTHON_YAML_LOAD: 21,
        v5.PYTHON_SHELL_EXEC: 22,
        v5.PYTHON_ENV_TOKEN: 23,
        v11.PYTHON_ARCHIVE_EXTRACT: 24,
        v11.PYTHON_PATH_WRITE: 25,
        K8S_HOST_PID: 40,
        K8S_HOST_NETWORK: 41,
        K8S_PRIVILEGED_CONTAINER: 42,
        K8S_PRIVILEGE_ESCALATION: 43,
        K8S_HOST_PATH: 44,
        TS_INNER_HTML: 50,
        TS_DYNAMIC_EXECUTION: 51,
    }
    return order.get(str(kind or ""), 99)


def _text_kinds(path: str, text: str) -> set[str]:
    result: set[str] = set()
    for line in str(text or "").splitlines() or [str(text or "")]:
        kind = _line_kind(path, line)
        if kind:
            result.add(kind)
    return result


def _semantic_mismatch(finding: dict[str, Any], expected: dict[tuple[str, int], set[str]]) -> bool:
    path, line, kind = _postable_key(finding)
    allowed = expected.get((path, line), set())
    if allowed and kind not in allowed:
        return True
    rendered_kinds = _text_kinds(path, "\n".join(str(finding.get(name, "") or "") for name in ("title", "body")))
    contradictory = {candidate for candidate in rendered_kinds if candidate != kind and candidate in TRACKED_HIGH_RISK_KINDS}
    return bool(contradictory)


def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    quoted_path = repr(path)
    if kind.startswith("python_"):
        return f"python3 -m py_compile {path}"
    if kind.startswith("ps_"):
        ps_path = path.replace("'", "''")
        script = "$errors=$null; " + f"[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath '{ps_path}'), [ref]$errors) | Out-Null; " + "if ($errors) { throw ($errors | Out-String) }"
        return "pwsh -NoProfile -Command " + shlex.quote(script)
    if kind == v10.YAML_TOKEN_TO_PR_URL:
        return "python3 -c " + shlex.quote(f"from pathlib import Path; text=Path({quoted_path}).read_text(); assert not ('GITHUB_TOKEN' in text and 'github.event.pull_request.body' in text)")
    if kind == v4.YAML_METADATA_SHELL:
        return "python3 -c " + shlex.quote(f"from pathlib import Path; text=Path({quoted_path}).read_text(); assert 'github.event.pull_request.labels' not in text and 'github.event.pull_request.body' not in text")
    if kind == v4.YAML_SHELL_PIPE:
        return "python3 -c " + shlex.quote(f"from pathlib import Path; text=Path({quoted_path}).read_text(); assert '| sh' not in text and '| bash' not in text")
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        return "python3 -c " + shlex.quote(f"from pathlib import Path; text=Path({quoted_path}).read_text(); assert 'github.event.pull_request.head' not in text and 'github.head_ref' not in text")
    if kind == v4.YAML_BROAD_WRITE:
        return "python3 -c " + shlex.quote(f"from pathlib import Path; text=Path({quoted_path}).read_text(); assert 'write-all' not in text and ': write' not in text")
    if kind == v4.YAML_PULL_REQUEST_TARGET:
        return "python3 -c " + shlex.quote(f"from pathlib import Path; text=Path({quoted_path}).read_text(); assert 'pull_request_target' not in text")
    if kind.startswith(("yaml_", "k8s_")):
        return "python3 -c " + shlex.quote(f"from pathlib import Path; Path({quoted_path}).read_text()")
    return _ORIGINAL_V12_VALIDATION_FOR_KEY(kind, path, line)
