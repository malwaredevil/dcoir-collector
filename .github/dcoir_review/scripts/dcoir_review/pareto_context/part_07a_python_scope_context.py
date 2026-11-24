def python_scoped_shadowed_name_roots_by_line(source: str) -> dict[int, set[str]]:
    module = ast.parse(source)
    by_line: dict[int, set[str]] = {}
    function_scope_types = (*_PY_SCOPE_FUNCTION_TYPES, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    child_scope_types = (*_PY_SCOPE_FUNCTION_TYPES, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    collect_scope_bindings = _python_scope_collect_bindings

    infos: dict[ast.AST, dict[str, Any]] = {module: collect_scope_bindings(module)}
    parents: dict[ast.AST, ast.AST | None] = {module: None}

    def register_scopes(tree: ast.AST, current_scope: ast.AST) -> None:
        for child in ast.iter_child_nodes(tree):
            if isinstance(child, child_scope_types):
                infos[child] = collect_scope_bindings(child)
                parents[child] = current_scope
                register_scopes(child, child)
            else:
                register_scopes(child, current_scope)

    register_scopes(module, module)

    def lexical_parent(node: ast.AST) -> ast.AST | None:
        parent = parents.get(node)
        while isinstance(parent, ast.ClassDef):
            parent = parents.get(parent)
        return parent

    latest_binding = _python_scope_latest_binding

    def nearest_nonlocal_owner(node: ast.AST, name: str) -> ast.AST | None:
        return _python_scope_nearest_nonlocal_owner(node, name, infos, module, lexical_parent)

    def resolve_trusted_targets(
        node: ast.AST,
        name: str,
        line: int | None = None,
        seen: set[tuple[int, str]] | None = None,
        before_sequence: int | None = None,
    ) -> set[str]:
        seen = set(seen or ())
        key = (id(node), name)
        if key in seen:
            return set()
        seen.add(key)
        info = infos[node]
        if node is not module and name in info['globals']:
            return resolve_trusted_targets(module, name, None, seen)
        if node is not module and name in info['nonlocals']:
            owner = nearest_nonlocal_owner(node, name)
            return resolve_trusted_targets(owner, name, None, seen) if owner is not None else set()
        event = latest_binding(info, name, line, before_sequence)
        if event is not None:
            return set(event[2] or ())
        if name in info['local_bindings']:
            if node is module or isinstance(node, function_scope_types):
                return set()
        parent = lexical_parent(node)
        if parent is None:
            return set()
        return resolve_trusted_targets(parent, name, None, seen)

    trusted_assignment_targets = {'urllib', 'urllib.request', 'urllib.request.urlopen'}
    changed = True
    while changed:
        changed = False
        for node, info in infos.items():
            for line, sequence, target_name, value_path in info.get('alias_assignments', []):
                events = info['binding_events'].get(target_name, [])
                current = next((event for event in events if event[0] == line and event[1] == sequence), None)
                if current is None or current[2] is not None:
                    continue
                value_root, dot, suffix = value_path.partition('.')
                base_targets = resolve_trusted_targets(
                    node,
                    value_root,
                    line,
                    before_sequence=sequence,
                )
                canonical = {f'{base}.{suffix}' if dot and suffix else base for base in base_targets}
                promoted = canonical & trusted_assignment_targets
                if not promoted:
                    continue
                info['binding_events'][target_name] = [
                    (event[0], event[1], set(promoted)) if event[0] == line and event[1] == sequence else event
                    for event in events
                ]
                info['trusted_alias_targets'].setdefault(target_name, set()).update(promoted)
                changed = True

    alias_sources = _python_scope_alias_sources(infos)
    submodule_import_binding_keys = _python_scope_submodule_import_binding_keys(infos)
    guaranteed_binding_keys = _python_scope_guaranteed_binding_keys(infos)

    global_shadowed_roots: set[str] = set()
    for node, info in infos.items():
        if node is module:
            continue
        for name in info['globals']:
            event = latest_binding(info, name, None)
            if event is not None and event[2] is None:
                global_shadowed_roots.add(name)

    def canonical_mutation_paths(node: ast.AST, path: str, line: int, sequence: int | None = None) -> set[str]:
        root, dot, suffix = path.partition('.')
        targets = resolve_trusted_targets(node, root, line, before_sequence=sequence)
        return {f'{target}.{suffix}' if dot and suffix else target for target in targets}

    all_alias_names = {name for info in infos.values() for name in info['trusted_alias_targets']}

    def qualified_events() -> list[tuple[int, int, ast.AST, str, bool]]:
        found = []
        for source_node, info in infos.items():
            for line, sequence, mutation, value_path, restoration_guaranteed, statement_id in info['attribute_mutations']:
                for target in canonical_mutation_paths(source_node, mutation, line, sequence):
                    if target not in {'urllib.request', 'urllib.request.urlopen'}:
                        continue
                    restored = target in _python_scope_guaranteed_restoration_targets(source_node, value_path, line, sequence, infos, module, function_scope_types, lexical_parent, nearest_nonlocal_owner, guaranteed_binding_keys)
                    found.append(
                        (line, sequence, source_node, target, restored, restoration_guaranteed, statement_id)
                    )
        return _python_scope_finalize_restoration_guarantees(found)

    mutation_events = qualified_events()
    eager_nodes = {module, *(node for node in infos if isinstance(node, ast.ClassDef))}

    def trusted_binding_is_shadowed(
        node: ast.AST,
        name: str,
        event: tuple[int, int, set[str] | None],
        seen: set[tuple[int, str, int, int]] | None = None,
    ) -> bool:
        targets = set(event[2] or ())
        if not targets & {'urllib.request', 'urllib.request.urlopen'}:
            return False
        event_key = (id(node), name, event[0], event[1])
        seen = set(seen or ())
        if event_key in seen:
            return True
        seen.add(event_key)
        state = _python_scope_mutation_state(mutation_events, eager_nodes, event[0], event[1])
        if node not in eager_nodes:
            state.update(_python_scope_mutation_state(mutation_events, {node}, event[0], event[1]))
        value_path = alias_sources.get(event_key)
        if event_key in submodule_import_binding_keys:
            return 'urllib.request.urlopen' in state
        if value_path:
            value_root, dot, _suffix = value_path.partition('.')
            source = _python_scope_binding_event_owner(
                node, value_root, event[0], event[1], infos, module,
                function_scope_types, lexical_parent, nearest_nonlocal_owner
            )
            if source is not None and trusted_binding_is_shadowed(
                source[0], value_root, source[1], seen
            ):
                return True
            if not dot:
                return False
            root_targets = resolve_trusted_targets(
                node, value_root, event[0], before_sequence=event[1]
            )
            return _python_scope_alias_source_shadowed(value_path, root_targets, state)
        if 'urllib.request' in targets:
            return 'urllib.request' in state
        return bool(state & {'urllib.request', 'urllib.request.urlopen'})

    mutation_events = _python_scope_demote_shadowed_mutation_roots(infos, qualified_events, trusted_binding_is_shadowed)
    while True:
        mutation_events = qualified_events()
        shadowed_binding_keys = _python_scope_shadowed_binding_keys(infos, trusted_binding_is_shadowed)
        if not _python_scope_demote_binding_keys(infos, shadowed_binding_keys):
            break
    mutation_events = qualified_events()
    deferred_events = _python_scope_deferred_mutations(mutation_events, eager_nodes)

    def apply_qualified_shadow_state(active: set[str], node: ast.AST, line: int | None) -> set[str]:
        state = _python_scope_mutation_state(
            mutation_events, eager_nodes, line if node in eager_nodes else None
        )
        if node is module and line is not None:
            state.update(path for start, path in deferred_events if start and start <= line)
        elif node is not module:
            state.update(path for _start, path in deferred_events)
        for name in all_alias_names:
            targets = resolve_trusted_targets(node, name, line)
            if 'urllib.request.urlopen' in state and targets & {'urllib', 'urllib.request'}:
                active.add(name)
            elif 'urllib.request' in state and 'urllib' in targets:
                active.add(name)
        return active

    nonlocal_rebounds: dict[ast.AST, set[str]] = {node: set() for node in infos}
    for node, info in infos.items():
        if node is module:
            continue
        for name in info['nonlocals']:
            event = latest_binding(info, name, None)
            if event is not None and event[2] is None:
                owner = nearest_nonlocal_owner(node, name)
                if owner is not None:
                    nonlocal_rebounds[owner].add(name)

    def apply_local_bindings(
        active: set[str], node: ast.AST, line: int | None, *, function_unbound_is_shadowed: bool
    ) -> set[str]:
        info = infos[node]
        for name in info['local_bindings'] - (info['globals'] | info['nonlocals']):
            event = latest_binding(info, name, line)
            if event is None:
                if function_unbound_is_shadowed:
                    active.add(name)
                continue
            if event[2] is None:
                active.add(name)
            else:
                active.discard(name)
        return active

    def module_line_state(line: int | None) -> set[str]:
        active: set[str] = set()
        apply_local_bindings(active, module, line, function_unbound_is_shadowed=True)
        if line is None:
            active.update(global_shadowed_roots)
        return apply_qualified_shadow_state(active, module, line)

    module_final_state = module_line_state(None)
    final_cache: dict[ast.AST, set[str]] = {module: set(module_final_state)}

    def scope_final_state(node: ast.AST) -> set[str]:
        if node in final_cache:
            return set(final_cache[node])
        info = infos[node]
        parent = lexical_parent(node)
        active = scope_final_state(parent) if parent is not None else set(module_final_state)
        for name in info['globals']:
            if name in module_final_state:
                active.add(name)
            else:
                active.discard(name)
        apply_local_bindings(
            active,
            node,
            None,
            function_unbound_is_shadowed=isinstance(node, function_scope_types),
        )
        active.update(nonlocal_rebounds[node])
        apply_qualified_shadow_state(active, node, None)
        final_cache[node] = set(active)
        return active

    def scope_line_state(node: ast.AST, line: int) -> set[str]:
        if node is module:
            return module_line_state(line)
        info = infos[node]
        parent = lexical_parent(node)
        active = scope_final_state(parent) if parent is not None else set(module_final_state)
        for name in info['globals']:
            if name in module_final_state:
                active.add(name)
            else:
                active.discard(name)
        apply_local_bindings(
            active,
            node,
            line,
            function_unbound_is_shadowed=isinstance(node, function_scope_types),
        )
        active.update(nonlocal_rebounds[node])
        return apply_qualified_shadow_state(active, node, line)

    max_line = int(getattr(module, 'end_lineno', 0) or len(source.splitlines()))
    for line in range(1, max_line + 1):
        by_line[line] = module_line_state(line)

    scoped_nodes = [node for node in infos if node is not module]
    for node in sorted(scoped_nodes, key=lambda item: (_python_scope_depth(item, parents), int(getattr(item, 'lineno', 0) or 0))):
        start = int(getattr(node, 'lineno', 0) or 0)
        end = int(getattr(node, 'end_lineno', start) or start)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            parts = ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt])
            parts += [generator.target for generator in node.generators]
            parts += [clause for generator in node.generators for clause in generator.ifs]
            parts += [generator.iter for generator in node.generators[1:]]
            for part in parts:
                first = int(getattr(part, 'lineno', start) or start)
                last = int(getattr(part, 'end_lineno', first) or first)
                for line in range(first, last + 1):
                    by_line[line] = scope_line_state(node, line)
            continue
        if isinstance(node, ast.Lambda):
            for line in range(start, end + 1):
                by_line[line] = scope_line_state(node, line)
            continue
        body = getattr(node, 'body', [])
        if not body:
            continue
        body_start = min(int(getattr(stmt, 'lineno', start) or start) for stmt in body)
        exec_parent = parents.get(node)
        for line in _python_scope_header_lines(node, body_start):
            by_line[line] = scope_line_state(exec_parent, line) if exec_parent is not None else module_line_state(line)
        for line in range(body_start, end + 1):
            by_line[line] = scope_line_state(node, line)

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
