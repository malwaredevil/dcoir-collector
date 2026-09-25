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
