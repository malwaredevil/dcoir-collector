#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v8 runtime patch layer."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v8 as v8
from dcoir_review.entrypoint import DcoirReviewEntrypoint


class Config(SimpleNamespace):
    max_inline_comments: int = 12
    redact_secret_literals: bool = True


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.debug: dict[str, object] = {}

    def required_risk_sentinels(self, sentinels):
        return list(sentinels)

    def write_debug_json_artifact_safely(self, _config, path, data):
        self.debug[path] = data


def sentinel(path: str, line: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label="", detail="")


WORKFLOW = ".github/workflows/dcoir-review-probe-20260627n.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe_20260627n/python_pickle_yaml_shell_callback.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe_20260627n/powershell_icacls_process_env.ps1"


def pr331_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(WORKFLOW, 3, "  pull_request_target:"),
        sentinel(WORKFLOW, 5, "  contents: write"),
        sentinel(WORKFLOW, 13, "          ref: ${{ github.event.pull_request.head.sha }}"),
        sentinel(WORKFLOW, 15, "        run: wget -qO- https://downloads.example.invalid/bootstrap.sh | sh"),
        sentinel(WORKFLOW, 17, '        run: bash -c "${{ github.event.pull_request.body }}"'),
        sentinel(POWERSHELL, 8, "icacls $OutputRoot /grant Everyone:F /T"),
        sentinel(POWERSHELL, 10, "Start-Process -FilePath $RequestedTool -ArgumentList $Arguments -Wait"),
        sentinel(POWERSHELL, 12, '$headers = @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        sentinel(PYTHON, 10, "    return yaml.load(raw_text, Loader=yaml.Loader)"),
        sentinel(PYTHON, 18, "    return subprocess.run(command, shell=True, check=False)"),
        sentinel(PYTHON, 23, '    headers = {"Authorization": f"Bearer {token}"}'),
    ]


def pr331_findings() -> list[dict[str, object]]:
    return [
        {"path": WORKFLOW, "line": 3, "title": "Privileged pull_request_target workflow context", "body": "pull_request_target runs with base-repository privileges", "severity": "critical", "confidence": 0.99},
        {"path": WORKFLOW, "line": 5, "title": "GitHub Actions workflow grants write permissions", "body": "contents: write grants broad write token permissions", "severity": "critical", "confidence": 0.99},
        {"path": WORKFLOW, "line": 13, "title": "Privileged workflow checks out untrusted PR code", "body": "checkout uses github.event.pull_request.head.sha", "severity": "critical", "confidence": 0.99},
        {"path": WORKFLOW, "line": 15, "title": "Workflow pipes a network installer into a shell", "body": "wget output is piped into sh", "severity": "critical", "confidence": 0.99},
        {"path": WORKFLOW, "line": 17, "title": "Workflow executes pull request metadata in a shell", "body": "github.event.pull_request.body is passed to bash -c", "severity": "critical", "confidence": 0.99},
        {"path": POWERSHELL, "line": 8, "title": "PowerShell broad ACL grant exposes collector output", "body": "icacls grants Everyone:F", "severity": "critical", "confidence": 0.99},
        {"path": POWERSHELL, "line": 10, "title": "PowerShell caller-controlled process launch", "body": "Start-Process launches RequestedTool", "severity": "critical", "confidence": 0.99},
        {"path": POWERSHELL, "line": 12, "title": "Environment token forwarded to request-controlled callback", "body": "DCOIR_TOKEN sent in Authorization header to callback", "severity": "critical", "confidence": 0.99},
        {"path": PYTHON, "line": 10, "title": "Unsafe YAML deserialization with yaml.Loader", "body": "yaml.load with yaml.Loader", "severity": "critical", "confidence": 0.99},
        {"path": PYTHON, "line": 18, "title": "Python shell execution with caller-controlled command", "body": "subprocess.run uses shell=True", "severity": "critical", "confidence": 0.99},
        {"path": PYTHON, "line": 23, "title": "Environment token forwarded to request-controlled callback", "body": "environment token sent as Bearer header to callback", "severity": "critical", "confidence": 0.99},
        {"path": WORKFLOW, "line": 13, "title": "Privileged pull_request_target workflow context", "body": "pull_request_target runs with base-repository privileges", "severity": "critical", "confidence": 0.99},
        {"path": PYTHON, "line": 14, "title": "Unsafe pickle deserialization enables arbitrary code execution", "body": "pickle.loads deserializes untrusted bytes", "severity": "high", "confidence": 0.97},
        {"path": ".github/chatgpt_staging/dcoir_review_probe_20260627n/optional_dom_pressure.tsx", "line": 2, "title": "Unsanitized dangerouslySetInnerHTML exposes XSS risk", "body": "optional pressure finding", "severity": "critical", "confidence": 0.97},
    ]


