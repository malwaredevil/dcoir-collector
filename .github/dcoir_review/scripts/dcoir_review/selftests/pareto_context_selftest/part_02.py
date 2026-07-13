multi_arg_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(case_id, note, output_dir):
+    destination = Path(output_dir, f"{case_id}.txt")
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in multi_arg_path_sentinels
)

variable_segment_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in variable_segment_path_sentinels
)

join_variable_segment_sentinels = mod.detect_risk_sentinels(
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
    for item in join_variable_segment_sentinels
)

path_wrapped_join_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+import os
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = os.path.join(output_dir, filename)
+    Path(destination).write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in path_wrapped_join_write_sentinels
)

qualified_path_wrapped_join_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+import os
+import pathlib
+def write_triage_note(filename, note, output_dir):
+    destination = os.path.join(output_dir, filename)
+    pathlib.Path(destination).write_bytes(note)
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in qualified_path_wrapped_join_write_sentinels
)

multiline_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,8 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(
+        output_dir,
+        filename,
+    )
+    destination.write_text(note, encoding="utf-8")
"""
)
assert mod.python_dynamic_path_target("destination = Path(\n    output_dir,\n    filename,\n)") == "destination"
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in multiline_path_sentinels
)

qualified_multiline_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+import pathlib
+def write_triage_note(filename, note, output_dir):
+    destination = pathlib.Path(
+        output_dir,
+        filename,
+    )
+    destination.write_text(note, encoding="utf-8")
"""
)
assert mod.python_dynamic_path_target("destination = pathlib.Path(\n    output_dir,\n    filename,\n)") == "destination"
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in qualified_multiline_path_sentinels
)
aliased_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path as P
+def write_triage_note(filename, note, output_dir):
+    destination = P(output_dir, filename)
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in aliased_path_sentinels
)
aliased_wrapped_path_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+import pathlib as pl
+def write_triage_note(filename, note, output_dir):
+    destination = pl.Path(output_dir, filename)
+    pl.Path(destination).write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in aliased_wrapped_path_write_sentinels
)
mod.set_python_path_alias_context({"tools/path_writer.py": {"P", "pl.Path"}})
mod.set_python_os_alias_context({"tools/path_writer.py": {"operating_system"}})
try:
    existing_alias_path_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -20,3 +20,4 @@
 def write_triage_note(filename, note, output_dir):
+    destination = P(output_dir, filename)
     destination.write_text(note, encoding="utf-8")
"""
    )
    existing_module_alias_wrapped_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -30,3 +30,4 @@
 def write_triage_note(filename, note, output_dir):
+    destination = pl.Path(output_dir, filename)
     pl.Path(destination).write_text(note, encoding="utf-8")
"""
    )
    existing_os_alias_path_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- a/tools/path_writer.py
+++ b/tools/path_writer.py
@@ -40,3 +40,4 @@
 def write_triage_note(filename, note, output_dir):
+    destination = operating_system.path.join(output_dir, filename)
     destination.write_text(note, encoding="utf-8")
"""
    )
finally:
    mod.set_python_path_alias_context({})
    mod.set_python_os_alias_context({})
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 21
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in existing_alias_path_sentinels
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 31
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in existing_module_alias_wrapped_sentinels
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 41
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in existing_os_alias_path_sentinels
)
cross_file_alias_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_builder.py b/tools/path_builder.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_builder.py
@@ -0,0 +1,2 @@
+from pathlib import Path as P
+SAFE = P("summary.txt")
diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,4 @@
+def write_triage_note(filename, note, output_dir):
+    destination = P(output_dir, filename)
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in cross_file_alias_sentinels)
cross_file_os_alias_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_builder.py b/tools/path_builder.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_builder.py
@@ -0,0 +1,4 @@
+import os as operating_system
+def build_path(filename, output_dir):
+    return operating_system.path.join(output_dir, filename)
diff --git a/tools/path_writer.py b/tools/path_writer.py
index 2222222..3333333 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,4 @@
+def write_triage_note(filename, note, output_dir):
+    destination = operating_system.path.join(output_dir, filename)
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in cross_file_os_alias_sentinels)

literal_root_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+import os
+from pathlib import Path
+def write_triage_note(filename, note):
+    destination = Path("/safe", filename)
+    backup = os.path.join("/safe", filename)
+    destination.write_text(note, encoding="utf-8")
+    backup.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in literal_root_path_sentinels
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 5
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in literal_root_path_sentinels
)

multi_variable_fstring_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_triage_note(base, filename, note):
+    destination = Path(f"{base}/{filename}")
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in multi_variable_fstring_path_sentinels
)

single_dynamic_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note):
+    destination = Path(filename)
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in single_dynamic_path_sentinels
)

chained_literal_then_variable_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / "cases" / filename
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in chained_literal_then_variable_sentinels
)

chained_variable_then_literal_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename / "note.txt"
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in chained_variable_then_literal_sentinels
)

fixture_string_sentinels = mod.detect_risk_sentinels(
    '''diff --git a/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py b/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
index 0000000..1111111 100644
--- /dev/null
+++ b/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
@@ -0,0 +1,6 @@
+# Intentionally unsafe sentinel fixture string; never executed by this selftest.
+fixture = """diff --git a/probe.py b/probe.py
++    subprocess.run(f"git add {destination}", shell=True, check=False)
+"""
'''
)
assert not any(item.label == "shell=True subprocess invocation" for item in fixture_string_sentinels)

split_fixture_marker_sentinels = mod.detect_risk_sentinels(
    '''diff --git a/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py b/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
index 0000000..1111111 100644
--- /dev/null
+++ b/.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
@@ -0,0 +1,7 @@
+# Intentionally unsafe sentinel fixture string; never executed by this selftest.
+fixture = """
+diff --git a/probe.py b/probe.py
++    subprocess.run(f"git add {destination}", shell=True, check=False)
+"""
'''
)
assert not any(item.label == "shell=True subprocess invocation" for item in split_fixture_marker_sentinels)
