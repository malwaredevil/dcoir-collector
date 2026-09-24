def python_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = python_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def python_bounded_int_expr(value: int) -> int | None:
    return value if abs(value).bit_length() <= PYTHON_INT_EXPR_MAX_BITS else None


def python_call_arg(call: ast.Call, position: int, *keyword_names: str) -> ast.AST | None:
    if len(call.args) > position:
        return call.args[position]
    for keyword in call.keywords:
        if keyword.arg in keyword_names:
            return keyword.value
    return None


def python_call_uses_write_mode(
    call: ast.Call,
    os_module_names: set[str] | None = None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
) -> bool:
    """Return True when open-style calls can mutate filesystem contents."""

    call_name = python_call_name(call.func)
    has_kwargs_expansion = any(keyword.arg is None for keyword in call.keywords)
    os_open_names = {f"{name}.open" for name in (os_module_names or DEFAULT_PYTHON_OS_MODULES)}
    if call_name in os_open_names:
        flags_node = python_call_arg(call, 1, "flags")
        folded_flags = python_fold_int_expr(flags_node, local_int_bindings, None, os_module_names)
        if folded_flags is not None:
            access_mode = folded_flags & PYTHON_OS_OPEN_ACCESS_MODE_MASK
            if access_mode == PYTHON_OS_OPEN_RDONLY_MODE:
                return bool(folded_flags & PYTHON_OS_OPEN_MUTATING_FLAG_MASK)
            return True
        if flags_node is None:
            return has_kwargs_expansion
        referenced_flags = python_os_open_flag_names(flags_node, os_module_names)
        if referenced_flags & (PYTHON_OS_OPEN_WRITE_ACCESS_NAMES | PYTHON_OS_OPEN_MUTATING_FLAG_NAMES):
            return True
        if (
            referenced_flags
            and referenced_flags <= PYTHON_OS_OPEN_KNOWN_FLAG_NAMES
            and python_os_open_flag_expr_is_fully_known(flags_node, os_module_names, local_int_bindings)
        ):
            return False
        return True
    if isinstance(call.func, ast.Name) and call.func.id == "open":
        mode_node = call.args[1] if len(call.args) > 1 else None
    elif isinstance(call.func, ast.Attribute) and call.func.attr == "open":
        mode_node = call.args[0] if call.args else None
    else:
        mode_node = None
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode_node = keyword.value
            break
    if mode_node is None:
        return has_kwargs_expansion
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return any(token in mode_node.value.lower() for token in ("w", "a", "x", "+"))
    return True


def python_fold_int_expr(
    node: ast.AST | None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
    seen_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
) -> int | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return python_bounded_int_expr(int(node.value))
    if isinstance(node, ast.Name):
        if local_int_bindings and node.id in local_int_bindings:
            if seen_names is None:
                seen_names = set()
            if node.id in seen_names:
                return None
            bound_value = local_int_bindings[node.id]
            if isinstance(bound_value, int):
                return python_bounded_int_expr(bound_value)
            return python_fold_int_expr(
                bound_value,
                local_int_bindings,
                seen_names | {node.id},
                os_module_names,
            )
        return None
    if isinstance(node, ast.Attribute):
        if python_call_name(node.value) not in (os_module_names or DEFAULT_PYTHON_OS_MODULES):
            return None
        value = getattr(os, node.attr, None)
        return python_bounded_int_expr(value) if isinstance(value, int) else None
    if isinstance(node, ast.UnaryOp):
        operand = python_fold_int_expr(node.operand, local_int_bindings, seen_names, os_module_names)
        if operand is None:
            return None
        if isinstance(node.op, ast.Invert):
            return python_bounded_int_expr(~operand)
        if isinstance(node.op, ast.UAdd):
            return python_bounded_int_expr(+operand)
        if isinstance(node.op, ast.USub):
            return python_bounded_int_expr(-operand)
        return None
    if isinstance(node, ast.BinOp):
        left = python_fold_int_expr(node.left, local_int_bindings, seen_names, os_module_names)
        right = python_fold_int_expr(node.right, local_int_bindings, seen_names, os_module_names)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.BitOr):
            return python_bounded_int_expr(left | right)
        if isinstance(node.op, ast.BitAnd):
            return python_bounded_int_expr(left & right)
        if isinstance(node.op, ast.BitXor):
            return python_bounded_int_expr(left ^ right)
        if isinstance(node.op, ast.LShift):
            if right < 0 or right > PYTHON_INT_EXPR_SHIFT_MAX:
                return None
            return python_bounded_int_expr(left << right)
        if isinstance(node.op, ast.RShift):
            if right < 0 or right > PYTHON_INT_EXPR_SHIFT_MAX:
                return None
            return python_bounded_int_expr(left >> right)
        if isinstance(node.op, ast.Add):
            return python_bounded_int_expr(left + right)
        if isinstance(node.op, ast.Sub):
            return python_bounded_int_expr(left - right)
    return None


