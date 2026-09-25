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

    def drop_root(root: str) -> None:
        aliases.difference_update(
            {
                alias
                for alias in aliases
                if alias == root or alias.startswith(f"{root}.")
            }
        )

    def bound_roots(statement: ast.stmt) -> set[str]:
        roots: set[str] = set()

        def collect_target(node: ast.AST) -> None:
            if isinstance(node, ast.Name):
                roots.add(node.id)
            elif isinstance(node, ast.Attribute):
                collect_target(node.value)
            elif isinstance(node, (ast.Tuple, ast.List)):
                for item in node.elts:
                    collect_target(item)
            elif isinstance(node, ast.Starred):
                collect_target(node.value)

        for node in ast.walk(statement):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    collect_target(target)
            elif isinstance(node, ast.AnnAssign):
                collect_target(node.target)
            elif isinstance(node, ast.AugAssign):
                collect_target(node.target)
            elif isinstance(node, ast.NamedExpr):
                collect_target(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                collect_target(node.target)
            elif isinstance(node, ast.With):
                for item in node.items:
                    if item.optional_vars is not None:
                        collect_target(item.optional_vars)
            elif isinstance(node, ast.AsyncWith):
                for item in node.items:
                    if item.optional_vars is not None:
                        collect_target(item.optional_vars)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                roots.add(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                roots.add(node.name)
        return roots

    for statement in module.body:
        if isinstance(statement, ast.ImportFrom):
            for imported in statement.names:
                imported_name = imported.asname or imported.name
                drop_root(imported_name)
                if statement.module == "pathlib" and imported.name == "Path":
                    aliases.add(imported_name)
        elif isinstance(statement, ast.Import):
            for imported in statement.names:
                root = imported.asname or imported.name.split(".", 1)[0]
                drop_root(root)
                if imported.name == "pathlib":
                    aliases.add(f"{root}.Path")
        else:
            for root in bound_roots(statement):
                drop_root(root)
    return aliases



def python_os_module_aliases(text: str) -> set[str]:
    aliases: set[str] = set()
    if len(text) > PYTHON_PATH_ASSIGNMENT_MAX_CHARS:
        return aliases
    try:
        module = ast.parse(text.lstrip())
    except SyntaxError:
        return aliases

    def bound_roots(statement: ast.stmt) -> set[str]:
        roots: set[str] = set()

        def collect_target(node: ast.AST) -> None:
            if isinstance(node, ast.Name):
                roots.add(node.id)
            elif isinstance(node, ast.Attribute):
                collect_target(node.value)
            elif isinstance(node, (ast.Tuple, ast.List)):
                for item in node.elts:
                    collect_target(item)
            elif isinstance(node, ast.Starred):
                collect_target(node.value)

        for node in ast.walk(statement):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    collect_target(target)
            elif isinstance(node, ast.AnnAssign):
                collect_target(node.target)
            elif isinstance(node, ast.AugAssign):
                collect_target(node.target)
            elif isinstance(node, ast.NamedExpr):
                collect_target(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                collect_target(node.target)
            elif isinstance(node, ast.With):
                for item in node.items:
                    if item.optional_vars is not None:
                        collect_target(item.optional_vars)
            elif isinstance(node, ast.AsyncWith):
                for item in node.items:
                    if item.optional_vars is not None:
                        collect_target(item.optional_vars)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                roots.add(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                roots.add(node.name)
        return roots

    for statement in module.body:
        if isinstance(statement, ast.Import):
            for imported in statement.names:
                root = imported.asname or imported.name.split(".", 1)[0]
                aliases.discard(root)
                if imported.name == "os":
                    aliases.add(root)
        elif isinstance(statement, ast.ImportFrom):
            for imported in statement.names:
                aliases.discard(imported.asname or imported.name)
        else:
            for root in bound_roots(statement):
                aliases.discard(root)
    return aliases
