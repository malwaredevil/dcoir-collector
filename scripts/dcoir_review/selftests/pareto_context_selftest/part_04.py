scope_reset_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+def build_path(filename, output_dir):
+    destination = Path(output_dir) / filename
+
+def write_supplied_path(destination, note):
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in scope_reset_sentinels)

outer_path_survives_nested_same_name_assignment_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,9 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    def helper(other_output_dir):
+        destination = Path(other_output_dir) / "helper.txt"
+        return destination
+    helper(output_dir)
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in outer_path_survives_nested_same_name_assignment_sentinels
)

comparison_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_supplied_path(destination, filename, note):
+    if destination == Path(f"{filename}"):
+        destination.write_text(note, encoding="utf-8")
"""
)
assert mod.python_dynamic_path_target("if destination == Path(f'{filename}'):") is None
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in comparison_path_sentinels)

attribute_exact_reassign_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+class Writer:
+    def write_triage_note(self, filename, note, output_dir):
+        self.destination = Path(output_dir) / filename
+        self.destination = Path(output_dir) / "summary.txt"
+        self.destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in attribute_exact_reassign_sentinels)

attribute_root_rebind_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+class Writer:
+    def write_triage_note(self, filename, note, output_dir, replacement):
+        self.destination = Path(output_dir) / filename
+        self = replacement
+        self.destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in attribute_root_rebind_sentinels)

attribute_subscript_mutation_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+class Writer:
+    def write_triage_note(self, filename, note, output_dir):
+        self.destination = Path(output_dir) / filename
+        self.destination[0] = "safe"
+        self.destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in attribute_subscript_mutation_sentinels)

captured_max_anchors = []
original_detect_risk_sentinels = mod._original_detect_risk_sentinels


def fake_original_detect_risk_sentinels(_diff, max_anchors=None):
    captured_max_anchors.append(max_anchors)
    return [
        mod.hardened.RiskSentinel(
            path=f"tools/original_{index}.py",
            line=index,
            label=f"original sentinel {index}",
            detail="original sentinel detail",
            text="original sentinel text",
        )
        for index in range(1, 4)
    ]


mod._original_detect_risk_sentinels = fake_original_detect_risk_sentinels
try:
    bounded_path_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    destination.write_text(note, encoding="utf-8")
""",
        max_anchors=3,
    )
finally:
    mod._original_detect_risk_sentinels = original_detect_risk_sentinels
assert captured_max_anchors == [None]
assert len(bounded_path_sentinels) == 3
assert bounded_path_sentinels[0].label == mod.FILE_WRITE_PATH_LABEL



python_dynamic_exec_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/eval_probe.py b/tools/eval_probe.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/eval_probe.py
@@ -0,0 +1,5 @@
+import os
+def evaluate_operator_expression(expression):
+    return eval(expression, {"__builtins__": __builtins__}, {"os": os})
+def execute_operator_expression(expression):
+    exec(expression)
"""
)
assert any(
    item.path == "tools/eval_probe.py"
    and item.line == 3
    and item.label == mod.PYTHON_DYNAMIC_EXEC_LABEL
    for item in python_dynamic_exec_sentinels
)
assert any(
    item.path == "tools/eval_probe.py"
    and item.line == 5
    and item.label == mod.PYTHON_DYNAMIC_EXEC_LABEL
    for item in python_dynamic_exec_sentinels
)
literal_eval_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/literal_probe.py b/tools/literal_probe.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/literal_probe.py
@@ -0,0 +1,4 @@
+import ast
+def parse_literal(expression):
+    return ast.literal_eval(expression)
"""
)
assert not any(item.label == mod.PYTHON_DYNAMIC_EXEC_LABEL for item in literal_eval_sentinels)
fixture_eval_string_sentinels = mod.detect_risk_sentinels(
    '''diff --git a/scripts/openrouter_pr_review_pareto_context_selftest.py b/scripts/openrouter_pr_review_pareto_context_selftest.py
index 0000000..1111111 100644
--- /dev/null
+++ b/scripts/openrouter_pr_review_pareto_context_selftest.py
@@ -0,0 +1,3 @@
+# Intentional fixture string; never executed by this selftest.
+fixture = "return eval(expression)"
'''
)
assert not any(item.label == mod.PYTHON_DYNAMIC_EXEC_LABEL for item in fixture_eval_string_sentinels)

class FakeGitHubClient:
    repo = "DCOIR-Collector/dcoir-collector"

    def __init__(self, reviews: list[dict[str, str]] | None = None) -> None:
        self.reviews = reviews or []
        self.files = {
            "tools/review_probe.py": "def run_probe(command):\n    return subprocess.run(command, shell=True)\n",
            "docs/review.md": "# Review\n\nKeep governed review evidence visible.\n",
            "tools/later_probe.py": "import subprocess\n\nsubprocess.run('whoami', shell=True)\n",
            "tools/huge_probe.py": "print('large context line')\n" * 1000,
            "tools/aliased_writer.py": "from pathlib import Path as P\nimport pathlib as pl\nimport os as operating_system\n\ndef write_triage_note(filename, note, output_dir):\n    destination = P(output_dir, filename)\n    pl.Path(destination).write_text(note)\n",
        }

    def request(self, _method: str, path: str):
        if path.startswith("/repos/DCOIR-Collector/dcoir-collector/pulls/287/reviews"):
            params = mod.urllib.parse.parse_qs(mod.urllib.parse.urlparse(path).query)
            page = int(params.get("page", ["1"])[0])
            return self.reviews if page == 1 else []
        if "/contents/" not in path:
            raise AssertionError(f"unexpected GitHub path: {path}")
        encoded_path = path.split("/contents/", 1)[1].split("?", 1)[0]
        file_path = mod.urllib.parse.unquote(encoded_path)
        if file_path == "large/oversized.py":
            return {"type": "file", "encoding": "none", "content": ""}
        content = self.files[file_path].encode("utf-8")
        return {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(content).decode("ascii"),
        }
