
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
