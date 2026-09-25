def python_scoped_shadowed_name_roots_by_line(source: str) -> dict[int, set[str]]:
    """Return conservative, lexical-scope-aware urllib shadow roots by source line."""
    module = ast.parse(source)
    by_line: dict[int, set[str]] = {}
    scope_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

    def attribute_path(node: ast.AST) -> str | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        return '.'.join([current.id, *reversed(parts)])

    def trusted_urllib_root_targets() -> dict[str, set[str]]:
        targets: dict[str, set[str]] = {}
        for item in ast.walk(module):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    if alias.name == 'urllib':
                        name = alias.asname or 'urllib'
                        targets.setdefault(name, set()).add('urllib')
                    elif alias.name == 'urllib.request':
                        name = alias.asname or 'urllib'
                        target = 'urllib.request' if alias.asname else 'urllib'
                        targets.setdefault(name, set()).add(target)
            elif isinstance(item, ast.ImportFrom):
                for alias in item.names:
                    if item.module == 'urllib' and alias.name == 'request':
                        name = alias.asname or alias.name
                        targets.setdefault(name, set()).add('urllib.request')
                    elif item.module == 'urllib.request' and alias.name == 'urlopen':
                        name = alias.asname or alias.name
                        targets.setdefault(name, set()).add('urllib.request.urlopen')
        return targets

    def canonical_paths(path: str, targets: dict[str, set[str]]) -> set[str]:
        root, dot, suffix = path.partition('.')
        mapped = targets.get(root)
        if not mapped:
            return {path}
        return {f'{target}.{suffix}' if dot and suffix else target for target in mapped}

    def collect_scope_bindings(node: ast.AST) -> dict[str, set[str]]:
        roots: set[str] = set()
        local_bindings: set[str] = set()
        assigned_names: set[str] = set()
        globals_declared: set[str] = set()
        nonlocals_declared: set[str] = set()
        trusted_roots: set[str] = set()
        attribute_mutations: set[str] = set()

        def bind_local(name: str, *, assigned: bool = False) -> None:
            roots.add(name)
            local_bindings.add(name)
            if assigned:
                assigned_names.add(name)

        def collect_target(target: ast.AST) -> None:
            if isinstance(target, ast.Name):
                bind_local(target.id, assigned=True)
            elif isinstance(target, ast.Attribute):
                path = attribute_path(target)
                if path:
                    attribute_mutations.add(path)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for item in target.elts:
                    collect_target(item)
            elif isinstance(target, ast.Starred):
                collect_target(target.value)

        if isinstance(node, scope_types):
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                bind_local(arg.arg)
            if args.vararg is not None:
                bind_local(args.vararg.arg)
            if args.kwarg is not None:
                bind_local(args.kwarg.arg)

        class Visitor(ast.NodeVisitor):
            def visit_Global(self, item: ast.Global) -> None:
                globals_declared.update(item.names)

            def visit_Nonlocal(self, item: ast.Nonlocal) -> None:
                nonlocals_declared.update(item.names)

            def visit_FunctionDef(self, item: ast.FunctionDef) -> None:
                if item is not node:
                    bind_local(item.name, assigned=True)
                    return
                for stmt in item.body:
                    self.visit(stmt)

            def visit_AsyncFunctionDef(self, item: ast.AsyncFunctionDef) -> None:
                if item is not node:
                    bind_local(item.name, assigned=True)
                    return
                for stmt in item.body:
                    self.visit(stmt)

            def visit_ClassDef(self, item: ast.ClassDef) -> None:
                bind_local(item.name, assigned=True)

            def visit_Lambda(self, item: ast.Lambda) -> None:
                if item is node:
                    self.visit(item.body)

            def visit_Import(self, item: ast.Import) -> None:
                for alias in item.names:
                    name = alias.asname or alias.name.split('.', 1)[0]
                    if alias.name in {'urllib', 'urllib.request'}:
                        trusted_roots.add(name)
                        local_bindings.add(name)
                    else:
                        bind_local(name, assigned=True)

            def visit_ImportFrom(self, item: ast.ImportFrom) -> None:
                for alias in item.names:
                    name = alias.asname or alias.name
                    trusted = (item.module == 'urllib.request' and alias.name == 'urlopen') or (
                        item.module == 'urllib' and alias.name == 'request'
                    )
                    if trusted:
                        trusted_roots.add(name)
                        local_bindings.add(name)
                    else:
                        bind_local(name, assigned=True)

            def visit_Assign(self, item: ast.Assign) -> None:
                for target in item.targets:
                    collect_target(target)
                self.visit(item.value)

            def visit_AnnAssign(self, item: ast.AnnAssign) -> None:
                collect_target(item.target)
                if item.value is not None:
                    self.visit(item.value)

            def visit_AugAssign(self, item: ast.AugAssign) -> None:
                collect_target(item.target)
                self.visit(item.value)

            def visit_NamedExpr(self, item: ast.NamedExpr) -> None:
                collect_target(item.target)
                self.visit(item.value)

            def visit_Delete(self, item: ast.Delete) -> None:
                for target in item.targets:
                    collect_target(target)

            def visit_For(self, item: ast.For) -> None:
                collect_target(item.target)
                self.generic_visit(item)

            visit_AsyncFor = visit_For

            def visit_With(self, item: ast.With) -> None:
                for entry in item.items:
                    if entry.optional_vars is not None:
                        collect_target(entry.optional_vars)
                self.generic_visit(item)

            visit_AsyncWith = visit_With

            def visit_ExceptHandler(self, item: ast.ExceptHandler) -> None:
                if isinstance(item.name, str):
                    bind_local(item.name, assigned=True)
                self.generic_visit(item)

        Visitor().visit(node)
        return {
            'roots': roots,
            'local_bindings': local_bindings,
            'assigned_names': assigned_names,
            'globals': globals_declared,
            'nonlocals': nonlocals_declared,
            'trusted_roots': trusted_roots,
            'attribute_mutations': attribute_mutations,
        }

    def iter_nested_scopes(node: ast.AST):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, scope_types):
                yield child
                continue
            yield from iter_nested_scopes(child)

    infos: dict[ast.AST, dict[str, set[str]]] = {}
    parents: dict[ast.AST, ast.AST | None] = {}

    def register_scope(node: ast.AST, parent: ast.AST | None) -> None:
        infos[node] = collect_scope_bindings(node)
        parents[node] = parent
        for child in iter_nested_scopes(node):
            register_scope(child, node)

    for top_scope in iter_nested_scopes(module):
        register_scope(top_scope, None)

    global_shadowed_roots: set[str] = set()
    for info in infos.values():
        global_shadowed_roots.update(info['globals'] & info['assigned_names'])

    trusted_targets = trusted_urllib_root_targets()
    known_calls = python_urllib_urlopen_call_names(source)
    shared_qualified_shadow_roots: set[str] = set()
    for info in infos.values():
        for mutation in info['attribute_mutations']:
            mutation_targets = canonical_paths(mutation, trusted_targets)
            for call in known_calls:
                call_targets = canonical_paths(call, trusted_targets)
                if any(
                    call_target == mutation_target or call_target.startswith(f'{mutation_target}.')
                    for mutation_target in mutation_targets
                    for call_target in call_targets
                ):
                    shared_qualified_shadow_roots.add(call.split('.', 1)[0])

    nonlocal_rebounds: dict[ast.AST, set[str]] = {node: set() for node in infos}
    for node, info in infos.items():
        rebound_names = info['nonlocals'] & info['assigned_names']
        for name in rebound_names:
            owner = parents.get(node)
            while owner is not None:
                owner_info = infos[owner]
                local_bindings = (owner_info['local_bindings'] | owner_info['trusted_roots']) - (
                    owner_info['globals'] | owner_info['nonlocals']
                )
                if name in local_bindings:
                    nonlocal_rebounds[owner].add(name)
                    break
                owner = parents.get(owner)

    module_shadow_state = global_shadowed_roots | shared_qualified_shadow_roots

    def scope_header_lines(node: ast.AST, body_start: int) -> set[int]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return set()
        starts = [int(getattr(node, 'lineno', 0) or 0)]
        starts.extend(int(getattr(item, 'lineno', 0) or 0) for item in node.decorator_list)
        start = min(line for line in starts if line > 0)
        return set(range(start, max(start, body_start - 1) + 1))

    def walk_scope(node: ast.AST, inherited: set[str]) -> None:
        info = infos[node]
        roots = set(info['roots'])
        roots.difference_update(info['globals'])
        roots.difference_update(info['nonlocals'])

        active = set(inherited)
        for name in info['globals']:
            if name in module_shadow_state:
                active.add(name)
            else:
                active.discard(name)
        active.difference_update(info['trusted_roots'])
        active.update(roots)
        active.update(nonlocal_rebounds[node])
        # A fresh import can replace a lexical/global name rebound, but it does
        # not undo mutation of the shared urllib module object itself. Reapply
        # only qualified-mutation roots whose canonical urlopen target is shared.
        active.update(shared_qualified_shadow_roots)

        start = int(getattr(node, 'lineno', 0) or 0)
        end = int(getattr(node, 'end_lineno', start) or start)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            body_start = min(int(getattr(stmt, 'lineno', start) or start) for stmt in node.body)
            header_lines = scope_header_lines(node, body_start)
            for line in header_lines:
                by_line[line] = set(inherited)
            for line in range(body_start, end + 1):
                if line in header_lines:
                    by_line[line] = set(inherited) | active
                else:
                    by_line[line] = set(active)
        else:
            for line in range(start, end + 1):
                by_line[line] = set(inherited) | active

        for child in iter_nested_scopes(node):
            walk_scope(child, active)

    for top_scope in iter_nested_scopes(module):
        walk_scope(top_scope, module_shadow_state)
    return by_line


def build_python_scoped_shadowed_name_context(
    gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]
) -> dict[str, dict[int, set[str]]]:
    head_sha = str(pr.get('head', {}).get('sha', '') or '')
    if not head_sha:
        return {}
    context: dict[str, dict[int, set[str]]] = {}
    for item in files:
        path = str(item.get('filename', '')).strip()
        status = str(item.get('status', '')).strip()
        if not path or status in {'removed', 'deleted'} or Path(path).suffix.lower() != '.py':
            continue
        try:
            by_line = python_scoped_shadowed_name_roots_by_line(fetch_pr_file_text(gh, path, head_sha))
        except (SyntaxError, ValueError, TypeError):
            continue
        if by_line:
            context[path] = by_line
    return context
