#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v18 cleanup overlay."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_required_runtime_patch_v17 as v17
import dcoir_review_required_runtime_patch_v18 as v18


PYTHON = ".github/chatgpt_staging/dcoir_review_probe/v17_probe.py"
POWERSHELL = ".github/chatgpt_staging/dcoir_review_probe/v17_probe.ps1"


def _apply() -> None:
    module = SimpleNamespace(base=None, hardened=None)
    v17.apply_pareto_context_module(module)
    v18.apply_pareto_context_module(module)


def test_render_scrubs_internal_schema_text() -> None:
    _apply()
    rendered = v16._render_comment(
        {
            "path": PYTHON,
            "line": 20,
            "title": "Python executes caller-controlled code",
            "body": "This line evaluates text as Python code.",
            "_anchored_line_text": "    exec(filter_source)",
            "_risk_sentinel_key": [PYTHON, 20, v16.PYTHON_DYNAMIC_EXEC],
            "suggested_replacement": "No anchored repair can be synthesized because the finding_id field is missing.",
            "fix_guidance": {
                "language": "python",
                "notes": "Remove exec.",
            },
        }
    )
    assert "finding_id" not in rendered
    assert "supplied finding" not in rendered
    assert "no anchored repair" not in rendered.lower()
    assert "non-executing parser" in rendered

    non_dynamic_rendered = v16._render_comment(
        {
            "path": POWERSHELL,
            "line": 11,
            "title": "The required finding_id field is missing",
            "body": "The supplied finding cannot be repaired.",
            "validation": "No anchored repair can be synthesized.",
            "_anchored_line_text": '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")',
            "_risk_sentinel_key": [POWERSHELL, 11, v4.PS_ACL],
            "fix_guidance": {
                "language": "powershell",
                "notes": "Narrow ACLs.",
            },
        }
    )
    assert "finding_id" not in non_dynamic_rendered
    assert "supplied finding" not in non_dynamic_rendered
    assert "no anchored repair" not in non_dynamic_rendered.lower()
    assert "non-executing parser" not in non_dynamic_rendered
    assert "targeted fix" in non_dynamic_rendered


def test_env_token_and_run_key_canonicalization_survive_v18() -> None:
    _apply()
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
    assert "Environment token forwarded to request-controlled callback" in env_rendered
    assert "hardcoded token" not in env_rendered.lower()
    assert "hardcoded secret" not in env_rendered.lower()

    run_key_rendered = v16._render_comment(
        {
            "path": POWERSHELL,
            "line": 17,
            "title": "HKLM Run-key persistence via caller-controlled path",
            "body": "Writes a current-user Run key.",
            "_anchored_line_text": 'New-ItemProperty -Path "HKCU:\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run" -Name ProbeV17 -Value $Executable -Force',
            "_risk_sentinel_key": [POWERSHELL, 17, v13.PS_RUN_KEY_PERSISTENCE],
        }
    )
    assert "HKCU Run-key" in run_key_rendered
    assert "HKLM Run-key" not in run_key_rendered


def test_aggregate_run_key_hive_is_visible() -> None:
    _apply()
    aggregate = {
        "path": POWERSHELL,
        "line": 11,
        "title": "PowerShell broad ACL grant exposes collector output",
        "body": "This PowerShell change grants broad filesystem ACL rights.",
        "_anchored_line_text": '$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")',
        "_risk_sentinel_key": [POWERSHELL, 11, v4.PS_ACL],
        "covered_risk_sentinel_keys": [
            [POWERSHELL, 11, v4.PS_ACL],
            [POWERSHELL, 17, v13.PS_RUN_KEY_PERSISTENCE],
        ],
        "fix_guidance": {"language": "powershell", "notes": "Narrow ACLs."},
    }
    sentinel = SimpleNamespace(
        path=POWERSHELL,
        line=17,
        label="PowerShell writes a Windows Run-key persistence location",
        detail="This line writes to a Run-key persistence location.",
        text='New-ItemProperty -Path "HKCU:\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run" -Name ProbeV17 -Value $Executable -Force',
    )
    v18._attach_covered_signal_text([aggregate], [sentinel])
    rendered = v16._render_comment(aggregate)
    assert "HKCU Run-key persistence" in rendered
    assert "startup-persistence risk" in rendered


