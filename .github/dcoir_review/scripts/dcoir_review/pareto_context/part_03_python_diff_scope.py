def detect_python_dynamic_exec_sentinels(diff: str) -> list[hardened.RiskSentinel]:
    sentinels: list[hardened.RiskSentinel] = []
    for diff_line in iter_python_diff_lines_with_context(diff):
        if not diff_line.is_added or diff_line.inside_multiline_string:
            continue
        if hardened.is_comment_only_added_line(diff_line.path, diff_line.text):
            continue
        call_name = python_dynamic_exec_call_name(diff_line.text)
        if not call_name:
            continue
        sentinels.append(
            hardened.RiskSentinel(
                path=diff_line.path,
                line=diff_line.line,
                label=PYTHON_DYNAMIC_EXEC_LABEL,
                detail=(
                    f"{call_name} can execute caller-controlled Python code; "
                    "replace dynamic evaluation with literal parsing, a constrained parser, or an explicit allowlist"
                ),
                text=diff_line.text,
            )
        )
    return sentinels


def python_is_scope_boundary(text: str) -> bool:
    return bool(PYTHON_SCOPE_BOUNDARY_RE.match(text))


def python_scope_key(text: str) -> str:
    if not python_is_scope_boundary(text):
        return ""
    signature = text.strip().split("#", 1)[0].rstrip(":").strip()
    return re.sub(r"\s+", " ", signature)


def python_hunk_context_scope(raw_line: str) -> str:
    match = PYTHON_HUNK_CONTEXT_RE.match(raw_line)
    if not match:
        return ""
    return python_scope_key(match.group("context"))


def current_python_scope_id(scope_stack: list[PythonScope]) -> int:
    return scope_stack[-1].scope_id if scope_stack else 0


def active_python_scope_ids(scope_stack: list[PythonScope]) -> set[int]:
    return {0, *(scope.scope_id for scope in scope_stack)}


def pop_python_scopes_for_indent(scope_stack: list[PythonScope], indent: int | None) -> None:
    if indent is None:
        return
    while scope_stack and indent <= scope_stack[-1].indent:
        scope_stack.pop()


def seed_python_hunk_scope(scope_stack: list[PythonScope], hunk_context: str, next_scope_id: int) -> int:
    if not hunk_context or any(scope.key == hunk_context for scope in scope_stack):
        return next_scope_id
    next_scope_id += 1
    scope_stack.append(PythonScope(0, hunk_context, next_scope_id))
    return next_scope_id


def trim_python_scope_stack_to_hunk(scope_stack: list[PythonScope], hunk_context: str) -> bool:
    if not hunk_context:
        return False
    for index in range(len(scope_stack) - 1, -1, -1):
        if scope_stack[index].key == hunk_context:
            del scope_stack[index + 1 :]
            return True
    return False


def python_code_line_indent(text: str) -> int | None:
    stripped = text.strip()
    if not stripped or stripped.startswith("#"):
        return None
    return len(text) - len(text.lstrip(" \t"))


def prune_assigned_paths_for_active_scopes(assigned_paths: dict[str, list[PythonTrackedPath]], active_scope_ids: set[int]) -> None:
    for target, assignments in list(assigned_paths.items()):
        while assignments and assignments[-1].scope_id not in active_scope_ids:
            assignments.pop()
        if not assignments:
            assigned_paths.pop(target, None)


def python_scope_boundary_shadowed_names(text: str) -> set[str]:
    stripped = text.lstrip()
    if not re.match(r"^(?:async\s+def|def|class)\s+", stripped):
        return set()
    source = f"{stripped}\n    pass\n" if stripped.rstrip().endswith(":") else stripped
    try:
        module = ast.parse(source)
    except SyntaxError:
        return set()
    if not module.body:
        return set()
    statement = module.body[0]
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names = {arg.arg for arg in [*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs]}
        if statement.args.vararg:
            names.add(statement.args.vararg.arg)
        if statement.args.kwarg:
            names.add(statement.args.kwarg.arg)
        return names
    if isinstance(statement, ast.ClassDef):
        return {statement.name}
    return set()


def push_assigned_path(
    assigned_paths: dict[str, list[PythonTrackedPath]],
    target: str,
    assignment: PythonDiffLine,
    scope_id: int,
) -> None:
    indent = python_code_line_indent(assignment.text) or 0
    assignments = assigned_paths.setdefault(target, [])
    while assignments and assignments[-1].scope_id == scope_id:
        assignments.pop()
    assignments.append(PythonTrackedPath(assignment, indent, scope_id))


def push_shadowed_assigned_path(
    assigned_paths: dict[str, list[PythonTrackedPath]],
    target: str,
    line: PythonDiffLine,
    scope_id: int,
) -> None:
    indent = (python_code_line_indent(line.text) or 0) + 1
    assignments = assigned_paths.setdefault(target, [])
    while assignments and assignments[-1].scope_id == scope_id:
        assignments.pop()
    assignments.append(PythonTrackedPath(None, indent, scope_id))


