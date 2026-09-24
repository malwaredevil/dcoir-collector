multiline_urlopen_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/http_client.py b/tools/http_client.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_client.py
@@ -0,0 +1,6 @@
+import urllib.request
+def fetch(req):
+    with urllib.request.urlopen(
+        req,
+    ) as response:
+        return response.read()
"""
)
assert not any(
    item.path == "tools/http_client.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in multiline_urlopen_sentinels
), multiline_urlopen_sentinels

os_open_read_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_read.py b/tools/os_read.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_read.py
@@ -0,0 +1,4 @@
+import os
+def load(user_path):
+    fd = os.open(user_path, os.O_RDONLY)
+    return fd
"""
)
assert not any(
    item.path == "tools/os_read.py" and item.label in legacy_path_write_labels
    for item in os_open_read_sentinels
), os_open_read_sentinels

os_open_read_with_flags_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_read_with_flags.py b/tools/os_read_with_flags.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_read_with_flags.py
@@ -0,0 +1,4 @@
+import os
+def load(user_path):
+    fd = os.open(user_path, os.O_RDONLY | os.O_CLOEXEC)
+    return fd
"""
)
assert not any(
    item.path == "tools/os_read_with_flags.py" and item.label in legacy_path_write_labels
    for item in os_open_read_with_flags_sentinels
), os_open_read_with_flags_sentinels

os_open_read_via_variable_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_read_variable.py b/tools/os_read_variable.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_read_variable.py
@@ -0,0 +1,5 @@
+import os
+def load(user_path):
+    flags = os.O_RDONLY
+    fd = os.open(user_path, flags)
+    return fd
"""
)
assert not any(
    item.path == "tools/os_read_variable.py" and item.label in legacy_path_write_labels
    for item in os_open_read_via_variable_sentinels
), os_open_read_via_variable_sentinels

os_open_branch_overridden_flags_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_branch_flags.py b/tools/os_branch_flags.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_branch_flags.py
@@ -0,0 +1,7 @@
+import os
+def persist(user_path, safe):
+    flags = os.O_WRONLY | os.O_CREAT
+    if safe:
+        flags = os.O_RDONLY
+    fd = os.open(user_path, flags)
+    return fd
"""
)
assert any(
    item.path == "tools/os_branch_flags.py"
    and item.line == 6
    and item.label in legacy_path_write_labels
    for item in os_open_branch_overridden_flags_sentinels
), os_open_branch_overridden_flags_sentinels

os_open_write_via_variable_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_write_variable.py b/tools/os_write_variable.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_write_variable.py
@@ -0,0 +1,5 @@
+import os
+def persist(user_path):
+    flags = os.O_WRONLY | os.O_CREAT
+    fd = os.open(user_path, flags)
+    return fd
"""
)
assert any(
    item.path == "tools/os_write_variable.py"
    and item.line == 4
    and item.label in legacy_path_write_labels
    for item in os_open_write_via_variable_sentinels
), os_open_write_via_variable_sentinels

os_open_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_write.py b/tools/os_write.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_write.py
@@ -0,0 +1,4 @@
+import os
+def persist(user_path):
+    fd = os.open(user_path, os.O_WRONLY | os.O_CREAT)
+    return fd
"""
)
assert any(
    item.path == "tools/os_write.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_write_sentinels
), os_open_write_sentinels

os_open_read_create_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_read_create.py b/tools/os_read_create.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_read_create.py
@@ -0,0 +1,4 @@
+import os
+def create(user_path):
+    fd = os.open(user_path, os.O_RDONLY | os.O_CREAT)
+    return fd
"""
)
assert any(
    item.path == "tools/os_read_create.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_read_create_sentinels
), os_open_read_create_sentinels

os_open_keyword_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_keyword_path.py b/tools/os_keyword_path.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_keyword_path.py
@@ -0,0 +1,4 @@
+import os
+def persist(user_path):
+    fd = os.open(path=user_path, flags=os.O_WRONLY)
+    return fd
"""
)
assert any(
    item.path == "tools/os_keyword_path.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_keyword_path_sentinels
), os_open_keyword_path_sentinels

os_open_kwargs_expansion_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_kwargs_writer.py b/tools/os_kwargs_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_kwargs_writer.py
@@ -0,0 +1,4 @@
+import os
+def persist(user_path, options):
+    fd = os.open(user_path, **options)
+    return fd
"""
)
assert any(
    item.path == "tools/os_kwargs_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_kwargs_expansion_sentinels
), os_open_kwargs_expansion_sentinels

os_open_partially_unknown_flags_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_partial_flags.py b/tools/os_partial_flags.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_partial_flags.py
@@ -0,0 +1,5 @@
+import os
+def persist(user_path, user_flags):
+    fd = os.open(user_path, os.O_RDONLY | user_flags)
+    return fd
"""
)
assert any(
    item.path == "tools/os_partial_flags.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_partially_unknown_flags_sentinels
), os_open_partially_unknown_flags_sentinels

os_open_large_shift_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_large_shift.py b/tools/os_large_shift.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_large_shift.py
@@ -0,0 +1,4 @@
+import os
+def persist(user_path):
+    fd = os.open(user_path, 1 << 1000000000)
+    return fd
"""
)
assert any(
    item.path == "tools/os_large_shift.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_large_shift_sentinels
), os_open_large_shift_sentinels

os_open_negative_shift_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_negative_shift.py b/tools/os_negative_shift.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_negative_shift.py
@@ -0,0 +1,4 @@
+import os
+def persist(user_path):
+    fd = os.open(user_path, 1 << -1)
+    return fd
"""
)
assert any(
    item.path == "tools/os_negative_shift.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_negative_shift_sentinels
), os_open_negative_shift_sentinels

read_only_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/read_only_path.py b/tools/read_only_path.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/read_only_path.py
@@ -0,0 +1,4 @@
+from pathlib import Path
+def load(user_path):
+    with Path(user_path).open("r") as handle:
+        return handle.read()
"""
)
assert not any(
    item.path == "tools/read_only_path.py"
    and item.label in legacy_path_write_labels
    for item in read_only_path_open_sentinels
), read_only_path_open_sentinels


unsafe_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_path_writer.py b/tools/unsafe_path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_path_writer.py
@@ -0,0 +1,4 @@
+from pathlib import Path
+def persist(user_path, payload):
+    with Path(user_path).open("wb") as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_path_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in unsafe_path_open_sentinels
), unsafe_path_open_sentinels

unsafe_multiline_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_multiline_path_writer.py b/tools/unsafe_multiline_path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_multiline_path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def persist(user_path, payload):
+    with Path(user_path).open(
+        "wb",
+    ) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_multiline_path_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in unsafe_multiline_path_open_sentinels
), unsafe_multiline_path_open_sentinels

unsafe_assigned_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_assigned_writer.py b/tools/unsafe_assigned_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_assigned_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def persist(output_dir, filename, payload):
+    target = Path(output_dir) / filename
+    with target.open("w") as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_assigned_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in unsafe_assigned_path_open_sentinels
), unsafe_assigned_path_open_sentinels

unsafe_chained_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_chained_writer.py b/tools/unsafe_chained_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_chained_writer.py
@@ -0,0 +1,4 @@
+from pathlib import Path
+def persist(root, filename, payload):
+    with (Path(root) / filename).open("w") as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_chained_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in unsafe_chained_path_open_sentinels
), unsafe_chained_path_open_sentinels

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