def test_internal_fix_synthesis_leak_preserves_raw_artifact() -> None:
    class FakeHardened:
        def __init__(self) -> None:
            self.artifacts: dict[str, object] = {}

        def write_debug_json_artifact_safely(self, _config, path, data) -> None:
            self.artifacts[path] = data

    def original_synthesize(_index, finding, _file_text, _schema, _config):
        enriched = dict(finding)
        enriched["suggested_replacement"] = "No anchored repair can be synthesized because the finding_id field is missing."
        enriched["fix_guidance"] = {
            "language": "python",
            "notes": "Remove the unsafe call.",
        }
        return enriched

    fake_hardened = FakeHardened()
    module = SimpleNamespace(
        base=None,
        hardened=fake_hardened,
        file_line_text=lambda file_text, line: file_text.splitlines()[line - 1],
        safe_artifact_name=lambda _path, fallback: fallback,
        synthesize_fix_for_finding=original_synthesize,
    )
    v18.apply_pareto_context_module(module)
    result = module.synthesize_fix_for_finding(
        1,
        {
            "path": PYTHON,
            "line": 2,
            "_anchored_line_text": "    exec(filter_source)",
            "_risk_sentinel_key": [PYTHON, 2, v16.PYTHON_DYNAMIC_EXEC],
        },
        "def render_filter(filter_source):\n    exec(filter_source)",
        {},
        SimpleNamespace(),
    )
    assert "finding_id" not in result["fix_guidance"]["notes"]
    assert result["fix_guidance"]["remove"] == "    exec(filter_source)"
    assert any(path.startswith("responses/fix-synthesis-v18/") for path in fake_hardened.artifacts)
    artifact = next(iter(fake_hardened.artifacts.values()))
    assert artifact["suppressed_internal_fix_synthesis_leak"] is True
    assert artifact["raw_fix_synthesis_preserved"] is True
    assert "finding_id" in artifact["raw_posted_fields"]["suggested_replacement"]

    leaking_line = '    exec("No anchored repair can be synthesized because the finding_id field is missing")'
    line_marker_hardened = FakeHardened()
    line_marker_module = SimpleNamespace(
        base=None,
        hardened=line_marker_hardened,
        file_line_text=lambda file_text, line: file_text.splitlines()[line - 1],
        safe_artifact_name=lambda _path, fallback: fallback,
        synthesize_fix_for_finding=original_synthesize,
    )
    v18.apply_pareto_context_module(line_marker_module)
    line_marker_result = line_marker_module.synthesize_fix_for_finding(
        3,
        {
            "path": PYTHON,
            "line": 2,
            "_anchored_line_text": leaking_line,
            "_risk_sentinel_key": [PYTHON, 2, v16.PYTHON_DYNAMIC_EXEC],
        },
        f"def trigger_v18_raw_preservation():\n{leaking_line}",
        {},
        SimpleNamespace(),
    )
    assert "finding_id" not in str(line_marker_result["fix_guidance"])
    assert "no anchored repair" not in str(line_marker_result["fix_guidance"]).lower()
    assert "remove" not in line_marker_result["fix_guidance"]
    line_marker_artifact = next(iter(line_marker_hardened.artifacts.values()))
    assert "finding_id" in str(line_marker_artifact["raw_posted_fields"])
    assert "finding_id" not in str(line_marker_artifact["normalized_fix_guidance"])
    assert "no anchored repair" not in str(line_marker_artifact["normalized_fix_guidance"]).lower()

    non_dynamic_module = SimpleNamespace(
        base=None,
        hardened=FakeHardened(),
        file_line_text=lambda file_text, line: file_text.splitlines()[line - 1],
        safe_artifact_name=lambda _path, fallback: fallback,
        synthesize_fix_for_finding=original_synthesize,
    )
    v18.apply_pareto_context_module(non_dynamic_module)
    non_dynamic = non_dynamic_module.synthesize_fix_for_finding(
        2,
        {
            "path": POWERSHELL,
            "line": 1,
            "_anchored_line_text": "Set-Acl -Path $TargetPath -AclObject $acl",
            "_risk_sentinel_key": [POWERSHELL, 1, v4.PS_ACL],
        },
        "Set-Acl -Path $TargetPath -AclObject $acl",
        {},
        SimpleNamespace(),
    )
    assert "finding_id" not in non_dynamic["fix_guidance"]["notes"]
    assert "non-executing parser" not in non_dynamic["fix_guidance"]["notes"]
    assert "targeted fix" in non_dynamic["fix_guidance"]["notes"]


def main() -> None:
    test_render_scrubs_internal_schema_text()
    test_env_token_and_run_key_canonicalization_survive_v18()
    test_aggregate_run_key_hive_is_visible()
    test_internal_fix_synthesis_leak_preserves_raw_artifact()
    print("dcoir_review_required_runtime_patch_v18_selftest passed")


if __name__ == "__main__":
    main()
