#!/usr/bin/env python3
"""Regression checks for stable hard-required coverage ownership."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_required_runtime_patch_v2 as v2


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v2" not in names, names
    assert "dcoir_review.required_coverage_policy" in names, names
    assert names.index("dcoir_review.required_coverage_policy") < names.index("dcoir_review.anchor_scoring")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    assert review.hardened.required_risk_sentinels.__module__ == "dcoir_review.required_coverage_policy"
    assert review.hardened.risk_sentinel_fallback_finding.__module__ == "dcoir_review.required_coverage_policy"
    assert review.synthesize_fix_for_finding.__module__ == "dcoir_review.required_coverage_policy"

    diff = """diff --git a/tools/acl.ps1 b/tools/acl.ps1
--- /dev/null
+++ b/tools/acl.ps1
@@ -0,0 +1,3 @@
+$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "Allow")
+$acl.AddAccessRule($rule)
+Set-Acl -LiteralPath $OutputDirectory -AclObject $acl
"""
    sentinels = review.detect_risk_sentinels(diff, 64)
    acl = next(item for item in sentinels if v2._sentinel_kind(item) == v2.PS_ACL_KIND)
    assert acl.label == "PowerShell broad ACL grant"
    assert review.hardened.is_required_risk_sentinel(acl)
    fallback = review.hardened.risk_sentinel_fallback_finding(acl, SimpleNamespace(max_inline_comments=12))
    assert fallback["title"] == v2.HARD_REQUIRED_KIND_TITLES[v2.PS_ACL_KIND]
    assert fallback["validation"].startswith("pwsh -NoProfile -Command")
    assert review.hardened.finding_covers_risk_sentinel(fallback, acl)

    print("dcoir_review_required_coverage_policy_selftest passed")


if __name__ == "__main__":
    main()
