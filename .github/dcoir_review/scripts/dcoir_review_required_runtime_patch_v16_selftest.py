#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v16 coverage overlay."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v16 as v16
import openrouter_pr_review_pareto_context as pareto


def _s(path: str, line: int, kind: str, text: str) -> SimpleNamespace:
    title, body, _notes = v16._template_for_kind(kind)
    return SimpleNamespace(path=path, line=line, label=title, detail=body, text=text)


def test_python_path_write_sentinel_skips_test_files() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    test_path = "project_sources/collector/tools/test_build_powershell_surface_inventory_path_safety.py"
    diff = "\n".join(
        [
            "diff --git a/a.py b/b.py",
            f"+++ b/{test_path}",
            "@@ -180,0 +182,1 @@",
            '+    outside_file.write_text("ok", encoding="utf-8")',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found)


def test_python_path_write_sentinel_keeps_non_test_files() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    path = "project_sources/collector/tools/build_dcoir_collector_runtime_package.py"
    diff = "\n".join(
        [
            "diff --git a/a.py b/b.py",
            f"+++ b/{path}",
            "@@ -10,0 +11,1 @@",
            '+    Path(output_path).write_text("ok", encoding="utf-8")',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found)


def test_python_dynamic_exec_classifier_only_matches_execution_builtins() -> None:
    path = "tools/reviewer_probe.py"
    # These are the bounded false-positive cases covered by #434. Arbitrary
    # object methods named eval/exec remain context-dependent and are not
    # declared safe by this deterministic regression.
    false_positives = [
        'VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")',
        'code = compile(source, "<string>", "exec")',
    ]
    for line in false_positives:
        assert v16._line_kind(path, line) != v16.PYTHON_DYNAMIC_EXEC, line

    true_positives = [
        "result = eval(user_input)",
        "exec(payload)",
        "result = builtins.eval(user_input)",
        "__builtins__.exec(payload)",
    ]
    for line in true_positives:
        assert v16._line_kind(path, line) == v16.PYTHON_DYNAMIC_EXEC, line


def test_python_path_write_classifier_skips_read_only_open_lookalikes() -> None:
    path = "tools/path_probe.py"
    false_positives = [
        'with open(user_path, "r") as handle:',
        'with gzip.open(user_path, "r") as handle:',
        'with tarfile.open(user_path, "r") as handle:',
        "fd = os.open(user_path, os.O_RDONLY)",
        "response = urllib.request.urlopen(user_path)",
    ]
    for line in false_positives:
        assert v16._line_kind(path, line) != v11.PYTHON_PATH_WRITE, line

    true_positives = [
        'with Path(user_path).open("wb") as handle:',
        'with pathlib.Path(user_path).open("w") as handle:',
        "with open(file=user_path, **options) as handle:",
        "with Path(user_path).open(**options) as handle:",
    ]
    for line in true_positives:
        assert v16._line_kind(path, line) == v11.PYTHON_PATH_WRITE, line


def test_python_path_write_classifier_handles_oversized_os_open_shifts() -> None:
    path = "tools/path_probe.py"
    for line in (
        "fd = os.open(user_path, 1 << 1000000000)",
        "fd = os.open(user_path, 1 << -1)",
    ):
        assert v16._line_kind(path, line) == v11.PYTHON_PATH_WRITE, line


def test_patched_detector_skips_read_only_open_and_urlopen() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/http_client.py b/tools/http_client.py",
            "+++ b/tools/http_client.py",
            "@@ -0,0 +1,6 @@",
            "+import urllib.request",
            "+def fetch(user_path):",
            '+    with open(user_path, "r") as handle:',
            "+        return handle.read()",
            "+    return urllib.request.urlopen(user_path)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_does_not_readd_multiline_read_only_or_urlopen() -> None:
    class Owner:
        RiskSentinel = pareto.hardened.RiskSentinel
        detect_risk_sentinels = staticmethod(pareto.detect_risk_sentinels)

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/http_client.py b/tools/http_client.py",
            "+++ b/tools/http_client.py",
            "@@ -0,0 +1,10 @@",
            "+import urllib.request",
            "+def read_only(user_path, req):",
            "+    with open(",
            "+        user_path,",
            "+        \"r\",",
            "+    ) as handle:",
            "+        handle.read()",
            "+    return urllib.request.urlopen(",
            "+        req,",
            "+    )",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_keeps_multiline_writable_open_from_context_detector() -> None:
    class Owner:
        RiskSentinel = pareto.hardened.RiskSentinel
        detect_risk_sentinels = staticmethod(pareto.detect_risk_sentinels)

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/writer.py b/tools/writer.py",
            "+++ b/tools/writer.py",
            "@@ -0,0 +1,6 @@",
            "+def persist(user_path, payload):",
            "+    with open(",
            "+        user_path,",
            "+        \"w\",",
            "+    ) as handle:",
            "+        handle.write(payload)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_skips_urlopen_aliases_from_diff_context() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/http_client.py b/tools/http_client.py",
            "+++ b/tools/http_client.py",
            "@@ -1,4 +1,4 @@",
            " from urllib.request import urlopen",
            " def fetch(req):",
            '-    return "pending"',
            "+    return urlopen(req)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_skips_module_alias_urlopen() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/http_module_alias.py b/tools/http_module_alias.py",
            "+++ b/tools/http_module_alias.py",
            "@@ -0,0 +1,4 @@",
            "+import urllib.request as ur",
            "+def fetch(req):",
            "+    return ur.urlopen(req)",
            "+",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_urlopen_context_prunes_shadowed_urllib_bindings() -> None:
    diff = "\n".join(
        [
            "diff --git a/tools/shadowed_urlopen.py b/tools/shadowed_urlopen.py",
            "+++ b/tools/shadowed_urlopen.py",
            "@@ -0,0 +1,4 @@",
            "+import urllib.request",
            "+urllib = storage",
            "+def persist(user_path):",
            "+    return urllib.request.urlopen(user_path)",
        ]
    )
    call_names = v16._python_diff_urllib_urlopen_call_names(diff).get("tools/shadowed_urlopen.py", set())
    assert "urllib.request.urlopen" not in call_names, call_names


def test_urlopen_context_prunes_function_scoped_shadowing() -> None:
    diff = "\n".join(
        [
            "diff --git a/tools/shadowed_param_urlopen.py b/tools/shadowed_param_urlopen.py",
            "+++ b/tools/shadowed_param_urlopen.py",
            "@@ -0,0 +1,4 @@",
            "+from urllib.request import urlopen",
            "+def persist(urlopen, user_path):",
            "+    return urlopen(user_path)",
            "+",
        ]
    )
    call_names = v16._python_diff_urllib_urlopen_call_names(diff).get("tools/shadowed_param_urlopen.py", set())
    assert "urlopen" in call_names, call_names


def test_urlopen_context_prunes_qualified_module_rebinding() -> None:
    diff = "\n".join(
        [
            "diff --git a/tools/shadowed_qualified_urlopen.py b/tools/shadowed_qualified_urlopen.py",
            "+++ b/tools/shadowed_qualified_urlopen.py",
            "@@ -0,0 +1,4 @@",
            "+import urllib.request",
            "+urllib.request.urlopen = custom_open",
            "+def persist(user_path):",
            "+    return urllib.request.urlopen(user_path)",
        ]
    )
    call_names = v16._python_diff_urllib_urlopen_call_names(diff).get("tools/shadowed_qualified_urlopen.py", set())
    assert "urllib.request.urlopen" not in call_names, call_names


def test_urlopen_context_prunes_qualified_alias_rebinding() -> None:
    diff = "\n".join(
        [
            "diff --git a/tools/shadowed_alias_urlopen.py b/tools/shadowed_alias_urlopen.py",
            "+++ b/tools/shadowed_alias_urlopen.py",
            "@@ -0,0 +1,4 @@",
            "+import urllib.request as ur",
            "+ur.urlopen = custom_open",
            "+def persist(user_path):",
            "+    return ur.urlopen(user_path)",
        ]
    )
    call_names = v16._python_diff_urllib_urlopen_call_names(diff).get("tools/shadowed_alias_urlopen.py", set())
    assert "ur.urlopen" not in call_names, call_names


def test_urlopen_context_prunes_rebound_cached_aliases() -> None:
    path = "tools/rebound_cached_urlopen.py"
    v16.PYTHON_URLLIB_URLOPEN_CALL_CONTEXT[path] = {"urlopen"}
    try:
        diff = "\n".join(
            [
                f"diff --git a/{path} b/{path}",
                f"+++ b/{path}",
                "@@ -1,2 +1,3 @@",
                " from urllib.request import urlopen",
                '+urlopen = custom_open',
                '+return urlopen(req)',
            ]
        )
        call_names = v16._python_diff_urllib_urlopen_call_names(diff).get(path, set())
        assert "urlopen" not in call_names, call_names
    finally:
        v16.PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.clear()


def test_scope_local_urlopen_shadowing_stays_local() -> None:
    diff = "\n".join(
        [
            "diff --git a/tools/shadowed_param_urlopen.py b/tools/shadowed_param_urlopen.py",
            "+++ b/tools/shadowed_param_urlopen.py",
            "@@ -0,0 +1,4 @@",
            "+from urllib.request import urlopen",
            "+def persist(urlopen, user_path):",
            "+    return urlopen(user_path)",
            "+",
        ]
    )
    roots = v16._python_diff_shadowed_name_roots_by_line(diff).get("tools/shadowed_param_urlopen.py", {})
    assert "urlopen" in roots.get(3, set()), roots
    assert not v16._python_is_known_urllib_urlopen(
        "    return urlopen(user_path)",
        known_call_names={"urlopen"},
        shadowed_names={"urlopen"},
    )


def test_patched_detector_keeps_cross_function_urlopen_imports() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/http_shadow_scope.py b/tools/http_shadow_scope.py",
            "+++ b/tools/http_shadow_scope.py",
            "@@ -0,0 +1,6 @@",
            "+from urllib.request import urlopen",
            "+def helper(urlopen):",
            "+    return urlopen(\"https://example.invalid\")",
            "+def fetch(req):",
            "+    return urlopen(req)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item) == ("tools/http_shadow_scope.py", 5, v11.PYTHON_PATH_WRITE) for item in found), found


def test_python_path_write_classifier_uses_alias_context() -> None:
    path = "tools/alias_reader.py"
    v16.PYTHON_PATH_ALIAS_CONTEXT.clear()
    v16.PYTHON_PATH_ALIAS_CONTEXT[path] = {"P"}
    try:
        assert v16._line_kind(path, 'with P(user_path).open("r") as handle:') != v11.PYTHON_PATH_WRITE
    finally:
        v16.PYTHON_PATH_ALIAS_CONTEXT.clear()


def test_python_path_write_classifier_uses_os_alias_context() -> None:
    path = "tools/os_alias_reader.py"
    v16.PYTHON_OS_ALIAS_CONTEXT.clear()
    v16.PYTHON_OS_ALIAS_CONTEXT[path] = {"operating_system"}
    try:
        assert v16._line_kind(path, "fd = operating_system.open(user_path, operating_system.O_RDONLY)") != v11.PYTHON_PATH_WRITE
    finally:
        v16.PYTHON_OS_ALIAS_CONTEXT.clear()


def test_patched_detector_keeps_shadowed_os_module_reads_conservative() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/os_shadow.py b/tools/os_shadow.py",
            "+++ b/tools/os_shadow.py",
            "@@ -0,0 +1,4 @@",
            "+import os",
            "+os = storage",
            "+def persist(user_path):",
            "+    return os.open(user_path, os.O_RDONLY)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item) == ("tools/os_shadow.py", 4, v11.PYTHON_PATH_WRITE) for item in found), found


def test_patched_detector_consumes_owner_alias_context() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace
        PYTHON_PATH_ALIAS_CONTEXT = {"tools/ctx_alias_reader.py": {"P"}}

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/ctx_alias_reader.py b/tools/ctx_alias_reader.py",
            "+++ b/tools/ctx_alias_reader.py",
            "@@ -3,0 +4,1 @@",
            '+with P(user_path).open("r") as handle:',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_derives_path_and_os_aliases_from_diff() -> None:
    class Owner:
        RiskSentinel = pareto.hardened.RiskSentinel
        detect_risk_sentinels = staticmethod(pareto.detect_risk_sentinels)

    owner = Owner()
    v16._patch_detect(owner)
    safe_diff = "\n".join(
        [
            "diff --git a/tools/alias_reader.py b/tools/alias_reader.py",
            "+++ b/tools/alias_reader.py",
            "@@ -0,0 +1,6 @@",
            "+from pathlib import Path as P",
            "+import os as operating_system",
            "+def load(user_path):",
            "+    with P(user_path).open(\"r\") as handle:",
            "+        fd = operating_system.open(user_path, operating_system.O_RDONLY)",
            "+        return handle.read(), fd",
        ]
    )
    found = owner.detect_risk_sentinels(safe_diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found

    hostile_diff = "\n".join(
        [
            "diff --git a/tools/alias_writer.py b/tools/alias_writer.py",
            "+++ b/tools/alias_writer.py",
            "@@ -0,0 +1,6 @@",
            "+from pathlib import Path as P",
            "+import os as operating_system",
            "+def save(user_path, payload):",
            "+    with P(user_path).open(\"w\") as handle:",
            "+        handle.write(payload)",
            "+    return operating_system.open(user_path, operating_system.O_WRONLY)",
        ]
    )
    found = owner.detect_risk_sentinels(hostile_diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_keeps_unknown_custom_open_calls() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/custom_open.py b/tools/custom_open.py",
            "+++ b/tools/custom_open.py",
            "@@ -0,0 +1,3 @@",
            "+def persist(storage, user_path, payload):",
            '+    with storage.open(user_path, "w") as handle:',
            "+        handle.write(payload)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_keeps_shadowed_read_only_bare_open_calls() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/custom_open_import.py b/tools/custom_open_import.py",
            "+++ b/tools/custom_open_import.py",
            "@@ -0,0 +1,4 @@",
            "+from custom_storage import open",
            "+def persist(user_path):",
            '+    with open(user_path, "r") as handle:',
            "+        return handle.read()",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_keeps_unknown_kwargs_open_calls() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/kwargs_open.py b/tools/kwargs_open.py",
            "+++ b/tools/kwargs_open.py",
            "@@ -0,0 +1,5 @@",
            "+from pathlib import Path",
            "+def persist(user_path, options):",
            "+    with open(file=user_path, **options) as handle:",
            "+        with Path(user_path).open(**options) as wrapped_handle:",
            "+            return handle, wrapped_handle",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item) == ("tools/kwargs_open.py", 3, v11.PYTHON_PATH_WRITE) for item in found), found
    assert any(v16._sentinel_key(item) == ("tools/kwargs_open.py", 4, v11.PYTHON_PATH_WRITE) for item in found), found


def test_patched_detector_consumes_owner_shadowed_name_context() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace
        PYTHON_SHADOWED_NAME_CONTEXT = {"tools/custom_open_import.py": {"open", "persist", "handle"}}

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            "diff --git a/tools/custom_open_import.py b/tools/custom_open_import.py",
            "+++ b/tools/custom_open_import.py",
            "@@ -2,3 +2,3 @@",
            " def persist(user_path):",
            '-    return "pending"',
            '+    with open(user_path, "r") as handle:',
            '+        return handle.read()',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_patched_detector_consumes_full_head_scoped_urlopen_shadow_context() -> None:
    path = "tools/head_scoped_urlopen.py"
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "",
            "def persist(urlopen, user_path, data):",
            '    return "pending"',
            "",
            "def fetch(req):",
            "    return urlopen(req)",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(4, set()), scoped_context
    assert "urlopen" not in scoped_context.get(7, set()), scoped_context

    class Owner:
        RiskSentinel = SimpleNamespace
        PYTHON_URLLIB_URLOPEN_CALL_CONTEXT = {path: {"urlopen"}}
        PYTHON_SHADOWED_NAME_CONTEXT = {path: {"persist", "fetch", "urlopen", "user_path", "data", "req"}}
        PYTHON_SCOPED_SHADOWED_NAME_CONTEXT = {path: scoped_context}

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return []

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            f"+++ b/{path}",
            "@@ -4 +4 @@ def persist(urlopen, user_path, data):",
            '-    return "pending"',
            '+    return urlopen(user_path, "w").write(data)',
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item) == (path, 4, v11.PYTHON_PATH_WRITE) for item in found), found


