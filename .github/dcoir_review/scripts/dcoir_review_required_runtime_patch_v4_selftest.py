#!/usr/bin/env python3
"""Narrow self-test for the DCOIR Review v4 runtime patch layer."""

from __future__ import annotations

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v4_apply as v4_apply


def test_trigger_line_not_contaminated_by_metadata_shell() -> None:
    finding = {
        "path": ".github/workflows/probe.yml",
        "line": 3,
        "title": "Privileged pull_request_target workflow context",
        "body": "Line 15 runs bash -c with github.event.pull_request.title.",
        "_anchored_line_text": "  pull_request_target:",
        "fix_guidance": {"language": "yaml", "remove": "      - run: bash -c \"${{ github.event.pull_request.title }}\""},
    }
    normalized = v4._normalize_comment_finding(finding)
    assert v4._semantic_kind(normalized) == v4.YAML_PULL_REQUEST_TARGET
    assert normalized["title"] == v4.HARD_REQUIRED_KIND_TITLES[v4.YAML_PULL_REQUEST_TARGET]
    assert "metadata" not in normalized["body"].lower()
    assert "remove" not in normalized.get("fix_guidance", {}), normalized.get("fix_guidance")


def test_metadata_shell_has_own_template_and_validation() -> None:
    finding = {
        "path": ".github/workflows/probe.yml",
        "line": 15,
        "title": "GitHub Actions workflow grants write permissions",
        "body": "Pull request title is executed by bash.",
        "_anchored_line_text": "      - run: bash -c \"${{ github.event.pull_request.title }}\"",
    }
    normalized = v4._normalize_comment_finding(finding)
    assert v4._semantic_kind(normalized) == v4.YAML_METADATA_SHELL
    assert normalized["title"] == v4.OPTIONAL_KIND_TITLES[v4.YAML_METADATA_SHELL]
    assert "assert text.strip" not in normalized["validation"]
    assert "github\\.event\\.pull_request" in normalized["validation"]


def test_env_token_callback_uses_deterministic_body() -> None:
    finding = {
        "path": "tools/probe.ps1",
        "line": 15,
        "title": "Hardcoded bearer token sent to request-controlled URL",
        "body": "This static credential creates secret exposure and should rotate exposed credential.",
        "_anchored_line_text": "Invoke-WebRequest -Uri $CallbackUrl -Headers @{ Authorization = \"Bearer $env:DCOIR_TOKEN\" }",
    }
    normalized = v4._normalize_comment_finding(finding)
    rendered = v4._render_deterministic_comment(normalized, "test-model")
    lower = rendered.lower()
    assert "environment token read from env and forwarded to request-controlled callback" in lower
    for banned in ("static credential", "secret exposure", "environment token value", "hardcoded", "literal bearer", "rotate exposed credential"):
        assert banned not in lower, rendered


def test_shell_pipe_https_does_not_claim_plain_http() -> None:
    finding = {
        "path": ".github/workflows/probe.yml",
        "line": 14,
        "title": "Workflow pipes a network installer into a shell",
        "_anchored_line_text": "      - run: wget -qO- https://example.invalid/bootstrap.sh | sh",
    }
    normalized = v4._normalize_comment_finding(finding)
    rendered = v4._render_deterministic_comment(normalized, "test-model")
    assert "plain HTTP" not in rendered
    assert "network-fetched content" in rendered


def test_notes_code_gets_fenced() -> None:
    notes = "Use a trusted ref instead.\n# current\nref: ${{ github.event.pull_request.head.sha }}\n# swap to\nref: ${{ github.sha }}"
    formatted = v4._format_notes(notes, ".github/workflows/probe.yml")
    assert "```yaml" in formatted, formatted
    assert "# current" in formatted
    assert "ref: ${{ github.sha }}" in formatted


def test_mismatched_remove_is_suppressed() -> None:
    finding = {
        "path": ".github/workflows/probe.yml",
        "line": 3,
        "_anchored_line_text": "  pull_request_target:",
        "fix_guidance": {"language": "yaml", "remove": "      - run: bash -c \"${{ github.event.pull_request.title }}\""},
    }
    guidance = v4._sanitize_fix_guidance(finding)
    assert "remove" not in guidance, guidance


def test_duplicate_start_process_key_collapses() -> None:
    first = {
        "path": "tools/probe.ps1",
        "line": 14,
        "title": "PowerShell caller-controlled process launch",
        "_anchored_line_text": "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait",
    }
    second = dict(first, title="Caller-controlled Start-Process execution without allowlisting")
    assert v4._dedupe_key(v4._normalize_comment_finding(first)) == v4._dedupe_key(v4._normalize_comment_finding(second))


def test_apply_shim_exports_callable() -> None:
    assert callable(v4_apply.apply_pareto_context_module)


def main() -> None:
    test_trigger_line_not_contaminated_by_metadata_shell()
    test_metadata_shell_has_own_template_and_validation()
    test_env_token_callback_uses_deterministic_body()
    test_shell_pipe_https_does_not_claim_plain_http()
    test_notes_code_gets_fenced()
    test_mismatched_remove_is_suppressed()
    test_duplicate_start_process_key_collapses()
    test_apply_shim_exports_callable()
    print("dcoir_review_required_runtime_patch_v4_selftest passed")


if __name__ == "__main__":
    main()