def test_pr331_duplicate_wrong_kind_is_dropped_and_pickle_fills_spare_slot() -> None:
    hardened = FakeHardened()
    result = v8._select_required_postable_v8(hardened, None, None, None, pr331_findings(), pr331_sentinels(), Config())
    keys = [v8.v7._postable_key(finding) for finding in result]
    assert len(result) == 12
    assert (WORKFLOW, 13, "yaml_untrusted_checkout") in keys
    assert (WORKFLOW, 13, "yaml_pull_request_target") not in keys
    assert (PYTHON, 14, "python_pickle_load") in keys or any(key[0] == PYTHON and key[1] == 14 for key in keys)
    metadata = hardened.debug["metadata/required-v8-final-selection.json"]
    assert any("semantic_mismatch" in item for item in metadata["dropped_final_findings"])
    assert any(item.startswith(f"{PYTHON}:14") for item in metadata["spare_budget_selected"])


def test_validation_templates_are_semantic() -> None:
    yaml_validation = v8._validation_for_kind(v8.v4.YAML_BROAD_WRITE, WORKFLOW)
    assert "write-all" in yaml_validation
    assert "python3 - <<'PY'" in yaml_validation
    ps_validation = v8._validation_for_kind(v8.v4.PS_PROCESS_LAUNCH, POWERSHELL)
    assert "caller-controlled Start-Process remains" in ps_validation
    py_validation = v8._validation_for_kind(v8.v5.PYTHON_SHELL_EXEC, PYTHON)
    assert "shell=True" in py_validation



def test_v8_captures_its_own_preselection_hooks() -> None:
    original_rank = lambda findings, _config: list(findings)
    original_covers = lambda _finding, _sentinel: False
    original_fallback = lambda _sentinel, _config: {}
    module = SimpleNamespace(rank_findings_for_required_budget=original_rank)
    hardened = FakeHardened()
    hardened.finding_covers_risk_sentinel = original_covers
    hardened.risk_sentinel_fallback_finding = original_fallback

    v8._patch_required_selection(module, hardened)

    assert module._dcoir_required_v8_original_rank_findings_for_required_budget is original_rank
    assert hardened._dcoir_required_v8_original_finding_covers_risk_sentinel is original_covers
    assert hardened._dcoir_required_v8_original_risk_sentinel_fallback_finding is original_fallback
    assert callable(hardened.add_risk_sentinel_fallback_findings)
    assert callable(hardened.enforce_risk_sentinel_findings)
    assert not hasattr(module, "_dcoir_required_v7_original_rank_findings_for_required_budget")



def test_v8_is_helper_only_beneath_v9() -> None:
    patch_modules = DcoirReviewEntrypoint().patch_module_names
    assert "dcoir_review_required_runtime_patch_v8" not in patch_modules
    assert "dcoir_review_required_runtime_patch_v9" in patch_modules
    assert callable(v8._select_required_postable_v8)
    assert callable(v8._validation_for_kind)


def main() -> None:
    test_pr331_duplicate_wrong_kind_is_dropped_and_pickle_fills_spare_slot()
    test_validation_templates_are_semantic()
    test_v8_captures_its_own_preselection_hooks()
    test_v8_is_helper_only_beneath_v9()
    print("dcoir_review_required_runtime_patch_v8_selftest passed")


if __name__ == "__main__":
    main()