def clear_assigned_path_in_scope(
    assigned_paths: dict[str, list[PythonTrackedPath]],
    target: str,
    indent: int,
    scope_id: int,
) -> None:
    assignments = assigned_paths.get(target)
    if assignments is not None:
        while assignments and assignments[-1].scope_id == scope_id:
            assignments.pop()
        assignments.append(PythonTrackedPath(None, indent, scope_id))
    else:
        assigned_paths[target] = [PythonTrackedPath(None, indent, scope_id)]
    prefix = f"{target}."
    for tracked_target, tracked_assignments in list(assigned_paths.items()):
        if not tracked_target.startswith(prefix):
            continue
        while tracked_assignments and tracked_assignments[-1].scope_id == scope_id:
            tracked_assignments.pop()
        tracked_assignments.append(PythonTrackedPath(None, indent, scope_id))


def current_assigned_path(assigned_paths: dict[str, list[PythonTrackedPath]], target: str) -> PythonDiffLine | None:
    assignments = assigned_paths.get(target)
    if not assignments:
        return None
    return assignments[-1].assignment


def remove_shadowed_assigned_paths(
    assigned_paths: dict[str, list[PythonTrackedPath]],
    shadowed_names: set[str],
    line: PythonDiffLine,
    scope_id: int,
) -> None:
    for shadowed_name in shadowed_names:
        push_shadowed_assigned_path(assigned_paths, shadowed_name, line, scope_id)
        prefix = f"{shadowed_name}."
        for tracked_target in list(assigned_paths):
            if tracked_target.startswith(prefix):
                push_shadowed_assigned_path(assigned_paths, tracked_target, line, scope_id)


def update_python_multiline_string_state(active_delimiter: str | None, active_diff_fixture: bool, text: str) -> tuple[str | None, bool]:
    if active_delimiter is not None and not active_diff_fixture and "diff --git " in text:
        active_diff_fixture = True
    for match in PYTHON_TRIPLE_QUOTE_RE.finditer(text):
        delimiter = match.group(0)
        if active_delimiter is None:
            active_delimiter = delimiter
            active_diff_fixture = "diff --git " in text[match.end() :]
        elif delimiter == active_delimiter:
            active_delimiter = None
            active_diff_fixture = False
    return active_delimiter, active_diff_fixture


def iter_python_diff_lines_with_context(diff: str) -> list[PythonDiffLine]:
    lines: list[PythonDiffLine] = []
    current_path: str | None = None
    right_line: int | None = None
    hunk_index = 0
    hunk_context = ""
    active_delimiter: str | None = None
    active_diff_fixture = False
    for raw_line in diff.splitlines():
        if raw_line.startswith("diff --git "):
            current_path = None
            right_line = None
            hunk_index = 0
            hunk_context = ""
            active_delimiter = None
            active_diff_fixture = False
            continue
        if raw_line.startswith("+++ b/"):
            current_path = raw_line[6:]
            active_delimiter = None
            active_diff_fixture = False
            continue
        if raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw_line)
            right_line = int(match.group(1)) if match else None
            hunk_index += 1
            hunk_context = python_hunk_context_scope(raw_line)
            active_delimiter = None
            active_diff_fixture = False
            continue
        if current_path is None or right_line is None:
            continue
        if Path(current_path).suffix.lower() != ".py":
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                right_line += 1
            elif not raw_line.startswith("-") or raw_line.startswith("---"):
                right_line += 1
            continue
        if raw_line.startswith("-") and not raw_line.startswith("---"):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            text = raw_line[1:]
            lines.append(
                PythonDiffLine(
                    current_path,
                    hunk_index,
                    right_line,
                    text,
                    True,
                    active_delimiter is not None,
                    active_diff_fixture,
                    hunk_context,
                )
            )
            if active_delimiter is not None or not hardened.is_comment_only_added_line(current_path, text):
                active_delimiter, active_diff_fixture = update_python_multiline_string_state(active_delimiter, active_diff_fixture, text)
            right_line += 1
            continue
        if raw_line.startswith(" "):
            text = raw_line[1:]
            lines.append(
                PythonDiffLine(
                    current_path,
                    hunk_index,
                    right_line,
                    text,
                    False,
                    active_delimiter is not None,
                    active_diff_fixture,
                    hunk_context,
                )
            )
            if active_delimiter is not None or not hardened.is_comment_only_added_line(current_path, text):
                active_delimiter, active_diff_fixture = update_python_multiline_string_state(active_delimiter, active_diff_fixture, text)
            right_line += 1
            continue
        if not raw_line.startswith("\\"):
            right_line += 1
    return lines


def python_diff_fixture_added_line_keys(diff: str) -> set[tuple[str, int]]:
    return {
        (line.path, line.line)
        for line in iter_python_diff_lines_with_context(diff)
        if line.is_added and line.inside_diff_fixture_string
    }


