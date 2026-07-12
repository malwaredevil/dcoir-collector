#!/usr/bin/env python3
"""Narrow self-test for the DCOIR Review v5 runtime patch layer."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v5_apply as v5_apply


def sentinel(path: str, line: int, text: str, label: str = "") -> SimpleNamespace:
    return SimpleNamespace(path=path, line=line, text=text, label=label, detail=label)


def test_nested_findings_accessor() -> None:
    nested = {"result": {"findings": [{"title": "nested"}]}, "findings": []}
    assert v5.findings_from_result(nested) == [{"title": "nested"}]
    direct = {"findings": [{"title": "direct"}]}
    assert v5.findings_from_result(direct) == [{"title": "direct"}]


def test_python_required_kinds_cover_exact_lines() -> None:
    yaml_sentinel = sentinel(
        "probe.py",
        9,
        "    return yaml.load(profile_text, Loader=yaml.Loader)",
        "unsafe deserialization primitive",
    )
    yaml_finding = {
        "path": "probe.py",
        "line": 9,
        "title": "Unsafe YAML deserialization via yaml.load with default Loader",
        "body": "Replace yaml.load with yaml.safe_load.",
        "_anchored_line_text": "    return yaml.load(profile_text, Loader=yaml.Loader)",
    }
    assert v5._sentinel_kind(yaml_sentinel) == v5.PYTHON_YAML_LOAD
    assert v5.finding_covers_sentinel(yaml_finding, yaml_sentinel)

    shell_sentinel = sentinel("probe.py", 13, "    return subprocess.Popen(command, shell=True)", "shell=True subprocess invocation")
    shell_finding = {
        "path": "probe.py",
        "line": 13,
        "title": "Shell=True subprocess invocation with caller-controlled command",
        "body": "Remove shell=True.",
        "_anchored_line_text": "    return subprocess.Popen(command, shell=True)",
    }
    assert v5._sentinel_kind(shell_sentinel) == v5.PYTHON_SHELL_EXEC
    assert v5.finding_covers_sentinel(shell_finding, shell_sentinel)


def test_env_token_templates_and_scrub() -> None:
    py_sentinel = sentinel(
        "probe.py",
        21,
        "token = os.getenv('DCOIR_TOKEN') headers={'Authorization': f'Bearer {token}'}",
        "environment token callback",
    )
    fallback = v5._fallback_finding(py_sentinel, SimpleNamespace(max_inline_comments=12))
    assert v5._semantic_kind(fallback) == v5.PYTHON_ENV_TOKEN
    rendered = v5.final_rendered_scrub(
        "Hardcoded bearer token creates secret exposure and should rotate exposed credential.",
        fallback,
    )
    lower = rendered.lower()
    assert "hardcoded" not in lower
    assert "secret exposure" not in lower
    assert "rotate exposed credential" not in lower


def test_yaml_metadata_shell_is_required_and_separate() -> None:
    metadata = sentinel(
        ".github/workflows/probe.yml",
        16,
        "        run: sh -c \"${{ github.event.pull_request.body }}\"",
        "GitHub Actions untrusted metadata shell execution",
    )
    finding = {
        "path": ".github/workflows/probe.yml",
        "line": 16,
        "title": "Shell execution of pull_request.body",
        "body": "PR body reaches sh -c.",
        "_anchored_line_text": "        run: sh -c \"${{ github.event.pull_request.body }}\"",
    }
    assert v5._sentinel_kind(metadata) == v5.v4.YAML_METADATA_SHELL
    assert v5.finding_covers_sentinel(finding, metadata)


def test_required_refill_inserts_missing_python_fallback() -> None:
    config = SimpleNamespace(max_inline_comments=12)
    hardened = SimpleNamespace(required_risk_sentinels=lambda sentinels: sentinels)
    yaml_sentinel = sentinel("probe.py", 9, "    return yaml.load(profile_text, Loader=yaml.Loader)")
    result = v5.add_risk_sentinel_fallback_findings(
        hardened,
        None,
        None,
        None,
        [],
        [yaml_sentinel],
        config,
    )
    assert len(result) == 1
    assert result[0]["line"] == 9
    assert v5._semantic_kind(result[0]) == v5.PYTHON_YAML_LOAD


def test_env_sentinel_detection_from_nearby_lines() -> None:
    class RiskSentinel(SimpleNamespace):
        pass

    lines = [
        SimpleNamespace(path="probe.py", line=17, text='    token = os.getenv("DCOIR_TOKEN")'),
        SimpleNamespace(path="probe.py", line=21, text='        headers={"Authorization": f"Bearer {token}"},'),
        SimpleNamespace(path="probe.ps1", line=15, text='$headers = @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        SimpleNamespace(path="probe.ps1", line=16, text='Invoke-RestMethod -Uri $CallbackUri -Headers $headers -Method Post'),
    ]
    hardened = SimpleNamespace(
        RiskSentinel=RiskSentinel,
        iter_added_diff_lines=lambda _diff: lines,
        is_comment_only_added_line=lambda _path, _text: False,
    )
    sentinels = v5_apply._make_env_token_sentinels(hardened, "diff")
    kinds = [v5._sentinel_kind(item) for item in sentinels]
    assert v5.PYTHON_ENV_TOKEN in kinds, kinds
    assert v5.PS_ENV_TOKEN in kinds, kinds


def test_apply_shim_exports_callable() -> None:
    assert callable(v5_apply.apply_pareto_context_module)


def main() -> None:
    test_nested_findings_accessor()
    test_python_required_kinds_cover_exact_lines()
    test_env_token_templates_and_scrub()
    test_yaml_metadata_shell_is_required_and_separate()
    test_required_refill_inserts_missing_python_fallback()
    test_env_sentinel_detection_from_nearby_lines()
    test_apply_shim_exports_callable()
    print("dcoir_review_required_runtime_patch_v5_selftest passed")


if __name__ == "__main__":
    main()
