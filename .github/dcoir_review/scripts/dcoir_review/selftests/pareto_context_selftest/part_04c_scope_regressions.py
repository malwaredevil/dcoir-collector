def _scope_context(source_lines: list[str]) -> dict[int, set[str]]:
    return mod.python_scoped_shadowed_name_roots_by_line("\n".join(source_lines))


assert_context = _scope_context(
    [
        "import urllib.request",
        "def mutator(flag):",
        "    saved = urllib.request.urlopen",
        "    urllib.request.urlopen = custom_open",
        "    assert flag",
        "    urllib.request.urlopen = saved",
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in assert_context.get(8, set()), assert_context

call_context = _scope_context(
    [
        "import urllib.request",
        "def mutator():",
        "    saved = urllib.request.urlopen",
        "    urllib.request.urlopen = custom_open",
        "    may_raise()",
        "    urllib.request.urlopen = saved",
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in call_context.get(8, set()), call_context

fixed_point_source = "\n".join(
    [
        "import urllib.request",
        "urllib.request = custom_request",
        "hostile = urllib.request",
        "urllib.request = hostile",
        "copy = urllib.request",
        "opener = copy.urlopen",
        "def persist(user_path, data):",
        '    return opener(user_path, "w").write(data)',
    ]
)
fixed_point_context = mod.python_scoped_shadowed_name_roots_by_line(fixed_point_source)
base_calls = mod.python_urllib_urlopen_call_names(fixed_point_source, preserve_shadowed=True)
assignment_calls = mod.python_assignment_urllib_urlopen_call_names(fixed_point_source, base_calls)
assert "opener" in fixed_point_context.get(8, set()), fixed_point_context
assert "opener" in assignment_calls, assignment_calls

multi_target_restore_context = _scope_context(
    [
        "import urllib.request",
        "def mutator(sink):",
        "    saved = urllib.request.urlopen",
        "    urllib.request.urlopen = custom_open",
        '    sink["key"] = urllib.request.urlopen = saved',
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in multi_target_restore_context.get(7, set()), multi_target_restore_context

safe_name_chain_restore_context = _scope_context(
    [
        "import urllib.request",
        "def mutator():",
        "    saved = urllib.request.urlopen",
        "    urllib.request.urlopen = custom_open",
        "    copied = urllib.request.urlopen = saved",
        "def fetch(request):",
        "    return urllib.request.urlopen(request)",
    ]
)
assert "urllib" not in safe_name_chain_restore_context.get(7, set()), safe_name_chain_restore_context

real_submodule_import_source = "\n".join(
    [
        "import urllib.request",
        "saved_request = urllib.request",
        "urllib.request = custom_request",
        "from urllib.request import urlopen as copied",
        "urllib.request = saved_request",
        "def fetch(request):",
        "    return copied(request)",
    ]
)
real_submodule_import_context = mod.python_scoped_shadowed_name_roots_by_line(real_submodule_import_source)
assert "copied" not in real_submodule_import_context.get(7, set()), real_submodule_import_context

direct_urlopen_mutation_import_source = "\n".join(
    [
        "import urllib.request",
        "saved_open = urllib.request.urlopen",
        "urllib.request.urlopen = custom_open",
        "from urllib.request import urlopen as copied",
        "urllib.request.urlopen = saved_open",
        "def persist(user_path, data):",
        '    return copied(user_path, "w").write(data)',
    ]
)
direct_urlopen_import_context = mod.python_scoped_shadowed_name_roots_by_line(
    direct_urlopen_mutation_import_source
)
assert "copied" in direct_urlopen_import_context.get(7, set()), direct_urlopen_import_context
