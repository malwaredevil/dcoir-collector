#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v17 calibration overlay."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_required_runtime_patch_v17 as v17


WORKFLOW = ".github/workflows/dcoir-review-v17-probe.yml"
PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v17_probe.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v17_probe.ps1"
TYPESCRIPT = ".github/chatgpt_staging/dcoir_review_probe/v17_optional_pressure.ts"
K8S = ".github/chatgpt_staging/dcoir_review_probe/v17_bonus_k8s.yml"


def _s(path: str, line: int, kind: str, text: str) -> SimpleNamespace:
    title, body, _notes = v16._template_for_kind(kind)
    return SimpleNamespace(path=path, line=line, label=title, detail=body, text=text)


def risk_sentinels() -> list[SimpleNamespace]:
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
        _s(POWERSHELL, 9, v13.PS_PLAINTEXT_SECURE_STRING, "$secret = ConvertTo-SecureString $SecretText -AsPlainText -Force"),
        _s(POWERSHELL, 11, v4.PS_ACL, '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")'),
        _s(POWERSHELL, 13, v4.PS_ACL, "Set-Acl -Path $TargetPath -AclObject $acl"),
        _s(POWERSHELL, 14, v4.PS_PROCESS_LAUNCH, "Start-Process -FilePath $Executable -ArgumentList $Args -Wait"),
        _s(POWERSHELL, 15, v9.PS_DYNAMIC_EXEC, "IEX $Command"),
        _s(POWERSHELL, 16, v5.PS_ENV_TOKEN, 'Invoke-RestMethod -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        _s(POWERSHELL, 17, v13.PS_RUN_KEY_PERSISTENCE, 'New-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name ProbeV17 -Value $Executable -Force'),
        _s(TYPESCRIPT, 2, v13.TS_INNER_HTML, "  target.innerHTML = input.html;"),
        _s(TYPESCRIPT, 3, v13.TS_DYNAMIC_EXECUTION, "  const runner = new Function(input.code);"),
        _s(K8S, 7, v13.K8S_HOST_PATH, "hostPath:"),
    ]


def _coverage(selected: list[dict]) -> set[v16.SentinelKey]:
    covered: set[v16.SentinelKey] = set()
    for item in selected:
        covered.update(v16._coverage_from_finding(item))
    return covered


def test_selector_is_append_only_after_required_coverage() -> None:
    sentinels = risk_sentinels()
    base_selected, base_metadata = v16._select_once(SimpleNamespace(), [], sentinels, SimpleNamespace(max_inline_comments=12))
    base_keys = [v16._postable_key(item) for item in base_selected]
    assert base_metadata["overflow_required_count"] == 0

    v17.apply_pareto_context_module(SimpleNamespace(base=None, hardened=None))
    selected, metadata = v16._select_once(SimpleNamespace(), [], sentinels, SimpleNamespace(max_inline_comments=12))
    keys = [v16._postable_key(item) for item in selected]
    required = {v16._coverage_key(v16._sentinel_key(item)) for item in sentinels if v16._sentinel_key(item)[2] in v16.CORE_REQUIRED_KINDS}

    assert keys[: len(base_keys)] == base_keys
    assert len(keys) == len(set(keys))
    assert required <= _coverage(selected)
    assert metadata["hard_required_count"] == 21
    assert metadata["covered_required_count"] == 21
    assert metadata["overflow_required_count"] == 0
    assert metadata["required_partial_overflow"] is False
    assert metadata["partial_overflow"] is True
    assert metadata["optional_pressure_overflow"] is True
    assert metadata["coverage_ledger_readback"]["required_omitted"] == 0
    assert metadata["coverage_ledger_readback"]["inline_posted"] == 12
    assert any(key[0] == TYPESCRIPT and key[2] in v16.OPTIONAL_PRESSURE_KINDS for key in keys[len(base_keys) :])
    assert all(not key[2].startswith("k8s_") for key in keys)


def test_optional_pressure_does_not_displace_when_no_spare_slot() -> None:
    sentinels = risk_sentinels()
    original_select_once = getattr(v16, "_dcoir_required_v17_original_select_once", None)
    if original_select_once is None:
        original_select_once = v16._select_once
        v17.apply_pareto_context_module(SimpleNamespace(base=None, hardened=None))
    base_selected, _base_metadata = original_select_once(
        SimpleNamespace(),
        [],
        sentinels,
        SimpleNamespace(max_inline_comments=12),
    )
    no_spare_limit = len(base_selected)
    selected_no_spare, metadata_no_spare = v16._select_once(
        SimpleNamespace(),
        [],
        sentinels,
        SimpleNamespace(max_inline_comments=no_spare_limit),
    )
    keys = [v16._postable_key(item) for item in selected_no_spare]
    assert len(selected_no_spare) == no_spare_limit
    assert metadata_no_spare["unused_inline_slots"] == 0
    assert not any(key[0] == TYPESCRIPT for key in keys)
    assert metadata_no_spare["overflow_required_count"] == 0
    assert metadata_no_spare["required_partial_overflow"] is False


