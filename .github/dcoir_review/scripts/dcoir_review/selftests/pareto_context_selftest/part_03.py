real_multiline_sql_sentinels = mod.detect_risk_sentinels(
    (
        '''diff --git a/tools/query_builder.py b/tools/query_builder.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/query_builder.py
@@ -0,0 +1,5 @@
+def load_case(case_id):
+    query = f"""
+SELECT * FROM cases WHERE id = '''
        "{case_id}"
        '''  -- intentionally unsafe for sentinel testing only
+"""
'''
    )
)
assert any(
    item.path == "tools/query_builder.py"
    and item.line == 3
    and item.label == "raw SQL/query string interpolation"
    for item in real_multiline_sql_sentinels
)

comment_like_string_close_sentinels = mod.detect_risk_sentinels(
    '''diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,6 @@
+def write_triage_note(case_id, note, output_dir):
+    doc = """open text
+    # """
+    destination = Path(output_dir) / f"{case_id}.txt"
+    destination.write_text(note, encoding="utf-8")
'''
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 4
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in comment_like_string_close_sentinels
)

assert mod.detect_risk_sentinels(
    """diff --git a/tools/comment_examples.py b/tools/comment_examples.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/comment_examples.py
@@ -0,0 +1,3 @@
+# destination = Path(output_dir) / f"{case_id}.txt"
+# destination.write_text(note, encoding="utf-8")
"""
) == []
literal_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_summary(output_dir, note):
+    destination = Path(output_dir) / "summary.txt"
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in literal_path_sentinels)
literal_single_path_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,5 @@
+from pathlib import Path
+def write_summary(note):
+    destination = Path("summary.txt")
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in literal_single_path_sentinels)

legacy_path_write_labels = {
    mod.FILE_WRITE_PATH_LABEL,
    "Python request-controlled file write",
    "Python writes to a request-controlled filesystem path",
}
urlopen_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/http_client.py b/tools/http_client.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_client.py
@@ -0,0 +1,4 @@
+import urllib.request
+def fetch(req):
+    with urllib.request.urlopen(req, timeout=180) as response:
+        return response.read()
"""
)
assert not any(
    item.path == "tools/http_client.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in urlopen_sentinels
), urlopen_sentinels

shadowed_urlopen_param_diff = (
    """diff --git a/tools/http_shadow.py b/tools/http_shadow.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_shadow.py
@@ -0,0 +1,4 @@
+from urllib.request import urlopen
+def persist(urlopen, user_path):
+    return urlopen(user_path)
+"""
)
shadowed_urlopen_param_call_names = mod.python_diff_urllib_urlopen_call_names(shadowed_urlopen_param_diff).get("tools/http_shadow.py", set())
assert "urlopen" not in shadowed_urlopen_param_call_names, shadowed_urlopen_param_call_names

shadowed_qualified_urlopen_diff = (
    """diff --git a/tools/http_shadow_qualified.py b/tools/http_shadow_qualified.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_shadow_qualified.py
@@ -0,0 +1,4 @@
+import urllib.request
+urllib.request.urlopen = custom_open
+def persist(user_path):
+    return urllib.request.urlopen(user_path)
+"""
)
shadowed_qualified_urlopen_call_names = mod.python_diff_urllib_urlopen_call_names(shadowed_qualified_urlopen_diff).get(
    "tools/http_shadow_qualified.py",
    set(),
)
assert "urllib.request.urlopen" not in shadowed_qualified_urlopen_call_names, shadowed_qualified_urlopen_call_names

shadowed_alias_urlopen_diff = (
    """diff --git a/tools/http_shadow_alias.py b/tools/http_shadow_alias.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/http_shadow_alias.py
@@ -0,0 +1,4 @@
+import urllib.request as ur
+ur.urlopen = custom_open
+def persist(user_path):
+    return ur.urlopen(user_path)
+"""
)
shadowed_alias_urlopen_call_names = mod.python_diff_urllib_urlopen_call_names(shadowed_alias_urlopen_diff).get(
    "tools/http_shadow_alias.py",
    set(),
)
assert "ur.urlopen" not in shadowed_alias_urlopen_call_names, shadowed_alias_urlopen_call_names

shadowed_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/custom_open_import.py b/tools/custom_open_import.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/custom_open_import.py
@@ -0,0 +1,4 @@
+from custom_storage import open
+def persist(user_path):
+    with open(user_path, "r") as handle:
+        return handle.read()
"""
)
assert any(
    item.path == "tools/custom_open_import.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in shadowed_open_sentinels
), shadowed_open_sentinels

