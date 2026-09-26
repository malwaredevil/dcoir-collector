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


chained_mutation_later_attribute_target_context = _scope_context(
    [
        "import urllib.request",
        "saved = urllib.request.urlopen",
        "def mutator():",
        "    urllib.request.urlopen = sink.value = custom_open",
        "    urllib.request.urlopen = saved",
        "mutator()",
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in chained_mutation_later_attribute_target_context.get(8, set()), chained_mutation_later_attribute_target_context

chained_mutation_later_name_target_context = _scope_context(
    [
        "import urllib.request",
        "saved = urllib.request.urlopen",
        "def mutator():",
        "    urllib.request.urlopen = mirror = custom_open",
        "    urllib.request.urlopen = saved",
        "mutator()",
        "def fetch(request):",
        "    return urllib.request.urlopen(request)",
    ]
)
assert "urllib" not in chained_mutation_later_name_target_context.get(8, set()), chained_mutation_later_name_target_context


benign_alias_cycle_context = _scope_context(
    [
        "import urllib.request",
        "saved = urllib.request.urlopen",
        "alias = urllib.request.urlopen",
        "def rebind_saved():",
        "    global saved",
        "    saved = alias",
        "def rebind_alias():",
        "    global alias",
        "    alias = saved",
        "rebind_saved()",
        "rebind_alias()",
        "def mutator():",
        "    global saved",
        "    urllib.request.urlopen = custom_open",
        "    urllib.request.urlopen = saved",
        "mutator()",
        "def fetch(request):",
        "    return urllib.request.urlopen(request)",
    ]
)
assert "urllib" not in benign_alias_cycle_context.get(18, set()), benign_alias_cycle_context

hostile_alias_cycle_context = _scope_context(
    [
        "import urllib.request",
        "saved = urllib.request.urlopen",
        "alias = urllib.request.urlopen",
        "def rebind_saved():",
        "    global saved",
        "    saved = alias",
        "def rebind_alias():",
        "    global alias",
        "    alias = saved",
        "def poison_alias():",
        "    global alias",
        "    alias = custom_open",
        "rebind_saved()",
        "rebind_alias()",
        "poison_alias()",
        "def mutator():",
        "    global saved",
        "    urllib.request.urlopen = custom_open",
        "    urllib.request.urlopen = saved",
        "mutator()",
        "def persist(user_path, data):",
        '    return urllib.request.urlopen(user_path, "w").write(data)',
    ]
)
assert "urllib" in hostile_alias_cycle_context.get(22, set()), hostile_alias_cycle_context