def test_rendering_canonicalizes_only_anchored_semantics() -> None:
    env_rendered = v16._render_comment(
        {
            "path": PYTHON,
            "line": 33,
            "title": "Outbound SSRF-prone request with hardcoded token and dynamic URL",
            "body": "Token is read from the environment and sent to callback_url.",
            "_anchored_line_text": '    return requests.post(callback_url, headers={"Authorization": f"Bearer {os.environ[\'DCOIR_TOKEN\']}"})',
            "_risk_sentinel_key": [PYTHON, 33, v5.PYTHON_ENV_TOKEN],
            "fix_guidance": {"language": "python", "notes": "Rotate the hardcoded secret."},
        }
    )
    env_token_title = "Environment token forwarded to request-controlled callback"
    assert env_token_title in env_rendered
    assert "hardcoded token" not in env_rendered.lower()
    assert "hardcoded secret" not in env_rendered.lower()

    literal_rendered = v16._render_comment(
        {
            "path": PYTHON,
            "line": 40,
            "title": "Hardcoded token literal",
            "body": "A literal token is present.",
            "_anchored_line_text": '    return requests.post(callback_url, headers={"Authorization": "Bearer literal-token"})',
            "_risk_sentinel_key": [PYTHON, 40, v5.PYTHON_ENV_TOKEN],
        }
    )
    assert "Hardcoded token literal" in literal_rendered

    run_key_rendered = v16._render_comment(
        {
            "path": POWERSHELL,
            "line": 17,
            "title": "HKLM Run-key persistence via caller-controlled path",
            "body": "Writes a current-user Run key.",
            "_anchored_line_text": 'New-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name ProbeV17 -Value $Executable -Force',
            "_risk_sentinel_key": [POWERSHELL, 17, v13.PS_RUN_KEY_PERSISTENCE],
        }
    )
    assert "HKCU Run-key" in run_key_rendered
    assert "HKLM Run-key" not in run_key_rendered


def test_false_missing_context_scrub_requires_exact_line_anchor() -> None:
    class FakeHardened:
        def __init__(self) -> None:
            self.artifacts: dict[str, object] = {}

        def write_debug_json_artifact_safely(self, _config, path, data) -> None:
            self.artifacts[path] = data

    def file_line_text(file_text: str, line: int) -> str:
        lines = file_text.splitlines()
        return lines[line - 1] if 0 < line <= len(lines) else ""

    def safe_artifact_name(_path: str, fallback: str) -> str:
        return fallback

    def original_synthesize(_index, finding, _file_text, _schema, _config):
        enriched = dict(finding)
        enriched["fix_guidance"] = {
            "language": "python",
            "notes": "The supplied file content does not contain the line `exec(filter_source)`. The `render_filter` function body is missing from the head-file context.",
        }
        return enriched

    fake_hardened = FakeHardened()
    module = SimpleNamespace(
        base=None,
        hardened=fake_hardened,
        file_line_text=file_line_text,
        safe_artifact_name=safe_artifact_name,
        synthesize_fix_for_finding=original_synthesize,
    )
    v17.apply_pareto_context_module(module)

    file_text = "\n".join(
        [
            "def render_filter(filter_source):",
            "    exec(filter_source)",
            "def unrelated():",
            "    exec(filter_source)",
        ]
    )
    finding = {
        "path": PYTHON,
        "line": 2,
        "title": "Arbitrary Python code execution",
        "body": "exec runs caller-controlled code.",
        "_anchored_line_text": "    exec(filter_source)",
        "_risk_sentinel_key": [PYTHON, 2, v16.PYTHON_DYNAMIC_EXEC],
    }
    scrubbed = module.synthesize_fix_for_finding(1, finding, file_text, {}, SimpleNamespace())
    assert "does not contain" not in scrubbed["fix_guidance"]["notes"].lower()
    assert scrubbed["fix_guidance"]["remove"] == "    exec(filter_source)"
    assert fake_hardened.artifacts

    wrong_line = dict(finding)
    wrong_line["line"] = 1
    not_scrubbed = module.synthesize_fix_for_finding(2, wrong_line, file_text, {}, SimpleNamespace())
    assert "does not contain" in not_scrubbed["fix_guidance"]["notes"].lower()


def main() -> None:
    test_selector_is_append_only_after_required_coverage()
    test_optional_pressure_does_not_displace_when_no_spare_slot()
    test_rendering_canonicalizes_only_anchored_semantics()
    test_false_missing_context_scrub_requires_exact_line_anchor()
    print("dcoir_review_required_runtime_patch_v17_selftest passed")


if __name__ == "__main__":
    main()
