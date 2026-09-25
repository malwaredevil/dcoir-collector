def python_line_imports_urllib_urlopen_alias(text: str) -> bool:
    module = python_parse_diff_line(text)
    if module is None:
        return bool(re.search(r"^\s*from\s+urllib\.request\s+import\s+.*\burlopen\b", text))
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
            return any(alias.name == "urlopen" for alias in node.names)
    return False


def python_shadowed_name_roots(module: ast.AST) -> set[str]:
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

    def collect_arguments(node: ast.arguments) -> None:
        for argument in (
            *node.posonlyargs,
            *node.args,
            *node.kwonlyargs,
        ):
            roots.add(argument.arg)
        if node.vararg is not None:
            roots.add(node.vararg.arg)
        if node.kwarg is not None:
            roots.add(node.kwarg.arg)

    class _ModuleScopeShadowVisitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                imported_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                if alias.name not in {"urllib", "urllib.request"}:
                    roots.add(imported_name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                imported_name = alias.asname or alias.name
                if not (
                    node.module == "urllib.request"
                    and alias.name == "urlopen"
                ) and not (
                    node.module == "urllib"
                    and alias.name == "request"
                ):
                    roots.add(imported_name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            roots.add(node.name)
            collect_arguments(node.args)
            for statement in node.body:
                self.visit(statement)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            roots.add(node.name)
            collect_arguments(node.args)
            for statement in node.body:
                self.visit(statement)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            roots.add(node.name)

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                collect_target(target)
            self.generic_visit(node.value)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            collect_target(node.target)
            if node.value is not None:
                self.generic_visit(node.value)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            collect_target(node.target)
            self.generic_visit(node.value)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            collect_target(node.target)
            self.generic_visit(node.value)

        def visit_For(self, node: ast.For) -> None:
            collect_target(node.target)
            self.generic_visit(node.iter)
            for statement in node.body:
                self.visit(statement)
            for statement in node.orelse:
                self.visit(statement)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            collect_target(node.target)
            self.generic_visit(node.iter)
            for statement in node.body:
                self.visit(statement)
            for statement in node.orelse:
                self.visit(statement)

        def visit_With(self, node: ast.With) -> None:
            for item in node.items:
                if item.optional_vars is not None:
                    collect_target(item.optional_vars)
                self.generic_visit(item.context_expr)
            for statement in node.body:
                self.visit(statement)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            for item in node.items:
                if item.optional_vars is not None:
                    collect_target(item.optional_vars)
                self.generic_visit(item.context_expr)
            for statement in node.body:
                self.visit(statement)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name:
                roots.add(node.name)
            if node.type is not None:
                self.generic_visit(node.type)
            for statement in node.body:
                self.visit(statement)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            collect_arguments(node.args)
            self.visit(node.body)

        def _visit_comprehension_generators(self, generators: list[ast.comprehension]) -> None:
            for generator in generators:
                collect_target(generator.target)
                self.visit(generator.iter)
                for if_clause in generator.ifs:
                    self.visit(if_clause)

        def visit_ListComp(self, node: ast.ListComp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.elt)

        def visit_SetComp(self, node: ast.SetComp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.elt)

        def visit_DictComp(self, node: ast.DictComp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.key)
            self.visit(node.value)

        def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.elt)

    visitor = _ModuleScopeShadowVisitor()
    for statement in getattr(module, "body", []):
        visitor.visit(statement)
    return roots


def python_module_shadowed_name_roots(module: ast.AST) -> set[str]:
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

    for statement in getattr(module, "body", []):
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                imported_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                if alias.name in {"urllib", "urllib.request", "os"}:
                    roots.discard(imported_name)
                else:
                    roots.add(imported_name)
        elif isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                imported_name = alias.asname or alias.name
                if (
                    statement.module == "urllib.request"
                    and alias.name == "urlopen"
                ) or (
                    statement.module == "urllib"
                    and alias.name == "request"
                ):
                    roots.discard(imported_name)
                else:
                    roots.add(imported_name)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            roots.add(statement.name)
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                collect_target(target)
        elif isinstance(statement, ast.AnnAssign):
            collect_target(statement.target)
        elif isinstance(statement, ast.AugAssign):
            collect_target(statement.target)
        elif isinstance(statement, ast.NamedExpr):
            collect_target(statement.target)
        elif isinstance(statement, (ast.For, ast.AsyncFor)):
            collect_target(statement.target)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                if item.optional_vars is not None:
                    collect_target(item.optional_vars)
    return roots


def python_scope_definition_name(text: str) -> str | None:
    module = python_parse_diff_line(text)
    if module is None or not module.body:
        return None
    statement = module.body[0]
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return statement.name
    return None


def python_trusted_import_roots(module: ast.AST) -> set[str]:
    roots: set[str] = set()
    for statement in getattr(module, "body", []):
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                imported_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                if alias.name in {"os", "urllib", "urllib.request"}:
                    roots.add(imported_name)
        elif isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                imported_name = alias.asname or alias.name
                if (
                    statement.module == "urllib.request"
                    and alias.name == "urlopen"
                ) or (
                    statement.module == "urllib"
                    and alias.name == "request"
                ):
                    roots.add(imported_name)
    return roots


def python_line_shadowed_name_roots(text: str) -> set[str]:
    module = python_parse_diff_line(text)
    if module is None:
        return set()
    roots = python_shadowed_name_roots(module)
    definition_name = python_scope_definition_name(text)
    if definition_name:
        roots.discard(definition_name)
    roots.difference_update(python_scope_boundary_shadowed_names(text))
    roots.difference_update(python_trusted_import_roots(module))
    return roots


def python_prune_shadowed_urlopen_call_names(call_names: set[str], shadowed_roots: set[str]) -> set[str]:
    if not shadowed_roots:
        return call_names
    return {
        call_name
        for call_name in call_names
        if call_name.split(".", 1)[0] not in shadowed_roots
    }


def python_urllib_urlopen_call_names(text: str) -> set[str]:
    call_names: set[str] = set()
    module = python_parse_diff_line(text)
    if module is None:
        if python_line_imports_urllib_urlopen_alias(text):
            call_names.add("urlopen")
        module_alias_match = re.match(r"^\s*import\s+urllib\.request\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
        if module_alias_match:
            call_names.add(f"{module_alias_match.group(1)}.urlopen")
        request_alias_match = re.match(r"^\s*from\s+urllib\s+import\s+request\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
        if request_alias_match:
            call_names.add(f"{request_alias_match.group(1)}.urlopen")
        urllib_alias_match = re.match(r"^\s*import\s+urllib\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
        if urllib_alias_match:
            call_names.add(f"{urllib_alias_match.group(1)}.request.urlopen")
        return call_names
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom):
            if node.module == "urllib.request":
                for alias in node.names:
                    if alias.name == "urlopen":
                        call_names.add(alias.asname or alias.name)
            elif node.module == "urllib":
                for alias in node.names:
                    if alias.name == "request":
                        call_names.add(f"{alias.asname or alias.name}.urlopen")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "urllib.request":
                    call_names.add(f"{alias.asname or alias.name}.urlopen")
                elif alias.name == "urllib":
                    call_names.add(f"{alias.asname or alias.name}.request.urlopen")
    return python_prune_shadowed_urlopen_call_names(
        call_names,
        python_module_shadowed_name_roots(module),
    )


def python_diff_urllib_urlopen_call_names(diff: str) -> dict[str, set[str]]:
    sources_by_path: dict[str, list[str]] = {}
    for diff_line in iter_python_diff_lines_with_context(diff):
        if Path(diff_line.path).suffix.lower() == ".py":
            sources_by_path.setdefault(diff_line.path, []).append(diff_line.text)
    call_names_by_path: dict[str, set[str]] = {}
    for path, lines in sources_by_path.items():
        call_names: set[str] = set()
        for line_text in lines:
            call_names.update(python_urllib_urlopen_call_names(line_text))
        call_names.update(PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.get(path, set()))
        call_names_by_path[path] = call_names
    return call_names_by_path
