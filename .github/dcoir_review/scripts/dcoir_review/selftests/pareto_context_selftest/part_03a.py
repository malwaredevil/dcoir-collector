self_derived_context_reassign_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -1,6 +1,7 @@
 from pathlib import Path
 def write_triage_note(filename, note, output_dir):
     destination = Path(output_dir) / filename
+    destination = destination.resolve()
     destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.text.strip() == "destination = destination.resolve()"
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in self_derived_context_reassign_sentinels
)
value_less_annotation_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    destination: Path
+    destination.write_text(note, encoding="utf-8")
"""
)
assert mod.python_simple_assignment("destination: Path") is None
assert "destination" not in mod.python_assignment_target_names("destination: Path")
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in value_less_annotation_sentinels
)

augmented_dynamic_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    destination = Path("/safe")
+    destination /= filename
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.text.strip() == "destination /= filename"
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in augmented_dynamic_path_sentinels
)

augmented_context_dynamic_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -1,5 +1,6 @@
 from pathlib import Path
 def write_triage_note(filename, note):
     destination = Path("/safe")
+    destination /= filename
     destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.text.strip() == "destination /= filename"
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in augmented_context_dynamic_path_sentinels
)

augmented_literal_preserves_dynamic_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    destination /= "summary.txt"
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.text.strip() == "destination = Path(output_dir) / filename"
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in augmented_literal_preserves_dynamic_path_sentinels
)

augmented_literal_context_base_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -1,5 +1,6 @@
 from pathlib import Path
 def write_triage_note(filename, note, output_dir):
     destination = Path(output_dir) / filename
+    destination /= "summary.txt"
     destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.text.strip() == 'destination /= "summary.txt"'
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in augmented_literal_context_base_sentinels
)

paren_next_line_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = (
+        Path(output_dir) / filename
+    )
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.text.strip() == "destination = ("
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in paren_next_line_path_sentinels
)

backslash_next_line_path_diff = (
    "diff --git a/tools/path_writer.py b/tools/path_writer.py\n"
    "index 0000000..1111111 100644\n"
    "--- /dev/null\n"
    "+++ b/tools/path_writer.py\n"
    "@@ -0,0 +1,6 @@\n"
    "+from pathlib import Path\n"
    "+def write_triage_note(filename, note, output_dir):\n"
    "+    destination = \\\n"
    "+        Path(output_dir) / filename\n"
    "+    destination.write_text(note, encoding=\"utf-8\")\n"
)
backslash_next_line_path_sentinels = mod.detect_risk_sentinels(backslash_next_line_path_diff)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.text.strip() == "destination = \\"
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in backslash_next_line_path_sentinels
)

paren_next_line_join_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+import os
+def write_triage_note(filename, note, output_dir):
+    destination = (
+        os.path.join(output_dir, filename)
+    )
+    destination.write_bytes(note)
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.text.strip() == "destination = ("
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in paren_next_line_join_sentinels
)

cross_hunk_assignment_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    note = note.strip()
@@ -20,2 +20,3 @@ def write_triage_note(filename, note, output_dir):
+    destination.write_text(note, encoding="utf-8")
+    destination.write_bytes(note)
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in cross_hunk_assignment_write_sentinels
)

disconnected_cross_hunk_multiline_assignment_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,3 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = (
@@ -20,2 +20,3 @@ def write_triage_note(filename, note, output_dir):
+        Path(output_dir) / filename
+    )
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(
    item.label == mod.FILE_WRITE_PATH_LABEL
    for item in disconnected_cross_hunk_multiline_assignment_sentinels
)

cross_file_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_builder.py b/tools/path_builder.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_builder.py
@@ -0,0 +1,3 @@
+from pathlib import Path
+def build_path(output_dir, case_id):
+    destination = Path(output_dir) / f"{case_id}.txt"
diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,3 @@
+def write_path(destination, note):
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in cross_file_sentinels)
attribute_sibling_assignment_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+class Writer:
+    def write_triage_note(self, filename, note, output_dir):
+        self.destination = Path(output_dir) / filename
+        self.mode = "x"
+        self.destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in attribute_sibling_assignment_sentinels
)
wrapped_literal_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_summary(output_dir, note):
+    destination = Path(output_dir / "summary.txt")
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in wrapped_literal_path_sentinels)
long_path_assignment = "destination = " + ("a" * (mod.PYTHON_PATH_ASSIGNMENT_MAX_CHARS + 1)) + "Path(filename)"
assert mod.python_dynamic_path_target(long_path_assignment) is None
assert not mod.python_path_assignment_start("target = ")
assert mod.python_path_assignment_start("target = (")
assert mod.python_path_assignment_start("target: Path = (  ")
assert mod.python_path_assignment_start("target = \\")
assert mod.python_path_assignment_start("target: Path = \\  ")
oversized_alias_text = (
    "from pathlib import Path as P\n"
    "import os as operating_system\n"
    + ("#" * (mod.PYTHON_PATH_ASSIGNMENT_MAX_CHARS + 1))
)
assert mod.python_path_constructor_aliases(oversized_alias_text) == set()
assert mod.python_os_module_aliases(oversized_alias_text) == set()
rebound_alias_text = (
    "import os as operating_system\n"
    "import custom_storage as operating_system\n"
    "from pathlib import Path as PathAlias\n"
    "from custom_storage import Path as PathAlias\n"
)
assert mod.python_os_module_aliases(rebound_alias_text) == set()
assert mod.python_path_constructor_aliases(rebound_alias_text) == set()
assert mod.python_urllib_urlopen_call_names(
    "from urllib.request import urlopen\n"
    "from custom_storage import urlopen\n"
) == set()
assert not mod.python_line_is_known_urllib_urlopen(
    "(lambda urlopen: urlopen(target))(writer)",
    known_call_names={"urlopen"},
)
assert not mod.python_line_is_known_urllib_urlopen(
    "[urlopen(target) for urlopen in writers]",
    known_call_names={"urlopen"},
)
