#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v16 coverage overlay."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16


def _s(path: str, line: int, kind: str, text: str) -> SimpleNamespace:
    title, body, _notes = v16._template_for_kind(kind)
    return SimpleNamespace(path=path, line=line, label=title, detail=body, text=text)


def test_python_path_write_sentinel_skips_test_files() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    test_path = "project_sources/collector/tools/test_build_powershell_surface_inventory_path_safety.py"
    diff = "\n".join(
        [
            "diff --git a/a.py b/b.py",
            f"+++ b/{test_path}",
            "@@ -180,0 +182,1 @@",
            '+    outside_file.write_text("ok", encoding="utf-8")',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found)


def test_python_path_write_sentinel_keeps_non_test_files() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    path = "project_sources/collector/tools/build_dcoir_collector_runtime_package.py"
    diff = "\n".join(
        [
            "diff --git a/a.py b/b.py",
            f"+++ b/{path}",
            "@@ -10,0 +11,1 @@",
            '+    Path(output_path).write_text("ok", encoding="utf-8")',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found)


def test_python_dynamic_exec_classifier_only_matches_execution_builtins() -> None:
    path = "tools/reviewer_probe.py"
    # These are the bounded false-positive cases covered by #434. Arbitrary
    # object methods named eval/exec remain context-dependent and are not
    # declared safe by this deterministic regression.
    false_positives = [
        'VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")',
        'code = compile(source, "<string>", "exec")',
    ]
    for line in false_positives:
        assert v16._line_kind(path, line) != v16.PYTHON_DYNAMIC_EXEC, line

    true_positives = [
        "result = eval(user_input)",
        "exec(payload)",
        "result = builtins.eval(user_input)",
        "__builtins__.exec(payload)",
    ]
    for line in true_positives:
        assert v16._line_kind(path, line) == v16.PYTHON_DYNAMIC_EXEC, line


def main() -> None:
    workflow = ".github/workflows/dcoir-review-v16-probe.yml"
    py = ".github/chatgpt_staging/dcoir_review_probe/v16_probe.py"
    ps = ".github/chatgpt_staging/dcoir_review_probe/v16_probe.ps1"
    ts = ".github/chatgpt_staging/dcoir_review_probe/v16_optional.ts"
    k8s = ".github/chatgpt_staging/dcoir_review_probe/v16_bonus_k8s.yml"

    risk_sentinels = [
        _s(workflow, 3, v4.YAML_PULL_REQUEST_TARGET, "  pull_request_target:"),
        _s(workflow, 5, v4.YAML_BROAD_WRITE, "  contents: write"),
        _s(workflow, 13, v4.YAML_UNTRUSTED_CHECKOUT, "          ref: ${{ github.event.pull_request.head.sha }}"),
        _s(workflow, 16, v4.YAML_METADATA_SHELL, '          bash -lc "${{ github.event.pull_request.body }}"'),
        _s(workflow, 19, v10.YAML_TOKEN_TO_PR_URL, '          curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.title }}"'),
        _s(workflow, 22, v4.YAML_SHELL_PIPE, "          curl -fsSL https://downloads.example.invalid/install.sh | sh"),
        _s(workflow, 25, v4.YAML_METADATA_SHELL, '          sh -c "${{ github.event.pull_request.labels[0].name }}"'),
        _s(py, 12, v9.PYTHON_PICKLE_LOAD, "    return pickle.loads(raw)"),
        _s(py, 16, v5.PYTHON_YAML_LOAD, "    return yaml.load(blob, Loader=yaml.Loader)"),
        _s(py, 20, v16.PYTHON_DYNAMIC_EXEC, "    return eval(rule_text)"),
        _s(py, 24, v5.PYTHON_SHELL_EXEC, "    return subprocess.run(command, shell=True, check=True)"),
        _s(py, 29, v11.PYTHON_ARCHIVE_EXTRACT, "        archive.extractall(destination)"),
        _s(py, 34, v5.PYTHON_ENV_TOKEN, '    return requests.get(callback_url, headers={"Authorization": f"Bearer {token}"})'),
        _s(py, 38, v11.PYTHON_PATH_WRITE, "    Path(target_name).write_text(content)"),
        _s(ps, 9, v13.PS_PLAINTEXT_SECURE_STRING, "$secret = ConvertTo-SecureString $Password -AsPlainText -Force"),
        _s(ps, 13, v4.PS_ACL, "Set-Acl -Path $OutputPath -AclObject $acl"),
        _s(ps, 14, v4.PS_PROCESS_LAUNCH, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        _s(ps, 15, v9.PS_DYNAMIC_EXEC, "Invoke-Expression $Command"),
        _s(ps, 16, v5.PS_ENV_TOKEN, 'Invoke-WebRequest -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        _s(ps, 17, v13.PS_RUN_KEY_PERSISTENCE, 'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name Probe -Value $ToolPath'),
        _s(ts, 4, v13.TS_INNER_HTML, "target.innerHTML = profile.html;"),
        _s(k8s, 7, v13.K8S_HOST_PATH, "hostPath:"),
    ]

    selected, metadata = v16._select_once(SimpleNamespace(), [], risk_sentinels, SimpleNamespace(max_inline_comments=12))
    assert len(selected) <= 12
    assert not metadata["omitted_required_sentinels"], metadata["omitted_required_sentinels"]
    assert metadata["aggregate_covered_sentinels"], metadata
    assert metadata["kubernetes_policy"] == "optional_bonus_only"

    covered = set()
    for item in selected:
        covered.update(v16._coverage_from_finding(item))

    required = {v16._coverage_key(v16._sentinel_key(item)) for item in risk_sentinels if v16._sentinel_key(item)[2] in v16.CORE_REQUIRED_KINDS}
    assert required <= covered
    assert v16._coverage_key((workflow, 19, v10.YAML_TOKEN_TO_PR_URL)) in covered
    assert v16._coverage_key((workflow, 25, v4.YAML_METADATA_SHELL)) in covered
    assert v16._coverage_key((py, 20, v16.PYTHON_DYNAMIC_EXEC)) in covered
    assert v16._coverage_key((ps, 17, v13.PS_RUN_KEY_PERSISTENCE)) in covered
    assert all(not v16._postable_key(item)[2].startswith("k8s_") for item in selected)

    rendered = "\n\n".join(v16._render_comment(item) for item in selected)
    assert "Reviewed with" not in rendered
    assert "```bash" in rendered

    test_python_path_write_sentinel_skips_test_files()
    test_python_path_write_sentinel_keeps_non_test_files()
    test_python_dynamic_exec_classifier_only_matches_execution_builtins()

    print("dcoir_review_required_runtime_patch_v16_selftest passed")


if __name__ == "__main__":
    main()
