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

multiline_alias_urlopen_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/http_alias_client.py b/tools/http_alias_client.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_alias_client.py
@@ -0,0 +1,7 @@
+from urllib.request import urlopen
+def fetch(req):
+    with urlopen(
+        req,
+    ) as response:
+        return response.read()
"""
)
assert not any(
    item.path == "tools/http_alias_client.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in multiline_alias_urlopen_sentinels
), multiline_alias_urlopen_sentinels

original_detect_risk_sentinels = mod._original_detect_risk_sentinels


def fake_original_custom_urlopen(_diff, _max_anchors=None):
    return [
        mod.hardened.RiskSentinel(
            path="tools/custom_urlopen.py",
            line=2,
            label=mod.FILE_WRITE_PATH_LABEL,
            detail="legacy sentinel",
            text="    with client.urlopen(user_path) as handle:",
        )
    ]


mod._original_detect_risk_sentinels = fake_original_custom_urlopen
try:
    custom_urlopen_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/custom_urlopen.py b/tools/custom_urlopen.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/custom_urlopen.py
@@ -0,0 +1,3 @@
+def persist(client, user_path):
+    with client.urlopen(user_path) as handle:
+        return handle
"""
    )
finally:
    mod._original_detect_risk_sentinels = original_detect_risk_sentinels
assert any(
    item.path == "tools/custom_urlopen.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in custom_urlopen_sentinels
), custom_urlopen_sentinels

custom_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/custom_open.py b/tools/custom_open.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/custom_open.py
@@ -0,0 +1,3 @@
+def persist(client, payload):
+    with client.open("w") as handle:
+        return handle.write(payload)
"""
)
assert not any(
    item.path == "tools/custom_open.py"
    and item.label in legacy_path_write_labels
    for item in custom_open_sentinels
), custom_open_sentinels

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
