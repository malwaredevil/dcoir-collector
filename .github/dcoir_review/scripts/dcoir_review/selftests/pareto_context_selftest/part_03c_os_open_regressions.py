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

module_alias_urlopen_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/http_module_alias_client.py b/tools/http_module_alias_client.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_module_alias_client.py
@@ -0,0 +1,4 @@
+import urllib.request as ur
+def fetch(req):
+    with ur.urlopen(req) as response:
+        return response.read()
"""
)
assert not any(
    item.path == "tools/http_module_alias_client.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in module_alias_urlopen_sentinels
), module_alias_urlopen_sentinels

mod.set_python_urllib_urlopen_call_context(
    {"tools/http_head_alias_client.py": {"urllib.request.urlopen", "urllib.urlopen", "urlopen"}}
)
try:
    head_context_alias_urlopen_sentinels = mod.detect_risk_sentinels(
        """diff --git a/tools/http_head_alias_client.py b/tools/http_head_alias_client.py
index 0000000..1111111 100644
--- a/tools/http_head_alias_client.py
+++ b/tools/http_head_alias_client.py
@@ -2,2 +2,2 @@
 def fetch(req):
-    return "pending"
+    return urlopen(req)
"""
    )
finally:
    mod.set_python_urllib_urlopen_call_context({})
assert not any(
    item.path == "tools/http_head_alias_client.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in head_context_alias_urlopen_sentinels
), head_context_alias_urlopen_sentinels

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

assert not mod.python_line_has_explicit_file_write_call(
    "with open(file=user_path, **options) as handle:",
    local_int_bindings={},
)
assert not mod.python_line_has_explicit_file_write_call(
    "with ur.urlopen(",
    known_call_names={"urllib.request.urlopen", "urllib.urlopen", "ur.urlopen"},
)
assert not mod.python_line_has_explicit_file_write_call('mode = "r"; open(user_path, mode)')
assert mod.python_line_has_explicit_file_write_call('mode = "w"; open(user_path, mode)')

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
