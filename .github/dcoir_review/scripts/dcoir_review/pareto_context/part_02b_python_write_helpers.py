def python_file_write_target(
    text: str,
    path_constructor_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
) -> str | None:
    module = python_parse_diff_line(text)
    if module is None:
        write_match = PYTHON_FILE_WRITE_RE.search(text)
        if not write_match:
            return None
        return write_match.group("target") or write_match.group("wrapped_target")
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in {"write_text", "write_bytes"}:
            target = python_target_key(node.func.value)
            if target:
                return target
            continue
        if node.func.attr == "open" and python_call_uses_write_mode(
            node,
            os_module_names,
            local_int_bindings,
            assume_path_receiver=True,
        ):
            target = python_target_key(node.func.value)
            if target:
                return target
    return None


def python_wrapped_file_write_target(
    text: str,
    path_constructor_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
) -> str | None:
    module = python_parse_diff_line(text)
    if module is None:
        return None
    constructor_names = path_constructor_names or DEFAULT_PYTHON_PATH_CONSTRUCTORS
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"write_text", "write_bytes", "open"}:
            continue
        if node.func.attr == "open" and not python_call_uses_write_mode(
            node,
            os_module_names,
            local_int_bindings,
            assume_path_receiver=True,
        ):
            continue
        value = node.func.value
        if python_is_path_constructor(value, constructor_names) and value.args:
            return python_target_key(value.args[0])
    return None


def append_file_write_sentinel(sentinels: list[hardened.RiskSentinel], anchor: PythonDiffLine) -> None:
    sentinels.append(
        hardened.RiskSentinel(
            path=anchor.path,
            line=anchor.line,
            label=FILE_WRITE_PATH_LABEL,
            detail=FILE_WRITE_PATH_DETAIL,
            text=anchor.text,
        )
    )


def python_dynamic_exec_call_name(text: str) -> str | None:
    if "eval" not in text and "exec" not in text:
        return None
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return None
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        call_name = python_call_name(node.func)
        if call_name in PYTHON_DYNAMIC_EXEC_CALL_NAMES:
            return call_name
    return None