def python_os_open_flag_names(
    node: ast.AST,
    os_module_names: set[str] | None = None,
) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and child.attr.startswith("O_")
            and python_call_name(child.value) in (os_module_names or DEFAULT_PYTHON_OS_MODULES)
        ):
            names.add(child.attr)
    return names


def python_os_open_flag_expr_is_fully_known(
    node: ast.AST,
    os_module_names: set[str] | None = None,
    local_int_bindings: dict[str, ast.AST | int] | None = None,
    seen_names: set[str] | None = None,
) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int)
    if isinstance(node, ast.Name):
        if not local_int_bindings or node.id not in local_int_bindings:
            return False
        if seen_names is None:
            seen_names = set()
        if node.id in seen_names:
            return False
        bound_value = local_int_bindings[node.id]
        if isinstance(bound_value, int):
            return True
        return python_os_open_flag_expr_is_fully_known(
            bound_value,
            os_module_names,
            local_int_bindings,
            seen_names | {node.id},
        )
    if isinstance(node, ast.Attribute):
        return (
            node.attr in PYTHON_OS_OPEN_KNOWN_FLAG_NAMES
            and python_call_name(node.value) in (os_module_names or DEFAULT_PYTHON_OS_MODULES)
        )
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.Invert, ast.UAdd, ast.USub)) and python_os_open_flag_expr_is_fully_known(
            node.operand,
            os_module_names,
            local_int_bindings,
            seen_names,
        )
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift, ast.Add, ast.Sub)):
            return False
        return python_os_open_flag_expr_is_fully_known(
            node.left,
            os_module_names,
            local_int_bindings,
            seen_names,
        ) and python_os_open_flag_expr_is_fully_known(
            node.right,
            os_module_names,
            local_int_bindings,
            seen_names,
        )
    return False


def python_target_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = python_target_key(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
    return None


def python_assignment_target_names(text: str) -> set[str]:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return set()
    names: set[str] = set()

    def collect(node: ast.AST) -> None:
        target_key = python_target_key(node)
        if target_key:
            names.add(target_key)
            return
        if isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                collect(item)
        elif isinstance(node, ast.Starred):
            collect(node.value)
        elif isinstance(node, ast.Subscript):
            collect(node.value)

    for statement in module.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                collect(target)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            collect(statement.target)
        elif isinstance(statement, ast.AugAssign):
            collect(statement.target)
    return names


def python_simple_assignment(text: str) -> tuple[str, ast.AST] | None:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return None
    if not module.body:
        return None
    statement = module.body[0]
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target_key = python_target_key(statement.targets[0])
        if target_key:
            return target_key, statement.value
    if isinstance(statement, ast.AnnAssign) and statement.value is not None:
        target_key = python_target_key(statement.target)
        if target_key:
            return target_key, statement.value
    return None


def python_assignment_value_references_target(text: str, target: str) -> bool:
    assignment = python_simple_assignment(text)
    if not assignment or assignment[0] != target:
        return False
    for node in ast.walk(assignment[1]):
        target_key = python_target_key(node)
        if target_key == target or (target_key and target_key.startswith(f"{target}.")):
            return True
    return False


def python_augmented_assignment_targets(text: str) -> set[str]:
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return set()
    targets: set[str] = set()
    for statement in module.body:
        if isinstance(statement, ast.AugAssign):
            target_key = python_target_key(statement.target)
            if target_key:
                targets.add(target_key)
    return targets


def python_statement_is_complete(text: str) -> bool:
    try:
        ast.parse(text.lstrip())
    except SyntaxError:
        return False
    return True


def python_path_constructor_aliases(text: str) -> set[str]:
    aliases: set[str] = set()
    if len(text) > PYTHON_PATH_ASSIGNMENT_MAX_CHARS:
        return aliases
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return aliases
    for statement in ast.walk(module):
        if isinstance(statement, ast.ImportFrom) and statement.module == "pathlib":
            for alias in statement.names:
                if alias.name == "Path":
                    aliases.add(alias.asname or alias.name)
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == "pathlib":
                    aliases.add(f"{alias.asname or alias.name}.Path")
    return aliases



def python_os_module_aliases(text: str) -> set[str]:
    aliases: set[str] = set()
    if len(text) > PYTHON_PATH_ASSIGNMENT_MAX_CHARS:
        return aliases
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return aliases
    for statement in ast.walk(module):
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == "os":
                    aliases.add(alias.asname or alias.name)
    return aliases

def set_python_path_alias_context(path_alias_context: dict[str, set[str]] | None) -> None:
    global PYTHON_PATH_ALIAS_CONTEXT
    PYTHON_PATH_ALIAS_CONTEXT = {
        path: set(aliases)
        for path, aliases in (path_alias_context or {}).items()
        if aliases
    }


def set_python_os_alias_context(os_alias_context: dict[str, set[str]] | None) -> None:
    global PYTHON_OS_ALIAS_CONTEXT
    PYTHON_OS_ALIAS_CONTEXT = {
        path: set(aliases)
        for path, aliases in (os_alias_context or {}).items()
        if aliases
    }
