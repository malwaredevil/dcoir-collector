def python_path_assignment_start(text: str, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> bool:
    if PYTHON_PATH_ASSIGNMENT_START_RE.search(text):
        return True
    if PYTHON_ASSIGNMENT_CONTINUATION_START_RE.search(text):
        return True
    names = sorted((path_constructor_names or set()) - DEFAULT_PYTHON_PATH_CONSTRUCTORS, key=len, reverse=True)
    os_join_names = sorted(
        f"{name}.path.join" for name in (os_module_names or set()) - DEFAULT_PYTHON_OS_MODULES
    )
    if not names and not os_join_names:
        return False
    constructors = "|".join(re.escape(name) for name in [*names, *os_join_names])
    return bool(
        re.search(
            rf"^\s*{PYTHON_PATH_TARGET_PART}\s*(?::\s*[^=]+)?=\s*(?:{constructors})\s*\(",
            text,
        )
    )


def python_is_literal_path_segment(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))


def python_is_dynamic_path_segment(node: ast.AST) -> bool:
    if python_is_literal_path_segment(node):
        return False
    if isinstance(node, ast.Constant):
        return False
    return True


def python_is_directory_base_path_name(name: str) -> bool:
    leaf = name.rsplit(".", 1)[-1].lower()
    return bool(re.search(r"(?:^|_)(?:base|dir|directory|folder|root|workspace|repo)(?:_|$)", leaf))


def python_single_arg_path_has_dynamic_write_segment(node: ast.AST) -> bool:
    if python_is_literal_path_segment(node):
        return False
    if isinstance(node, ast.Constant):
        return False
    target = python_target_key(node)
    if target and python_is_directory_base_path_name(target):
        return False
    return python_is_dynamic_path_segment(node)


def python_is_path_constructor(node: ast.AST, path_constructor_names: set[str] | None = None) -> bool:
    constructors = path_constructor_names or DEFAULT_PYTHON_PATH_CONSTRUCTORS
    return isinstance(node, ast.Call) and python_call_name(node.func) in constructors


def python_is_os_path_join(node: ast.AST, os_module_names: set[str] | None = None) -> bool:
    modules = os_module_names or DEFAULT_PYTHON_OS_MODULES
    return isinstance(node, ast.Call) and python_call_name(node.func) in {f"{name}.path.join" for name in modules}


def python_is_joinpath_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath"


def python_path_expr_info(node: ast.AST, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> tuple[bool, bool]:
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            left_is_path, left_has_dynamic = python_path_expr_info(node.left, path_constructor_names, os_module_names)
            right_is_path, right_has_dynamic = python_path_expr_info(node.right, path_constructor_names, os_module_names)
            if left_is_path or right_is_path:
                return True, (
                    left_has_dynamic
                    or right_has_dynamic
                    or python_is_dynamic_path_segment(node.left)
                    or python_is_dynamic_path_segment(node.right)
                )
            return False, False
        if isinstance(node.op, ast.Div):
            left_is_path, left_has_dynamic = python_path_expr_info(node.left, path_constructor_names, os_module_names)
            if not left_is_path:
                right_is_dynamic = python_is_dynamic_path_segment(node.right)
                return right_is_dynamic, right_is_dynamic
            return True, left_has_dynamic or python_is_dynamic_path_segment(node.right)
    if python_is_joinpath_call(node):
        base_is_path, base_has_dynamic = python_path_expr_info(node.func.value, path_constructor_names, os_module_names)
        if not base_is_path:
            return False, False
        return True, base_has_dynamic or any(python_is_dynamic_path_segment(arg) for arg in node.args)
    if python_is_path_constructor(node, path_constructor_names) or python_is_os_path_join(node, os_module_names):
        args = list(node.args)
        if len(args) == 1:
            arg = args[0]
            arg_is_path, arg_has_dynamic = python_path_expr_info(arg, path_constructor_names, os_module_names)
            if arg_is_path or (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Div)):
                return True, arg_has_dynamic
            return True, python_single_arg_path_has_dynamic_write_segment(arg)
        if len(args) < 1:
            return True, False
        return True, any(python_is_dynamic_path_segment(arg) for arg in args[1:])
    return False, False


def python_path_expr_has_dynamic_write_segment(node: ast.AST, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> bool:
    _is_path, has_dynamic = python_path_expr_info(node, path_constructor_names, os_module_names)
    return has_dynamic


def python_single_dynamic_path_expr(node: ast.AST, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> bool:
    if not (python_is_path_constructor(node, path_constructor_names) or python_is_os_path_join(node, os_module_names)):
        return False
    args = list(node.args)
    if len(args) != 1:
        return False
    arg = args[0]
    arg_is_path, arg_has_dynamic = python_path_expr_info(arg, path_constructor_names, os_module_names)
    if arg_is_path or (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Div)):
        return arg_has_dynamic
    return python_single_arg_path_has_dynamic_write_segment(arg)


def python_dynamic_path_target(text: str, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> str | None:
    assignment = python_simple_assignment(text)
    if assignment:
        target, expr_node = assignment
        if python_path_expr_has_dynamic_write_segment(expr_node, path_constructor_names, os_module_names) or python_single_dynamic_path_expr(
            expr_node,
            path_constructor_names,
            os_module_names,
        ):
            return target
    if len(text) > PYTHON_PATH_ASSIGNMENT_MAX_CHARS:
        return None
    constructor_names = path_constructor_names or DEFAULT_PYTHON_PATH_CONSTRUCTORS
    os_modules = os_module_names or DEFAULT_PYTHON_OS_MODULES
    os_join_names = {f"{name}.path.join" for name in os_modules}
    if "Path" not in text and not any(name in text for name in os_join_names) and not any(f"{name}(" in text for name in constructor_names):
        return None
    match = PYTHON_PATH_ASSIGNMENT_RE.search(text)
    if not match:
        return None
    expr = match.group("expr")
    if "/" not in expr and not any(name in expr for name in os_join_names) and not re.search(r"\bPath\s*\(", expr):
        return None
    if not (re.search(r"\bf['\"]", expr) and "{" in expr):
        return None
    return match.group("target")


def python_augmented_dynamic_path_target(text: str, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> str | None:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return None
    if not module.body or not isinstance(module.body[0], ast.AugAssign):
        return None
    statement = module.body[0]
    target = python_target_key(statement.target)
    if not target:
        return None
    if isinstance(statement.op, ast.Div) and python_is_dynamic_path_segment(statement.value):
        return target
    if isinstance(statement.op, ast.Add):
        value_is_path, value_has_dynamic = python_path_expr_info(statement.value, path_constructor_names, os_module_names)
        if value_is_path and value_has_dynamic:
            return target
    return None


def python_direct_dynamic_file_write(text: str, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> bool:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
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
    return False


def python_file_write_target(text: str, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> str | None:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        write_match = PYTHON_FILE_WRITE_RE.search(text)
        if not write_match:
            return None
        return write_match.group("target") or write_match.group("wrapped_target")
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"write_text", "write_bytes"}:
            continue
        target = python_target_key(node.func.value)
        if target:
            return target
    return None


def python_wrapped_file_write_target(text: str, path_constructor_names: set[str] | None = None, os_module_names: set[str] | None = None) -> str | None:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return None
    constructor_names = path_constructor_names or DEFAULT_PYTHON_PATH_CONSTRUCTORS
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"write_text", "write_bytes"}:
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


