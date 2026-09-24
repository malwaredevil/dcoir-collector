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


def fake_original_non_python_urlopen(_diff, _max_anchors=None):
    return [
        mod.hardened.RiskSentinel(
            path="docs/reference.txt",
            line=1,
            label=mod.FILE_WRITE_PATH_LABEL,
            detail="legacy sentinel detail",
            text="urllib.request.urlopen(",
        )
    ]


mod._original_detect_risk_sentinels = fake_original_non_python_urlopen
try:
    non_python_urlopen_sentinels = mod.detect_risk_sentinels(
        """diff --git a/docs/reference.txt b/docs/reference.txt
index 0000000..1111111 100644
--- /dev/null
+++ b/docs/reference.txt
@@ -0,0 +1,1 @@
+urllib.request.urlopen(
"""
    )
finally:
    mod._original_detect_risk_sentinels = original_detect_risk_sentinels
assert any(item.path == "docs/reference.txt" and item.label == mod.FILE_WRITE_PATH_LABEL for item in non_python_urlopen_sentinels)



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
    '''diff --git a/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py b/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
index 0000000..1111111 100644
--- /dev/null
+++ b/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
@@ -0,0 +1,3 @@
+# Intentional fixture string; never executed by this selftest.
+fixture = "return eval(expression)"
'''
)
assert not any(item.label == mod.PYTHON_DYNAMIC_EXEC_LABEL for item in fixture_eval_string_sentinels)
