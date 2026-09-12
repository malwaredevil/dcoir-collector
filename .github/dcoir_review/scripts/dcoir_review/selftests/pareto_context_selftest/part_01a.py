assert mod.review_mode_for_command("/dcoir-review", "/dcoir-review", config, True) == "diff"
assert mod.review_mode_for_command("/dcoir-review deep", "/dcoir-review", config, True) == "deep-forced"
assert mod.review_mode_for_command("/dcoir-review exhaustive", "/dcoir-review", config, True) == "deep-forced"
assert mod.review_mode_for_command("/dcoir-review diff", "/dcoir-review", config, False) == "diff"

anchor_diff = """diff --git a/probes/serialization_probe.py b/probes/serialization_probe.py
index 0000000..1111111 100644
--- /dev/null
+++ b/probes/serialization_probe.py
@@ -0,0 +1,5 @@
+import pickle
+def restore(raw_payload):
+    return pickle.loads(raw_payload)
+    return None
+# end
"""
anchor_line_index = mod.hardened.build_added_line_index(anchor_diff)
anchor_sentinels = mod.detect_risk_sentinels(anchor_diff)
anchored_findings, anchor_unanchored = mod.split_findings_with_review_body_fallback(
    {
        "summary": "Found unsafe deserialization.",
        "findings": [
            {
                "title": "Unsafe pickle deserialization",
                "severity": "high",
                "confidence": 0.95,
                "path": "probes/serialization_probe.py",
                "line": 4,
                "body": "The changed code deserializes untrusted bytes with pickle.loads.",
                "validation": "python3 -m py_compile probes/serialization_probe.py",
                "suggested_replacement": "",
            }
        ],
    },
    config,
    anchor_line_index,
    anchor_diff,
    anchor_sentinels,
)
assert anchor_unanchored == []
# The model supplied line 4, which is already an added changed line. The stable
# normalization contract preserves that exact GitHub-postable evidence boundary
# even though nearby line 3 contains stronger lexical/sentinel matches.
assert anchored_findings[0]["line"] == 4
assert anchored_findings[0].get("_reanchored_from_line") is None

yaml_sentinels = mod.detect_risk_sentinels(
    """diff --git a/.github/workflows/probe.yml b/.github/workflows/probe.yml
index 0000000..1111111 100644
--- /dev/null
+++ b/.github/workflows/probe.yml
@@ -0,0 +1,13 @@
+name: probe
+on:
+  pull_request_target:
+permissions:
+  contents: write
+jobs:
+  test:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+        with:
+          ref: ${{ github.event.pull_request.head.sha }}
+      - run: curl https://example.test/install.sh | bash
"""
)
assert any(item.label == mod.GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_LABEL and item.line == 5 for item in yaml_sentinels)
assert any(item.label == mod.GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_LABEL and item.line == 12 for item in yaml_sentinels)