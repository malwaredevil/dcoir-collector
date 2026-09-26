same_line_intervening_statement_context = _scope_context(
    [
        "import urllib.request",
        "saved = urllib.request.urlopen",
        "def mutator():",
        "    urllib.request.urlopen = custom_open; risky(); urllib.request.urlopen = saved",
        "try:",
        "    mutator()",
        "except Exception:",
        "    pass",
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in same_line_intervening_statement_context.get(10, set()), same_line_intervening_statement_context

same_line_adjacent_restoration_context = _scope_context(
    [
        "import urllib.request",
        "saved = urllib.request.urlopen",
        "def mutator():",
        "    urllib.request.urlopen = custom_open; urllib.request.urlopen = saved",
        "mutator()",
        "def fetch(request):",
        "    return urllib.request.urlopen(request)",
    ]
)
assert "urllib" not in same_line_adjacent_restoration_context.get(7, set()), same_line_adjacent_restoration_context


nested_nonlocal_poisoned_local_snapshot_context = _scope_context(
    [
        "import urllib.request",
        "def outer():",
        "    saved = urllib.request.urlopen",
        "    def poison():",
        "        nonlocal saved",
        "        saved = custom_open",
        "    poison()",
        "    urllib.request.urlopen = custom_open",
        "    urllib.request.urlopen = saved",
        "outer()",
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in nested_nonlocal_poisoned_local_snapshot_context.get(12, set()), nested_nonlocal_poisoned_local_snapshot_context

nested_nonlocal_same_trusted_local_snapshot_context = _scope_context(
    [
        "import urllib.request",
        "def outer():",
        "    saved = urllib.request.urlopen",
        "    def refresh():",
        "        nonlocal saved",
        "        saved = urllib.request.urlopen",
        "    refresh()",
        "    urllib.request.urlopen = custom_open",
        "    urllib.request.urlopen = saved",
        "outer()",
        "def fetch(request):",
        "    return urllib.request.urlopen(request)",
    ]
)
assert "urllib" not in nested_nonlocal_same_trusted_local_snapshot_context.get(12, set()), nested_nonlocal_same_trusted_local_snapshot_context
