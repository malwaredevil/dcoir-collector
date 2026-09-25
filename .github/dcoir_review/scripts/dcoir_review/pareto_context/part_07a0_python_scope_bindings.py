_PY_SCOPE_FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _python_scope_attribute_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return '.'.join([current.id, *reversed(parts)])


def _python_scope_collect_bindings(node: ast.AST) -> dict[str, Any]:
    roots: set[str] = set()
    local_bindings: set[str] = set()
    assigned_names: set[str] = set()
    globals_declared: set[str] = set()
    nonlocals_declared: set[str] = set()
    trusted_alias_targets: dict[str, set[str]] = {}
    attribute_mutations: list[tuple[int, int, str, str | None, bool]] = []
    binding_events: dict[str, list[tuple[int, int, set[str] | None]]] = {}
    alias_assignments: list[tuple[int, int, str, str]] = []
    submodule_import_binding_keys: set[tuple[str, int, int]] = set()
    sequence = 0

    def record_event(name: str, source_node: ast.AST | None, targets: set[str] | None) -> int:
        nonlocal sequence
        sequence += 1
        line = int(getattr(source_node, 'lineno', getattr(node, 'lineno', 0)) or 0)
        binding_events.setdefault(name, []).append((line, sequence, None if targets is None else set(targets)))
        return sequence

    def bind_local(name: str, *, assigned: bool = False, source_node: ast.AST | None = None) -> int | None:
        roots.add(name)
        local_bindings.add(name)
        if assigned:
            assigned_names.add(name)
        if source_node is not None:
            return record_event(name, source_node, None)
        return None

    def bind_trusted(
        name: str,
        target: str,
        source_node: ast.AST,
        *,
        from_real_submodule: bool = False,
    ) -> None:
        local_bindings.add(name)
        trusted_alias_targets.setdefault(name, set()).add(target)
        event_sequence = record_event(name, source_node, {target})
        if from_real_submodule:
            submodule_import_binding_keys.add(
                (name, int(getattr(source_node, 'lineno', 0) or 0), event_sequence)
            )

    guaranteed_statements = _python_scope_guaranteed_direct_statements(node)

    def collect_target(
        target: ast.AST,
        alias_value_path: str | None = None,
        restoration_guaranteed: bool = False,
    ) -> None:
        nonlocal sequence
        if isinstance(target, ast.Name):
            event_sequence = bind_local(target.id, assigned=True, source_node=target)
            if alias_value_path and event_sequence is not None:
                alias_assignments.append((int(getattr(target, 'lineno', 0) or 0), event_sequence, target.id, alias_value_path))
        elif isinstance(target, ast.Attribute):
            path = _python_scope_attribute_path(target)
            if path:
                sequence += 1
                attribute_mutations.append(
                    (
                        int(getattr(target, 'lineno', 0) or 0),
                        sequence,
                        path,
                        alias_value_path,
                        restoration_guaranteed,
                    )
                )
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                collect_target(item)
        elif isinstance(target, ast.Starred):
            collect_target(target.value)

    def collect_match_pattern(pattern: ast.AST) -> None:
        if isinstance(pattern, ast.MatchAs):
            if pattern.pattern is not None:
                collect_match_pattern(pattern.pattern)
            if pattern.name:
                bind_local(pattern.name, assigned=True, source_node=pattern)
        elif isinstance(pattern, ast.MatchStar):
            if pattern.name:
                bind_local(pattern.name, assigned=True, source_node=pattern)
        elif isinstance(pattern, ast.MatchMapping):
            for child in pattern.patterns:
                collect_match_pattern(child)
            if pattern.rest:
                bind_local(pattern.rest, assigned=True, source_node=pattern)
        elif isinstance(pattern, ast.MatchSequence):
            for child in pattern.patterns:
                collect_match_pattern(child)
        elif isinstance(pattern, ast.MatchClass):
            for child in (*pattern.patterns, *pattern.kwd_patterns):
                collect_match_pattern(child)
        elif isinstance(pattern, ast.MatchOr):
            for child in pattern.patterns:
                collect_match_pattern(child)

    def visit_arg_annotations(visitor: ast.NodeVisitor, args: ast.arguments) -> None:
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            if arg.annotation is not None:
                visitor.visit(arg.annotation)
        if args.vararg is not None and args.vararg.annotation is not None:
            visitor.visit(args.vararg.annotation)
        if args.kwarg is not None and args.kwarg.annotation is not None:
            visitor.visit(args.kwarg.annotation)

    def visit_function_header(visitor: ast.NodeVisitor, item: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in item.decorator_list:
            visitor.visit(decorator)
        for default in item.args.defaults:
            visitor.visit(default)
        for default in item.args.kw_defaults:
            if default is not None:
                visitor.visit(default)
        visit_arg_annotations(visitor, item.args)
        if item.returns is not None:
            visitor.visit(item.returns)

    def visit_class_header(visitor: ast.NodeVisitor, item: ast.ClassDef) -> None:
        for decorator in item.decorator_list:
            visitor.visit(decorator)
        for base_node in item.bases:
            visitor.visit(base_node)
        for keyword in item.keywords:
            visitor.visit(keyword.value)

    def visit_lambda_header(visitor: ast.NodeVisitor, item: ast.Lambda) -> None:
        for default in item.args.defaults:
            visitor.visit(default)
        for default in item.args.kw_defaults:
            if default is not None:
                visitor.visit(default)

    if isinstance(node, _PY_SCOPE_FUNCTION_TYPES):
        args = node.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            bind_local(arg.arg, source_node=arg)
        if args.vararg is not None:
            bind_local(args.vararg.arg, source_node=args.vararg)
        if args.kwarg is not None:
            bind_local(args.kwarg.arg, source_node=args.kwarg)

    class Visitor(ast.NodeVisitor):
        def visit_Global(self, item: ast.Global) -> None:
            globals_declared.update(item.names)

        def visit_Nonlocal(self, item: ast.Nonlocal) -> None:
            nonlocals_declared.update(item.names)

        def visit_FunctionDef(self, item: ast.FunctionDef) -> None:
            if item is not node:
                visit_function_header(self, item)
                bind_local(item.name, assigned=True, source_node=item)
                return
            for stmt in item.body:
                self.visit(stmt)

        def visit_AsyncFunctionDef(self, item: ast.AsyncFunctionDef) -> None:
            if item is not node:
                visit_function_header(self, item)
                bind_local(item.name, assigned=True, source_node=item)
                return
            for stmt in item.body:
                self.visit(stmt)

        def visit_ClassDef(self, item: ast.ClassDef) -> None:
            if item is not node:
                visit_class_header(self, item)
                bind_local(item.name, assigned=True, source_node=item)
                return
            for stmt in item.body:
                self.visit(stmt)

        def visit_Lambda(self, item: ast.Lambda) -> None:
            if item is not node:
                visit_lambda_header(self, item)
                return
            self.visit(item.body)

        def visit_Import(self, item: ast.Import) -> None:
            for alias in item.names:
                name = alias.asname or alias.name.split('.', 1)[0]
                if alias.name == 'urllib':
                    bind_trusted(name, 'urllib', item)
                elif alias.name == 'urllib.request':
                    bind_trusted(name, 'urllib.request' if alias.asname else 'urllib', item)
                else:
                    bind_local(name, assigned=True, source_node=item)

        def visit_ImportFrom(self, item: ast.ImportFrom) -> None:
            for alias in item.names:
                name = alias.asname or alias.name
                if item.module == 'urllib.request' and alias.name == 'urlopen':
                    bind_trusted(
                        name,
                        'urllib.request.urlopen',
                        item,
                        from_real_submodule=True,
                    )
                elif item.module == 'urllib' and alias.name == 'request':
                    bind_trusted(name, 'urllib.request', item)
                else:
                    bind_local(name, assigned=True, source_node=item)

        def visit_Assign(self, item: ast.Assign) -> None:
            self.visit(item.value)
            alias_value_path = _python_scope_attribute_path(item.value) if isinstance(item.value, (ast.Name, ast.Attribute)) else None
            prior_targets_cannot_raise = True
            for target in item.targets:
                collect_target(
                    target,
                    alias_value_path,
                    id(item) in guaranteed_statements and prior_targets_cannot_raise,
                )
                prior_targets_cannot_raise = (
                    prior_targets_cannot_raise and isinstance(target, ast.Name)
                )

        def visit_AnnAssign(self, item: ast.AnnAssign) -> None:
            alias_value_path = None
            if item.value is not None:
                self.visit(item.value)
                if isinstance(item.value, (ast.Name, ast.Attribute)):
                    alias_value_path = _python_scope_attribute_path(item.value)
            collect_target(item.target, alias_value_path, id(item) in guaranteed_statements)

        def visit_AugAssign(self, item: ast.AugAssign) -> None:
            self.visit(item.value)
            collect_target(item.target)

        def visit_NamedExpr(self, item: ast.NamedExpr) -> None:
            self.visit(item.value)
            alias_value_path = _python_scope_attribute_path(item.value) if isinstance(item.value, (ast.Name, ast.Attribute)) else None
            collect_target(item.target, alias_value_path)

        def visit_Delete(self, item: ast.Delete) -> None:
            for target in item.targets:
                collect_target(target)

        def visit_For(self, item: ast.For) -> None:
            self.visit(item.iter)
            collect_target(item.target)
            for stmt in item.body:
                self.visit(stmt)
            for stmt in item.orelse:
                self.visit(stmt)

        visit_AsyncFor = visit_For

        def visit_With(self, item: ast.With) -> None:
            for entry in item.items:
                self.visit(entry.context_expr)
                if entry.optional_vars is not None:
                    collect_target(entry.optional_vars)
            for stmt in item.body:
                self.visit(stmt)

        visit_AsyncWith = visit_With

        def visit_ExceptHandler(self, item: ast.ExceptHandler) -> None:
            if item.type is not None:
                self.visit(item.type)
            if isinstance(item.name, str):
                bind_local(item.name, assigned=True, source_node=item)
            for stmt in item.body:
                self.visit(stmt)

        def _visit_comprehension_scope(self, item: ast.AST, values: list[ast.AST]) -> None:
            generators = list(getattr(item, 'generators', []))
            if item is not node:
                if generators:
                    self.visit(generators[0].iter)
                return
            for generator in generators:
                self.visit(generator.iter)
                collect_target(generator.target)
                for clause in generator.ifs:
                    self.visit(clause)
            for value in values:
                self.visit(value)

        def visit_ListComp(self, item: ast.ListComp) -> None:
            self._visit_comprehension_scope(item, [item.elt])

        visit_SetComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

        def visit_DictComp(self, item: ast.DictComp) -> None:
            self._visit_comprehension_scope(item, [item.key, item.value])

        def visit_match_case(self, item: ast.match_case) -> None:
            collect_match_pattern(item.pattern)
            if item.guard is not None:
                self.visit(item.guard)
            for stmt in item.body:
                self.visit(stmt)

    Visitor().visit(node)
    return {
        'roots': roots,
        'local_bindings': local_bindings,
        'assigned_names': assigned_names,
        'globals': globals_declared,
        'nonlocals': nonlocals_declared,
        'trusted_alias_targets': trusted_alias_targets,
        'attribute_mutations': attribute_mutations,
        'binding_events': binding_events,
        'alias_assignments': alias_assignments,
        'submodule_import_binding_keys': submodule_import_binding_keys,
    }
