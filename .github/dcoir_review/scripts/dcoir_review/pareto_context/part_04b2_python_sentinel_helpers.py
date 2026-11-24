def python_diff_shadowed_name_roots_by_line(diff: str) -> dict[str, dict[int, set[str]]]:
    shadowed_names_by_path: dict[str, dict[int, set[str]]] = {}
    shadowed_bindings: dict[str, list[int]] = {}
    scope_stack: list[PythonScope] = []
    next_scope_id = 0
    current_path = ""
    current_hunk = 0

    def push_shadowed_root(name: str, scope_id: int) -> None:
        root = name.split(".", 1)[0]
        bindings = shadowed_bindings.setdefault(root, [])
        while bindings and bindings[-1] == scope_id:
            bindings.pop()
        bindings.append(scope_id)

    def visible_shadowed_roots() -> set[str]:
        return {name for name, bindings in shadowed_bindings.items() if bindings}

    def prune_shadowed_bindings(active_scope_ids: set[int]) -> None:
        for name, bindings in list(shadowed_bindings.items()):
            while bindings and bindings[-1] not in active_scope_ids:
                bindings.pop()
            if not bindings:
                shadowed_bindings.pop(name, None)

    for diff_line in iter_python_diff_lines_with_context(diff):
        if diff_line.path != current_path:
            current_path = diff_line.path
            current_hunk = diff_line.hunk
            shadowed_bindings.clear()
            scope_stack.clear()
            next_scope_id = seed_python_hunk_scope(scope_stack, diff_line.hunk_context, next_scope_id)
        elif diff_line.hunk != current_hunk:
            if not trim_python_scope_stack_to_hunk(scope_stack, diff_line.hunk_context):
                shadowed_bindings.clear()
                scope_stack.clear()
                next_scope_id = seed_python_hunk_scope(scope_stack, diff_line.hunk_context, next_scope_id)
            current_hunk = diff_line.hunk
        diff_line_indent = python_code_line_indent(diff_line.text)
        pop_python_scopes_for_indent(scope_stack, diff_line_indent)
        prune_shadowed_bindings(active_python_scope_ids(scope_stack))
        current_scope_id = current_python_scope_id(scope_stack)
        definition_name = python_scope_definition_name(diff_line.text)
        if definition_name:
            push_shadowed_root(definition_name, current_scope_id)
        if python_is_scope_boundary(diff_line.text):
            next_scope_id += 1
            scope_stack.append(PythonScope(diff_line_indent or 0, python_scope_key(diff_line.text), next_scope_id))
            current_scope_id = current_python_scope_id(scope_stack)
            scope_shadowed_names = python_scope_boundary_shadowed_names(diff_line.text)
            if definition_name:
                scope_shadowed_names.discard(definition_name)
            for shadowed_name in scope_shadowed_names:
                push_shadowed_root(shadowed_name, current_scope_id)
        for shadowed_name in python_line_shadowed_name_roots(diff_line.text):
            push_shadowed_root(shadowed_name, current_scope_id)
        shadowed_names_by_path.setdefault(diff_line.path, {})[diff_line.line] = visible_shadowed_roots()
    return shadowed_names_by_path


def python_diff_statement_text_for_anchor(diff: str, path: str, line: int, fallback_text: str) -> str:
    matching_lines = [diff_line for diff_line in iter_python_diff_lines_with_context(diff) if diff_line.path == path]
    for index, diff_line in enumerate(matching_lines):
        if diff_line.line != line:
            continue
        statement_lines = [diff_line.text]
        statement = diff_line.text
        if python_statement_is_complete(statement):
            return statement
        for next_line in matching_lines[index + 1:]:
            if next_line.hunk != diff_line.hunk:
                break
            statement_lines.append(next_line.text)
            statement = "\n".join(statement_lines)
            if python_statement_is_complete(statement) or len(statement_lines) >= 12:
                return statement
        return statement
    return fallback_text


def python_has_known_file_open_call(
    text: str,
    path_constructor_names: set[str],
    os_module_names: set[str],
) -> bool:
    known_read_mode_open_calls = {"bz2.open", "gzip.open", "lzma.open", "tarfile.open"}
    module = python_parse_diff_line(text)
    if module is None:
        return False
    os_open_names = {f"{name}.open" for name in os_module_names}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        call_name = python_call_name(node.func)
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            return True
        if call_name in known_read_mode_open_calls or call_name in os_open_names:
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and python_is_proven_path_receiver(node.func.value)
        ):
            return True
    return False


def python_line_is_known_urllib_urlopen(
    text: str,
    allow_imported_alias: bool = False,
    known_call_names: set[str] | None = None,
    shadowed_names: set[str] | None = None,
) -> bool:
    call_names = set(known_call_names or ())
    if allow_imported_alias:
        call_names.add("urlopen")
    if not call_names:
        return False
    module = python_parse_diff_line(text)
    active_shadowed_names = set(shadowed_names or ())
    if module is not None:
        active_shadowed_names.update(python_line_shadowed_name_roots(text))
    call_names = python_prune_shadowed_urlopen_call_names(
        call_names,
        active_shadowed_names,
    )
    if not call_names:
        return False
    if module is not None:
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and python_call_name(node.func) in call_names:
                return True
        return False
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in sorted(call_names, key=len, reverse=True)) + r")\s*\("
    return bool(re.search(pattern, text))
