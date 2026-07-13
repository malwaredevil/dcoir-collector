#!/usr/bin/env python3
"""Regression test for v12 helper recursion after runtime monkey-patching."""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any


WORKFLOW = ".github/workflows/dcoir-review-v12-recursion-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v12_recursion_probe.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v12_recursion_probe.ps1"
K8S = ".github/chatgpt_staging/dcoir_review_probe/v12_optional_k8s.yml"


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def install_stubs() -> None:
    v4 = types.ModuleType("dcoir_review_required_runtime_patch_v4")
    v4.YAML_PULL_REQUEST_TARGET = "yaml_pull_request_target"
    v4.YAML_BROAD_WRITE = "yaml_broad_write"
    v4.YAML_UNTRUSTED_CHECKOUT = "yaml_untrusted_checkout"
    v4.YAML_SHELL_PIPE = "yaml_shell_pipe"
    v4.YAML_METADATA_SHELL = "yaml_metadata_shell"
    v4.PS_ACL = "ps_acl"
    v4.PS_PROCESS_LAUNCH = "ps_process_launch"
    sys.modules[v4.__name__] = v4

    v5 = types.ModuleType("dcoir_review_required_runtime_patch_v5")
    v5.PYTHON_YAML_LOAD = "python_yaml_load"
    v5.PYTHON_SHELL_EXEC = "python_shell_exec"
    v5.PYTHON_ENV_TOKEN = "python_env_token_callback"
    v5.PS_ENV_TOKEN = "ps_env_token_callback"
    v5._normalize = normalize
    v5._normalize_comment_finding = lambda finding: dict(finding)
    sys.modules[v5.__name__] = v5

    core = types.ModuleType("dcoir_review_required_runtime_patch_v9_core")
    core.SELECTION_SUMMARY = {}
    core._line_number = lambda value: int(value or 0)
    core._severity_rank = lambda finding: {"critical": 0, "high": 1, "medium": 2}.get(
        str(finding.get("severity", "")).lower(), 3
    )
    core._confidence = lambda finding: float(finding.get("confidence", 0) or 0)
    sys.modules[core.__name__] = core

    v9 = types.ModuleType("dcoir_review_required_runtime_patch_v9")
    v9.PYTHON_PICKLE_LOAD = "python_pickle_load"
    v9.PS_DYNAMIC_EXEC = "ps_dynamic_exec"
    v9._ensure_prompt_review = lambda _config: None
    sys.modules[v9.__name__] = v9

    selection = types.ModuleType("dcoir_review_required_runtime_patch_v9_selection")
    selection._iter_added_diff_lines = lambda _diff: []
    sys.modules[selection.__name__] = selection

    v10 = types.ModuleType("dcoir_review_required_runtime_patch_v10")
    v10.YAML_TOKEN_TO_PR_URL = "yaml_token_to_pr_body_url"
    v10._validation_for_token_to_pr_url = lambda path: f"validate token url {path}"
    v10._scrub_shell_pipe_wording = lambda _finding: None
    sys.modules[v10.__name__] = v10

    v11 = types.ModuleType("dcoir_review_required_runtime_patch_v11")
    v11.PYTHON_ARCHIVE_EXTRACT = "python_archive_extract"
    v11.PYTHON_PATH_WRITE = "python_path_write"
    v11.K8S_HOST_NETWORK = "k8s_host_network"
    v11.K8S_PRIVILEGED_CONTAINER = "k8s_privileged_container"
    v11.K8S_PRIVILEGE_ESCALATION = "k8s_privilege_escalation"
    v11.K8S_HOST_PATH = "k8s_host_path"
    v11._normalize = normalize
    v11._canonical_kind = lambda kind: kind
    v11._base_required_sentinels = lambda _hardened, risk_sentinels: list(risk_sentinels)
    v11._base_sentinel_key = lambda sentinel: (
        str(getattr(sentinel, "path", "") or ""),
        int(getattr(sentinel, "line", 0) or 0),
        "",
    )
    v11._text_kinds = lambda path, text: {line_kind(path, text)} - {""}
    v11._explicit_kind = lambda finding: (
        str(finding.get("_risk_sentinel_key", ["", 0, ""])[2])
        if isinstance(finding.get("_risk_sentinel_key"), (list, tuple))
        else str(finding.get("_risk_sentinel_kind", "") or "")
    )
    v11._title_kinds = lambda _finding: set()
    v11._line_kind = line_kind
    v11._postable_key = postable_key
    v11._fallback_for_sentinel = fallback_for_sentinel
    v11._validation_for_key = lambda kind, path, line=0: f"validate {kind} {path}:{line}"
    v11._patch_progress_comment = lambda *_args, **_kwargs: None
    sys.modules[v11.__name__] = v11