unsafe_builtin_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_writer.py b/tools/unsafe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_writer.py
@@ -0,0 +1,3 @@
+def persist(user_path, payload):
+    with open(user_path, "w", encoding="utf-8") as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in unsafe_builtin_open_sentinels
), unsafe_builtin_open_sentinels
unsafe_keyword_only_builtin_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_keyword_writer.py b/tools/unsafe_keyword_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_keyword_writer.py
@@ -0,0 +1,3 @@
+def persist(user_path, payload):
+    with open(file=user_path, mode="w", encoding="utf-8") as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_keyword_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in unsafe_keyword_only_builtin_open_sentinels
), unsafe_keyword_only_builtin_open_sentinels

unsafe_multiline_builtin_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_multiline_writer.py b/tools/unsafe_multiline_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_multiline_writer.py
@@ -0,0 +1,6 @@
+def persist(user_path, payload):
+    with open(
+        user_path,
+        "w",
+    ) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_multiline_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in unsafe_multiline_builtin_open_sentinels
), unsafe_multiline_builtin_open_sentinels

unsafe_multiline_context_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_multiline_context_writer.py b/tools/unsafe_multiline_context_writer.py
index 1111111..2222222 100644
--- a/tools/unsafe_multiline_context_writer.py
+++ b/tools/unsafe_multiline_context_writer.py
@@ -1,6 +1,6 @@
 def persist(user_path, payload):
     with open(
-        "safe.txt",
-        "r",
+        user_path,
+        "w",
     ) as handle:
         handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_multiline_context_writer.py"
    and item.line == 3
    and item.label in legacy_path_write_labels
    for item in unsafe_multiline_context_open_sentinels
), unsafe_multiline_context_open_sentinels

unsafe_multiline_commented_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_multiline_comment_writer.py b/tools/unsafe_multiline_comment_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_multiline_comment_writer.py
@@ -0,0 +1,7 @@
+def persist(user_path, payload):
+    with open(
+        user_path,
+        # keep utf-8 writes explicit
+        mode="w",
+    ) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_multiline_comment_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in unsafe_multiline_commented_open_sentinels
), unsafe_multiline_commented_open_sentinels

open_kwargs_expansion_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/unsafe_kwargs_writer.py b/tools/unsafe_kwargs_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/unsafe_kwargs_writer.py
@@ -0,0 +1,3 @@
+def persist(user_path, payload, options):
+    with open(file=user_path, **options) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/unsafe_kwargs_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in open_kwargs_expansion_sentinels
), open_kwargs_expansion_sentinels

default_builtin_open_read_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/default_open_reader.py b/tools/default_open_reader.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/default_open_reader.py
@@ -0,0 +1,3 @@
+def load(user_path):
+    with open(user_path) as handle:
+        return handle.read()
"""
)
assert not any(
    item.path == "tools/default_open_reader.py"
    and item.label in legacy_path_write_labels
    for item in default_builtin_open_read_sentinels
), default_builtin_open_read_sentinels

overflowed_multiline_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/overflowed_multiline_writer.py b/tools/overflowed_multiline_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/overflowed_multiline_writer.py
@@ -0,0 +1,16 @@
+def persist(user_path, payload):
+    with open(
+        user_path,
+        # preserve explicit write semantics
+        # line 1
+        # line 2
+        # line 3
+        # line 4
+        # line 5
+        # line 6
+        # line 7
+        # line 8
+        mode="w",
+    ) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/overflowed_multiline_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in overflowed_multiline_open_sentinels
), overflowed_multiline_open_sentinels

multiline_string_path_open_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/multiline_string_path_writer.py b/tools/multiline_string_path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/multiline_string_path_writer.py
@@ -0,0 +1,7 @@
+def persist(user_path, payload):
+    with open(
+        f\"\"\"{user_path}
+        .txt\"\"\",
+        "w",
+    ) as handle:
+        handle.write(payload)
"""
)
assert any(
    item.path == "tools/multiline_string_path_writer.py"
    and item.line == 2
    and item.label in legacy_path_write_labels
    for item in multiline_string_path_open_sentinels
), multiline_string_path_open_sentinels

safe_reassign_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/safe_writer.py b/tools/safe_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/safe_writer.py
@@ -0,0 +1,6 @@
+from pathlib import Path
+def write_summary(output_dir, note, case_id):
+    destination = Path(output_dir) / f"{case_id}.txt"
+    destination = Path(output_dir) / "summary.txt"
+    destination.write_text(note, encoding="utf-8")
"""
)
assert not any(item.label == mod.FILE_WRITE_PATH_LABEL for item in safe_reassign_sentinels)
self_derived_reassign_sentinels = mod.detect_risk_sentinels(
    """diff --git a/tools/path_writer.py b/tools/path_writer.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/path_writer.py
@@ -0,0 +1,7 @@
+from pathlib import Path
+def write_triage_note(filename, note, output_dir):
+    destination = Path(output_dir) / filename
+    destination = destination.resolve()
+    destination.write_text(note, encoding="utf-8")
"""
)
assert any(
    item.path == "tools/path_writer.py"
    and item.line == 3
    and item.label == mod.FILE_WRITE_PATH_LABEL
    for item in self_derived_reassign_sentinels
)
