def python_line_imports_urllib_urlopen_alias(text: str) -> bool:
    module = python_parse_diff_line(text)
    if module is None:
        return bool(re.search(r"^\s*from\s+urllib\.request\s+import\s+.*\burlopen\b", text))
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
            return any(alias.name == "urlopen" for alias in node.names)
    return False


def python_line_is_known_urllib_urlopen(
    text: str,
    allow_imported_alias: bool = False,
    known_call_names: set[str] | None = None,
) -> bool:
    module = python_parse_diff_line(text)
    call_names = set(known_call_names or {"urllib.request.urlopen", "urllib.urlopen"})
    if allow_imported_alias:
        call_names.add("urlopen")
    if module is not None:
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and python_call_name(node.func) in call_names:
                return True
        return False
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in sorted(call_names, key=len, reverse=True)) + r")\s*\("
    return bool(re.search(pattern, text))


def python_line_has_explicit_file_write_call(
    text: str,
    path_constructor_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
    allow_urllib_urlopen_alias: bool = False,
    known_call_names: set[str] | None = None,
) -> bool:
    """Distinguish real file-write APIs from lexical open() lookalikes."""

    module = python_parse_diff_line(text)
    if module is None:
        if python_line_is_known_urllib_urlopen(
            text,
            allow_urllib_urlopen_alias,
            known_call_names,
        ):
            return False
        # Preserve legacy coverage when a single diff line cannot be parsed safely.
        return True
    scoped_bindings = dict(local_int_bindings or {})
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    scoped_bindings[target.id] = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
            scoped_bindings[statement.target.id] = statement.value
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                return python_call_uses_write_mode(
                    node,
                    os_module_names,
                    scoped_bindings,
                    conservative_unknown_kwargs=False,
                )
            if isinstance(func, ast.Attribute) and func.attr in {"write_text", "write_bytes"}:
                return True
            if isinstance(func, ast.Attribute) and func.attr == "open":
                return python_call_uses_write_mode(
                    node,
                    os_module_names,
                    scoped_bindings,
                    conservative_unknown_kwargs=False,
                )
    return False


def python_direct_dynamic_file_write(
    text: str,
    path_constructor_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
) -> bool:
    module = python_parse_diff_line(text)
    if module is None:
        return False
    constructor_names = path_constructor_names or DEFAULT_PYTHON_PATH_CONSTRUCTORS
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"write_text", "write_bytes"}:
            continue
        value = node.func.value
        if python_target_key(value):
            continue
        value_is_path, value_has_dynamic = python_path_expr_info(value, constructor_names, os_module_names)
        if value_is_path and value_has_dynamic:
            return True
    if python_direct_dynamic_open_write(text, path_constructor_names, os_module_names, local_int_bindings):
        return True
    return False


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