def line_kind(path: str, text: str) -> str:
    lower = normalize(text)
    suffix = Path(path.lower()).suffix
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in lower:
            return "yaml_pull_request_target"
        if "pull_request.head" in lower:
            return "yaml_untrusted_checkout"
        if "wget" in lower and "| sh" in lower:
            return "yaml_shell_pipe"
        if "hostnetwork" in lower:
            return "k8s_host_network"
    if suffix == ".py":
        if "pickle.load" in lower:
            return "python_pickle_load"
        if "extractall" in lower:
            return "python_archive_extract"
        if ".open(" in lower and "write" in lower:
            return "python_path_write"
    if suffix == ".ps1":
        if "start-process" in lower:
            return "ps_process_launch"
        if "filesystemaccessrule" in lower:
            return "ps_acl"
    return ""


def postable_key(finding: dict[str, Any]) -> tuple[str, int, str]:
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
        return str(explicit[0]), int(explicit[1]), str(explicit[2])
    path = str(finding.get("path", "") or "")
    return path, int(finding.get("line", 0) or 0), line_kind(path, str(finding.get("_anchored_line_text", "") or ""))


def fallback_for_sentinel(_hardened: Any, sentinel: Any, _config: Any) -> dict[str, Any]:
    return {
        "title": str(getattr(sentinel, "label", "") or "required fallback"),
        "severity": "high",
        "confidence": 0.99,
        "path": str(getattr(sentinel, "path", "") or ""),
        "line": int(getattr(sentinel, "line", 0) or 0),
        "body": str(getattr(sentinel, "detail", "") or "fallback"),
        "_anchored_line_text": str(getattr(sentinel, "text", "") or ""),
    }


def load_v12():
    install_stubs()
    path = Path(__file__).with_name("dcoir_review_required_runtime_patch_v12.py")
    spec = importlib.util.spec_from_file_location("dcoir_review_required_runtime_patch_v12", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.artifacts: dict[str, Any] = {}

    def write_debug_json_artifact_safely(self, _config: Any, path: str, data: Any) -> None:
        self.artifacts[path] = data


class Config(SimpleNamespace):
    max_inline_comments: int = 6
    debug: bool = True


def sentinel(path: str, line: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label="", detail="")


def risk_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 12, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 14, "        run: wget -qO- https://downloads.example.invalid/install.sh | sh"),
        sentinel(PYTHON, 9, "    return pickle.load(raw)"),
        sentinel(PYTHON, 18, "    archive.extractall(destination)"),
        sentinel(PYTHON, 22, '    Path(user_path).open(mode="wb").write(payload)'),
        sentinel(POWERSHELL, 11, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "Modify", "Allow")'),
        sentinel(POWERSHELL, 14, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        sentinel(K8S, 6, "  hostNetwork: true"),
    ]


def findings() -> list[dict[str, Any]]:
    return [
        {
            "path": WORKFLOW,
            "line": 3,
            "title": "pull_request_target",
            "_anchored_line_text": "  pull_request_target:",
            "_risk_sentinel_key": [WORKFLOW, 3, "yaml_pull_request_target"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": PYTHON,
            "line": 9,
            "title": "pickle load",
            "_anchored_line_text": "    return pickle.load(raw)",
            "_risk_sentinel_key": [PYTHON, 9, "python_pickle_load"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": POWERSHELL,
            "line": 14,
            "title": "Start-Process launch",
            "_anchored_line_text": "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait",
            "_risk_sentinel_key": [POWERSHELL, 14, "ps_process_launch"],
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": K8S,
            "line": 6,
            "title": "optional hostNetwork",
            "_anchored_line_text": "  hostNetwork: true",
            "_risk_sentinel_key": [K8S, 6, "k8s_host_network"],
            "severity": "high",
            "confidence": 0.8,
        },
    ]


def main() -> None:
    v12 = load_v12()
    hardened = FakeHardened()
    module = SimpleNamespace(base=None, hardened=hardened)
    config = Config()

    v12.apply_pareto_context_module(module)
    v12.apply_pareto_context_module(module)

    first_key = v12._postable_key(findings()[0])
    assert first_key == (WORKFLOW, 3, "yaml_pull_request_target")
    assert v12._spare_priority(findings()[0])[0] == 0

    ranked = module.rank_findings_for_required_budget(findings(), config)
    assert ranked
    assert all(v12._postable_key(item)[2] for item in ranked if item["path"] != K8S)

    selected = v12._select_required_postable(hardened, findings(), risk_sentinels(), config)
    metadata = sys.modules["dcoir_review_required_runtime_patch_v9_core"].SELECTION_SUMMARY
    assert selected
    assert metadata["final_invalid_selected_keys"] == []
    assert metadata["final_postable_count"] == config.max_inline_comments

    print("dcoir_review_required_runtime_patch_v12_recursion_selftest passed")


if __name__ == "__main__":
    main()
