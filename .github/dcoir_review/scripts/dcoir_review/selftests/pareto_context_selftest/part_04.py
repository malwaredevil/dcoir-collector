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

os_open_multiline_write_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/os_write_multiline.py b/tools/os_write_multiline.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/os_write_multiline.py
@@ -0,0 +1,6 @@
+import os
+def persist(user_path):
+    fd = os.open(
+        user_path,
+        os.O_WRONLY | os.O_CREAT)
+    return fd
"""
)
assert any(
    item.path == "tools/os_write_multiline.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in os_open_multiline_write_sentinels
), os_open_multiline_write_sentinels

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

unsafe_multiline_assigned_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_multiline_assigned_writer.py b/tools/unsafe_multiline_assigned_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_multiline_assigned_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def persist(output_dir, filename, payload):
+    target = Path(output_dir) / filename
+    with target.open(
+        "w",
+    ) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_multiline_assigned_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in unsafe_multiline_assigned_path_open_sentinels
), unsafe_multiline_assigned_path_open_sentinels

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