def test_full_head_scoped_urlopen_shadowing_does_not_leak_across_functions() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "",
            "def persist(urlopen, user_path, data):",
            '    return urlopen(user_path, "w").write(data)',
            "",
            "def fetch(req):",
            "    return urlopen(req)",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert not v16._python_is_known_urllib_urlopen(
        '    return urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(4, set()),
    )
    assert v16._python_is_known_urllib_urlopen(
        "    return urlopen(req)",
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(7, set()),
    )


def test_full_head_nested_scope_shadowing_is_preserved() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def outer(flag):",
            "    if flag:",
            "        def persist(urlopen, user_path, data):",
            '            return urlopen(user_path, "w").write(data)',
            "        return persist",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(5, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '            return urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_trusted_inner_import_overrides_outer_shadow() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def outer(urlopen):",
            "    if urlopen:",
            "        def fetch(req):",
            "            from urllib.request import urlopen",
            "            return urlopen(req)",
            "        return fetch",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" not in scoped_context.get(6, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "            return urlopen(req)",
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(6, set()),
    )


def test_full_head_global_custom_rebind_remains_shadowed() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def persist(user_path, data):",
            "    global urlopen",
            "    urlopen = custom_open",
            '    return urlopen(user_path, "w").write(data)',
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(5, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    return urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_global_declaration_without_rebind_uses_module_import() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def outer(urlopen):",
            "    def fetch(req):",
            "        global urlopen",
            "        return urlopen(req)",
            "    return fetch",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" not in scoped_context.get(5, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "        return urlopen(req)",
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_global_custom_rebind_propagates_cross_function() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def rebind():",
            "    global urlopen",
            "    urlopen = custom_open",
            "def persist(user_path, data):",
            '    return urlopen(user_path, "w").write(data)',
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(6, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    return urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(6, set()),
    )


def test_full_head_dotted_trusted_import_binds_root_name() -> None:
    source = "\n".join(
        [
            "import urllib.request",
            "def outer(urllib):",
            "    def fetch(req):",
            "        import urllib.request",
            "        return urllib.request.urlopen(req)",
            "    return fetch",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urllib" not in scoped_context.get(5, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "        return urllib.request.urlopen(req)",
        known_call_names={"urllib.request.urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_global_rebind_remains_shadowed_in_global_consumer() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def rebind():",
            "    global urlopen",
            "    urlopen = custom_open",
            "def persist(user_path, data):",
            "    global urlopen",
            '    return urlopen(user_path, "w").write(data)',
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(7, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    return urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(7, set()),
    )


def test_full_head_nonlocal_rebind_propagates_to_sibling_scope() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def outer():",
            "    from urllib.request import urlopen",
            "    def rebind():",
            "        nonlocal urlopen",
            "        urlopen = custom_open",
            "    def persist(user_path, data):",
            '        return urlopen(user_path, "w").write(data)',
            "    return rebind, persist",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(8, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '        return urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(8, set()),
    )


def test_full_head_nonlocal_reference_without_rebind_stays_trusted() -> None:
    source = "\n".join(
        [
            "def outer():",
            "    from urllib.request import urlopen",
            "    def fetch(req):",
            "        nonlocal urlopen",
            "        return urlopen(req)",
            "    return fetch",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" not in scoped_context.get(5, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "        return urlopen(req)",
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_qualified_urlopen_mutation_propagates_to_sibling_scope() -> None:
    source = "\n".join(
        [
            "import urllib.request",
            "def rebind():",
            "    urllib.request.urlopen = custom_open",
            "def persist(user_path, data):",
            '    return urllib.request.urlopen(user_path, "w").write(data)',
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urllib" in scoped_context.get(5, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    return urllib.request.urlopen(user_path, "w").write(data)',
        known_call_names={"urllib.request.urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_qualified_mutation_survives_sibling_trusted_reimport() -> None:
    source = "\n".join(
        [
            "import urllib.request",
            "def rebind():",
            "    urllib.request.urlopen = custom_open",
            "def persist(user_path, data):",
            "    from urllib import request as req",
            '    return req.urlopen(user_path, "w").write(data)',
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "req" in scoped_context.get(6, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    return req.urlopen(user_path, "w").write(data)',
        known_call_names={"req.urlopen"},
        shadowed_names=scoped_context.get(6, set()),
    )


def test_full_head_unrelated_urllib_attribute_mutation_stays_trusted() -> None:
    source = "\n".join(
        [
            "import urllib.request",
            "def mutate():",
            "    urllib.foo = custom_value",
            "def fetch(req):",
            "    return urllib.request.urlopen(req)",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urllib" not in scoped_context.get(3, set()), scoped_context
    assert "urllib" not in scoped_context.get(5, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "    return urllib.request.urlopen(req)",
        known_call_names={"urllib.request.urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_unrelated_attribute_mutation_does_not_shadow_urllib() -> None:
    source = "\n".join(
        [
            "import urllib.request",
            "def mutate(client):",
            "    client.request = custom_request",
            "def fetch(req):",
            "    return urllib.request.urlopen(req)",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urllib" not in scoped_context.get(5, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "    return urllib.request.urlopen(req)",
        known_call_names={"urllib.request.urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_default_expression_uses_enclosing_shadow_state() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def outer(urlopen, user_path, data):",
            '    def persist(value=urlopen(user_path, "w").write(data)):',
            "        from urllib.request import urlopen",
            "        return urlopen(value)",
            "    return persist",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(3, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    def persist(value=urlopen(user_path, "w").write(data)):',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(3, set()),
    )
    assert "urlopen" not in scoped_context.get(5, set()), scoped_context
    assert v16._python_is_known_urllib_urlopen(
        "        return urlopen(value)",
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(5, set()),
    )


def test_full_head_decorator_expression_uses_enclosing_shadow_state() -> None:
    source = "\n".join(
        [
            "from urllib.request import urlopen",
            "def outer(urlopen, user_path, data):",
            '    @urlopen(user_path, "w").write(data)',
            "    def persist(value):",
            "        from urllib.request import urlopen",
            "        return urlopen(value)",
            "    return persist",
        ]
    )
    scoped_context = pareto.python_scoped_shadowed_name_roots_by_line(source)
    assert "urlopen" in scoped_context.get(3, set()), scoped_context
    assert not v16._python_is_known_urllib_urlopen(
        '    @urlopen(user_path, "w").write(data)',
        known_call_names={"urlopen"},
        shadowed_names=scoped_context.get(3, set()),
    )
    assert "urlopen" not in scoped_context.get(6, set()), scoped_context


def test_pareto_shadowed_name_context_registry_is_defined() -> None:
    pareto.set_python_shadowed_name_context({"tools/custom_open_import.py": {"open"}})
    assert pareto.PYTHON_SHADOWED_NAME_CONTEXT == {"tools/custom_open_import.py": {"open"}}
    pareto.set_python_shadowed_name_context({})
    assert pareto.PYTHON_SHADOWED_NAME_CONTEXT == {}


def test_patched_detector_consumes_sentinel_owner_urlopen_context() -> None:
    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return [_s("tools/http_head_alias_client.py", 2, v11.PYTHON_PATH_WRITE, "    return urlopen(req)")]

    class SentinelOwner:
        PYTHON_URLLIB_URLOPEN_CALL_CONTEXT = {"tools/http_head_alias_client.py": {"urlopen"}}

    owner = Owner()
    v16._patch_detect(owner, SentinelOwner())
    diff = "\n".join(
        [
            "diff --git a/tools/http_head_alias_client.py b/tools/http_head_alias_client.py",
            "+++ b/tools/http_head_alias_client.py",
            "@@ -2,2 +2,2 @@",
            " def fetch(req):",
            '-    return "pending"',
            "+    return urlopen(req)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert not any(v16._sentinel_key(item)[2] == v11.PYTHON_PATH_WRITE for item in found), found


def test_core_semantics_keeps_stable_finding_family_dependency() -> None:
    from dcoir_review import finding_family

    v16._patch_core_semantics()
    assert finding_family.FAMILY_ORDER == ("yaml", "python", "powershell", "other", "typescript")


def test_patched_detector_preserves_mixed_urlopen_and_file_write() -> None:
    path = "tools/mixed_url_write.py"
    statement = '    urllib.request.urlopen(url).read(); open(user_path, "w").write(data)'

    class Owner:
        RiskSentinel = SimpleNamespace

        @staticmethod
        def detect_risk_sentinels(_diff, *_args, **_kwargs):
            return [_s(path, 3, v11.PYTHON_PATH_WRITE, statement)]

    owner = Owner()
    v16._patch_detect(owner)
    diff = "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            f"+++ b/{path}",
            "@@ -0,0 +1,3 @@",
            "+import urllib.request",
            "+def persist(url, user_path, data):",
            "+    urllib.request.urlopen(url).read(); open(user_path, \"w\").write(data)",
        ]
    )
    found = owner.detect_risk_sentinels(diff)
    assert any(v16._sentinel_key(item) == (path, 3, v11.PYTHON_PATH_WRITE) for item in found), found


def main() -> None:
    workflow = ".github/workflows/dcoir-review-v16-probe.yml"
    py = ".github/chatgpt_staging/dcoir_review_probe/v16_probe.py"
    ps = ".github/chatgpt_staging/dcoir_review_probe/v16_probe.ps1"
    ts = ".github/chatgpt_staging/dcoir_review_probe/v16_optional.ts"
    k8s = ".github/chatgpt_staging/dcoir_review_probe/v16_bonus_k8s.yml"

    ps_plaintext_secure_line = "".join((
        "$sec",
        "ret = ConvertTo-SecureString $Password -AsPlainText -Force",
    ))

    risk_sentinels = [
        _s(workflow, 3, v4.YAML_PULL_REQUEST_TARGET, "  pull_request_target:"),
        _s(workflow, 5, v4.YAML_BROAD_WRITE, "  contents: write"),
        _s(workflow, 13, v4.YAML_UNTRUSTED_CHECKOUT, "          ref: ${{ github.event.pull_request.head.sha }}"),
        _s(workflow, 16, v4.YAML_METADATA_SHELL, '          bash -lc "${{ github.event.pull_request.body }}"'),
        _s(workflow, 19, v10.YAML_TOKEN_TO_PR_URL, '          curl -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" "${{ github.event.pull_request.title }}"'),
        _s(workflow, 22, v4.YAML_SHELL_PIPE, "          curl -fsSL https://downloads.example.invalid/install.sh | sh"),
        _s(workflow, 25, v4.YAML_METADATA_SHELL, '          sh -c "${{ github.event.pull_request.labels[0].name }}"'),
        _s(py, 12, v9.PYTHON_PICKLE_LOAD, "    return pickle.loads(raw)"),
        _s(py, 16, v5.PYTHON_YAML_LOAD, "    return yaml.load(blob, Loader=yaml.Loader)"),
        _s(py, 20, v16.PYTHON_DYNAMIC_EXEC, "    return eval(rule_text)"),
        _s(py, 24, v5.PYTHON_SHELL_EXEC, "    return subprocess.run(command, shell=True, check=True)"),
        _s(py, 29, v11.PYTHON_ARCHIVE_EXTRACT, "        archive.extractall(destination)"),
        _s(py, 34, v5.PYTHON_ENV_TOKEN, '    return requests.get(callback_url, headers={"Authorization": f"Bearer {token}"})'),
        _s(py, 38, v11.PYTHON_PATH_WRITE, "    Path(target_name).write_text(content)"),
        _s(ps, 9, v13.PS_PLAINTEXT_SECURE_STRING, ps_plaintext_secure_line),
        _s(ps, 13, v4.PS_ACL, "Set-Acl -Path $OutputPath -AclObject $acl"),
        _s(ps, 14, v4.PS_PROCESS_LAUNCH, "Start-Process -FilePath $ToolPath -ArgumentList $Arguments -Wait"),
        _s(ps, 15, v9.PS_DYNAMIC_EXEC, "Invoke-Expression $Command"),
        _s(ps, 16, v5.PS_ENV_TOKEN, 'Invoke-WebRequest -Uri $Callback -Headers @{ Authorization = "Bearer $env:DCOIR_TOKEN" }'),
        _s(ps, 17, v13.PS_RUN_KEY_PERSISTENCE, 'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name Probe -Value $ToolPath'),
        _s(ts, 4, v13.TS_INNER_HTML, "target.innerHTML = profile.html;"),
        _s(k8s, 7, v13.K8S_HOST_PATH, "hostPath:"),
    ]

    selected, metadata = v16._select_once(SimpleNamespace(), [], risk_sentinels, SimpleNamespace(max_inline_comments=12))
    assert len(selected) <= 12
    assert not metadata["omitted_required_sentinels"], metadata["omitted_required_sentinels"]
    assert metadata["aggregate_covered_sentinels"], metadata
    assert metadata["kubernetes_policy"] == "optional_bonus_only"

    covered = set()
    for item in selected:
        covered.update(v16._coverage_from_finding(item))

    required = {v16._coverage_key(v16._sentinel_key(item)) for item in risk_sentinels if v16._sentinel_key(item)[2] in v16.CORE_REQUIRED_KINDS}
    assert required <= covered
    assert v16._coverage_key((workflow, 19, v10.YAML_TOKEN_TO_PR_URL)) in covered
    assert v16._coverage_key((workflow, 25, v4.YAML_METADATA_SHELL)) in covered
    assert v16._coverage_key((py, 20, v16.PYTHON_DYNAMIC_EXEC)) in covered
    assert v16._coverage_key((ps, 17, v13.PS_RUN_KEY_PERSISTENCE)) in covered
    assert all(not v16._postable_key(item)[2].startswith("k8s_") for item in selected)

    rendered = "\n\n".join(v16._render_comment(item) for item in selected)
    assert "Reviewed with" not in rendered
    assert "```bash" in rendered

    test_python_path_write_sentinel_skips_test_files()
    test_python_path_write_sentinel_keeps_non_test_files()
    test_python_dynamic_exec_classifier_only_matches_execution_builtins()
    test_python_path_write_classifier_skips_read_only_open_lookalikes()
    test_python_path_write_classifier_handles_oversized_os_open_shifts()
    test_patched_detector_skips_read_only_open_and_urlopen()
    test_patched_detector_preserves_mixed_urlopen_and_file_write()
    test_patched_detector_skips_urlopen_aliases_from_diff_context()
    test_patched_detector_skips_module_alias_urlopen()
    test_urlopen_context_prunes_shadowed_urllib_bindings()
    test_urlopen_context_prunes_function_scoped_shadowing()
    test_urlopen_context_prunes_qualified_module_rebinding()
    test_urlopen_context_prunes_qualified_alias_rebinding()
    test_urlopen_context_prunes_rebound_cached_aliases()
    test_scope_local_urlopen_shadowing_stays_local()
    test_patched_detector_keeps_cross_function_urlopen_imports()
    test_python_path_write_classifier_uses_alias_context()
    test_python_path_write_classifier_uses_os_alias_context()
    test_patched_detector_keeps_shadowed_os_module_reads_conservative()
    test_patched_detector_consumes_owner_alias_context()
    test_patched_detector_derives_path_and_os_aliases_from_diff()
    test_patched_detector_keeps_unknown_custom_open_calls()
    test_patched_detector_keeps_shadowed_read_only_bare_open_calls()
    test_patched_detector_keeps_unknown_kwargs_open_calls()
    test_patched_detector_consumes_owner_shadowed_name_context()
    test_patched_detector_consumes_full_head_scoped_urlopen_shadow_context()
    test_full_head_scoped_urlopen_shadowing_does_not_leak_across_functions()
    test_full_head_nested_scope_shadowing_is_preserved()
    test_full_head_trusted_inner_import_overrides_outer_shadow()
    test_full_head_global_custom_rebind_remains_shadowed()
    test_full_head_global_declaration_without_rebind_uses_module_import()
    test_full_head_global_custom_rebind_propagates_cross_function()
    test_full_head_dotted_trusted_import_binds_root_name()
    test_full_head_global_rebind_remains_shadowed_in_global_consumer()
    test_full_head_nonlocal_rebind_propagates_to_sibling_scope()
    test_full_head_nonlocal_reference_without_rebind_stays_trusted()
    test_full_head_qualified_urlopen_mutation_propagates_to_sibling_scope()
    test_full_head_qualified_mutation_survives_sibling_trusted_reimport()
    test_full_head_unrelated_urllib_attribute_mutation_stays_trusted()
    test_full_head_unrelated_attribute_mutation_does_not_shadow_urllib()
    test_full_head_default_expression_uses_enclosing_shadow_state()
    test_full_head_decorator_expression_uses_enclosing_shadow_state()
    test_pareto_shadowed_name_context_registry_is_defined()
    test_patched_detector_consumes_sentinel_owner_urlopen_context()
    test_core_semantics_keeps_stable_finding_family_dependency()

    print("dcoir_review_required_runtime_patch_v16_selftest passed")


if __name__ == "__main__":
    main()
