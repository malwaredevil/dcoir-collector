#!/usr/bin/env python3
"""Regression self-test for DCOIR Review v9 runtime patch."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v9 as v9


WORKFLOW = ".github/workflows/dcoir-review-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/python_pickle_yaml_shell_callback.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/powershell_acl_process_env.ps1"


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    redact_secret_literals: bool = True
    debug: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def required_risk_sentinels(self, sentinels):
        return list(sentinels)

    def write_debug_json_artifact_safely(self, _config, path, data):
        self.debug[path] = data


class FakeHardenedRequiredSubset(FakeHardened):
    def __init__(self, required):
        super().__init__()
        self.required = list(required)

    def required_risk_sentinels(self, _sentinels):
        return list(self.required)


class FakeDetectorOwner:
    RiskSentinel = SimpleNamespace

    def __init__(self) -> None:
        self.calls = 0

    def detect_risk_sentinels(self, _diff):
        self.calls += 1
        return []


def sentinel(path: str, line: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label="", detail="")


def pr332_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 5, "  pull-requests: write"),
        sentinel(WORKFLOW, 13, "          ref: ${{ github.head_ref }}"),
        sentinel(WORKFLOW, 15, "        run: curl -fsSL https://downloads.example.invalid/agent.sh | bash"),
        sentinel(WORKFLOW, 17, '        run: sh -c "${{ github.event.pull_request.title }}"'),
        sentinel(POWERSHELL, 8, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")'),
        sentinel(POWERSHELL, 12, 'Start-Process -FilePath $ToolName -ArgumentList "/quiet" -Wait'),
        sentinel(POWERSHELL, 15, 'Invoke-RestMethod -Uri $CallbackUri -Headers @{ Authorization = "Bearer $token" } -Method Post'),
        sentinel(PYTHON, 10, "    return yaml.load(text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 14, "    return pickle.loads(raw_state)"),
        sentinel(PYTHON, 18, "    return subprocess.Popen(command_text, shell=True)"),
        sentinel(PYTHON, 23, '    headers = {"Authorization": f"Bearer {api_token}"}'),
    ]


def pr332_findings() -> list[dict[str, object]]:
    return [
        {"path": WORKFLOW, "line": 3, "title": "Privileged pull_request_target workflow context", "body": "pull_request_target runs with base-repository privileges", "severity": "critical", "confidence": 0.99, "_anchored_line_text": "  pull_request_target:"},
        {"path": WORKFLOW, "line": 5, "title": "GitHub Actions workflow grants write permissions", "body": "pull-requests: write grants broad write token permissions", "severity": "critical", "confidence": 0.99, "_anchored_line_text": "  pull-requests: write"},
        {"path": WORKFLOW, "line": 13, "title": "Privileged workflow checks out untrusted PR code", "body": "checkout uses github.head_ref", "severity": "critical", "confidence": 0.99, "_anchored_line_text": "          ref: ${{ github.head_ref }}"},
        {"path": WORKFLOW, "line": 15, "title": "Workflow pipes a network installer into a shell", "body": "curl output is piped into bash", "severity": "critical", "confidence": 0.99, "_anchored_line_text": "        run: curl -fsSL https://downloads.example.invalid/agent.sh | bash"},
        {"path": WORKFLOW, "line": 17, "title": "Workflow executes pull request metadata in a shell", "body": "github.event.pull_request.title is passed to sh -c", "severity": "critical", "confidence": 0.99, "_anchored_line_text": '        run: sh -c "${{ github.event.pull_request.title }}"'},
        {"path": POWERSHELL, "line": 8, "title": "PowerShell broad ACL grant exposes collector output", "body": "Everyone FullControl ACL grant", "severity": "critical", "confidence": 0.99},
        {"path": POWERSHELL, "line": 12, "title": "PowerShell caller-controlled process launch", "body": "Start-Process launches ToolName", "severity": "critical", "confidence": 0.99},
        {"path": POWERSHELL, "line": 15, "title": "Environment token forwarded to request-controlled callback", "body": "DCOIR_TOKEN sent in Authorization header to callback", "severity": "critical", "confidence": 0.99},
        {"path": PYTHON, "line": 10, "title": "Unsafe YAML deserialization with yaml.Loader", "body": "yaml.load with yaml.Loader", "severity": "critical", "confidence": 0.99, "_anchored_line_text": "    return yaml.load(text, Loader=yaml.Loader)"},
        {"path": PYTHON, "line": 14, "title": "Unsafe pickle.loads enables code execution", "body": "pickle.loads deserializes untrusted bytes", "severity": "critical", "confidence": 0.99, "_anchored_line_text": "    return pickle.loads(raw_state)"},
        {"path": PYTHON, "line": 18, "title": "Python shell execution with caller-controlled command", "body": "subprocess.Popen uses shell=True", "severity": "critical", "confidence": 0.99},
        {"path": PYTHON, "line": 23, "title": "Environment token forwarded to request-controlled callback", "body": "environment token sent as Bearer header to callback", "severity": "critical", "confidence": 0.99},
        {"path": WORKFLOW, "line": 17, "title": "Privileged pull_request_target workflow context", "body": "pull_request_target runs with base-repository privileges", "severity": "critical", "confidence": 0.99, "_anchored_line_text": '        run: sh -c "${{ github.event.pull_request.title }}"'},
    ]


def test_pr332_wrong_duplicate_is_dropped() -> None:
    hardened = FakeHardened()
    result = v9._select_required_postable(hardened, pr332_findings(), pr332_sentinels(), Config())
    keys = [v9._postable_key(finding) for finding in result]
    assert len(result) == 12
    assert (WORKFLOW, 17, v9.v4.YAML_METADATA_SHELL) in keys
    assert (WORKFLOW, 17, v9.v4.YAML_PULL_REQUEST_TARGET) not in keys
    assert (PYTHON, 14, v9.PYTHON_PICKLE_LOAD) in keys
    metadata = hardened.debug["metadata/required-v9-final-selection.json"]
    assert metadata["final_invalid_selected_keys"] == []
    assert f"{PYTHON}:14 {v9.PYTHON_PICKLE_LOAD}" in metadata["selected_keys"]


def test_fake_anchor_text_does_not_authorize_untrusted_line() -> None:
    hardened = FakeHardened()
    fake = {
        "path": PYTHON,
        "line": 99,
        "title": "Unsafe pickle.loads enables code execution",
        "body": "pickle.loads deserializes untrusted bytes",
        "severity": "critical",
        "confidence": 1.0,
        "_anchored_line_text": "    return pickle.loads(raw_state)",
    }
    result = v9._select_required_postable(hardened, [*pr332_findings(), fake], pr332_sentinels(), Config())
    assert (PYTHON, 99, v9.PYTHON_PICKLE_LOAD) not in [v9._postable_key(finding) for finding in result]


def test_no_sentinels_preserves_ordinary_findings() -> None:
    hardened = FakeHardened()
    finding = {
        "path": PYTHON,
        "line": 44,
        "title": "Unsafe pickle.loads enables code execution",
        "body": "pickle.loads deserializes untrusted bytes",
        "severity": "high",
        "confidence": 0.9,
        "_anchored_line_text": "    return pickle.loads(raw_state)",
    }
    result = v9._select_required_postable(hardened, [finding], [], Config())
    assert len(result) == 1
    assert v9._postable_key(result[0]) == (PYTHON, 44, v9.PYTHON_PICKLE_LOAD)


def test_required_fallback_is_inserted_when_model_misses_sentinel() -> None:
    hardened = FakeHardened()
    findings = [finding for finding in pr332_findings() if not (finding["path"] == PYTHON and finding["line"] == 14)]
    result = v9._select_required_postable(hardened, findings, pr332_sentinels(), Config())
    keys = [v9._postable_key(finding) for finding in result]
    assert (PYTHON, 14, v9.PYTHON_PICKLE_LOAD) in keys
    fallback = [finding for finding in result if v9._postable_key(finding) == (PYTHON, 14, v9.PYTHON_PICKLE_LOAD)][0]
    assert fallback["_risk_sentinel_kind"] == v9.PYTHON_PICKLE_LOAD
