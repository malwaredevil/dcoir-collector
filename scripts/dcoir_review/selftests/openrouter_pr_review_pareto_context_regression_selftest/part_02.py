
with patch.dict(
    getattr(os, "environ"),
    {
        "GITHUB_REPOSITORY": "DCOIR-Collector/dcoir-collector",
        "PR_NUMBER": "296",
        "OPENROUTER_API_KEY": "test-key-placeholder",
    },
    clear=True,
):
    assert mod.python_file_write_target('destination.write_text(note, encoding="utf-8")') == "destination"
    assert mod.python_file_write_target("Path(destination).write_bytes(note)") is None
    assert mod.python_direct_dynamic_file_write("Path(destination).write_bytes(note)")
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

    single_arg_path_slash_literal_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    destination = Path(filename) / "note.txt"
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in single_arg_path_slash_literal_sentinels
    )

    single_arg_path_joinpath_literal_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    destination = Path(filename).joinpath("note.txt")
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in single_arg_path_joinpath_literal_sentinels
    )

    direct_path_slash_literal_write_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    (Path(filename) / "note.txt").write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in direct_path_slash_literal_write_sentinels
    )

    direct_joinpath_literal_write_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    Path(filename).joinpath("note.txt").write_bytes(note)
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in direct_joinpath_literal_write_sentinels
    )

    direct_literal_path_write_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_summary(note):
+    (Path("summary.txt") / "note.txt").write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in direct_literal_path_write_sentinels)


    direct_constructor_path_write_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    Path(filename).write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in direct_constructor_path_write_sentinels
    )

    direct_qualified_constructor_path_write_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+import pathlib
+def write_triage_note(output_dir, filename, note):
+    pathlib.Path(output_dir, filename).write_bytes(note)
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in direct_qualified_constructor_path_write_sentinels
    )

    string_literal_write_text_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename):
+    destination = Path(filename) / "note.txt"
+    example = "destination.write_text(note, encoding='utf-8')"
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in string_literal_write_text_sentinels)

    comment_only_path_write_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/commented_writer.py b/tools/commented_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/commented_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    destination = Path(filename) / "note.txt"
+    # destination.write_text(note, encoding="utf-8")
+    # destination.write_bytes(note)
+    # (Path(filename) / "note.txt").write_text(note, encoding="utf-8")
+    # Path(filename).joinpath("note.txt").write_bytes(note)
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in comment_only_path_write_sentinels)

    literal_single_arg_path_slash_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_summary(note):
+    destination = Path("summary.txt") / "note.txt"
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in literal_single_arg_path_slash_sentinels)

    literal_wrapped_path_expr_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_summary(note, output_dir):
+    destination = Path(output_dir / "summary.txt")
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in literal_wrapped_path_expr_sentinels)

    joinpath_variable_segment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir).joinpath(filename)
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in joinpath_variable_segment_sentinels
    )

    qualified_joinpath_variable_segment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+import pathlib
+def write_triage_note(filename, note, output_dir):
+    destination = pathlib.Path(output_dir).joinpath(filename)
+    destination.write_bytes(note)
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in qualified_joinpath_variable_segment_sentinels
    )

    os_path_join_variable_segment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+import os
+def write_triage_note(filename, note, output_dir):
+    destination = os.path.join(output_dir, filename)
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in os_path_join_variable_segment_sentinels
    )

    aliased_os_path_join_variable_segment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+import os as operating_system
+def write_triage_note(filename, note, output_dir):
+    destination = operating_system.path.join(output_dir, filename)
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in aliased_os_path_join_variable_segment_sentinels
    )

    aliased_os_path_join_direct_receiver_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+import os as operating_system
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    Path(operating_system.path.join(output_dir, filename)).write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 4
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in aliased_os_path_join_direct_receiver_sentinels
    )

    literal_joinpath_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_summary(note, output_dir):
+    destination = Path(output_dir).joinpath("summary.txt")
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in literal_joinpath_sentinels)

    nested_scope_outer_assignment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    def normalize_note():
+        return note.strip()
+    destination.write_text(normalize_note(), encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 3
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in nested_scope_outer_assignment_sentinels
    )

    nested_same_name_assignment_sentinels = mod.detect_risk_sentinels(
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
        for item in nested_same_name_assignment_sentinels
    )

    nested_scope_inner_assignment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    def build_path():
+        destination = Path(output_dir) / filename
+        return destination
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in nested_scope_inner_assignment_sentinels)

    block_scope_assignment_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    if filename:
+        destination = Path(output_dir) / filename
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert any(
        item.path == "tools/path_writer.py"
        and item.line == 4
        and item.label == mod.FILE_WRITE_PATH_LABEL
        for item in block_scope_assignment_sentinels
    )

    unrelated_cross_hunk_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -10,2 +10,4 @@ def build_path(filename, output_dir):
+    destination = Path(output_dir) / filename
+    return destination
@@ -30,2 +32,3 @@ def write_supplied_path(destination, note):
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in unrelated_cross_hunk_sentinels)

    shadowed_parameter_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+destination = Path(output_dir) / filename
+def write_supplied_path(destination, note):
+    destination.write_text(note, encoding="utf-8")
"""
    )
    assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in shadowed_parameter_sentinels)

    print("Path-write review finding regression selftest passed")
