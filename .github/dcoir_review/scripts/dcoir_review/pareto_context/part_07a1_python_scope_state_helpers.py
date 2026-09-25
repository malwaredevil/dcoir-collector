def _python_scope_statement_may_exit(statement: ast.AST) -> bool:
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False
    found = False

    class Visitor(ast.NodeVisitor):
        def visit_Return(self, _node: ast.Return) -> None:
            nonlocal found
            found = True

        def visit_Raise(self, _node: ast.Raise) -> None:
            nonlocal found
            found = True

        def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, _node: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, _node: ast.Lambda) -> None:
            return

    Visitor().visit(statement)
    return found


def _python_scope_guaranteed_direct_statements(node: ast.AST) -> set[int]:
    guaranteed: set[int] = set()
    reaches_following_on_all_paths = True
    for statement in list(getattr(node, 'body', []) or []):
        if reaches_following_on_all_paths:
            guaranteed.add(id(statement))
        if reaches_following_on_all_paths and _python_scope_statement_may_exit(statement):
            reaches_following_on_all_paths = False
    return guaranteed


def _python_scope_latest_binding(
    info: dict[str, Any],
    name: str,
    line: int | None,
    before_sequence: int | None = None,
) -> tuple[int, int, set[str] | None] | None:
    events = list(info['binding_events'].get(name, []))
    if line is not None:
        events = [
            event for event in events
            if event[0] < line or (event[0] == line and (before_sequence is None or event[1] < before_sequence))
        ]
    return max(events, key=lambda event: (event[0], event[1])) if events else None


def _python_scope_mutation_state(events, nodes, line=None, before=None):
    state = set()
    for event in events:
        event_line, seq, event_node, path, restored = event[:5]
        if event_node not in nodes:
            continue
        if line is not None and (event_line > line or (event_line == line and before is not None and seq >= before)):
            continue
        (state.discard if restored else state.add)(path)
    return state


def _python_scope_deferred_mutations(events, excluded):
    states = {}
    for event in events:
        _line, _seq, node, path, restored = event[:5]
        restoration_guaranteed = bool(event[5]) if len(event) > 5 else True
        if node in excluded:
            continue
        if restored and not restoration_guaranteed:
            continue
        state = states.setdefault(node, set())
        (state.discard if restored else state.add)(path)
    return [(int(getattr(node, 'lineno', 0) or 0), path) for node, state in states.items() for path in state]


def _python_scope_alias_source_shadowed(
    value_path: str,
    root_targets: set[str],
    mutation_state: set[str],
) -> bool:
    _root, dot, suffix = value_path.partition('.')
    if not dot:
        return False
    if 'urllib.request' in mutation_state and 'urllib' in root_targets:
        if suffix == 'request' or suffix.startswith('request.'):
            return True
    if 'urllib.request.urlopen' in mutation_state:
        if 'urllib' in root_targets and (suffix == 'request.urlopen' or suffix.startswith('request.urlopen.')):
            return True
        if 'urllib.request' in root_targets and (suffix == 'urlopen' or suffix.startswith('urlopen.')):
            return True
    return False


def _python_scope_header_lines(node: ast.AST, body_start: int) -> set[int]:
    starts = [int(getattr(node, 'lineno', 0) or 0)]
    starts.extend(int(getattr(item, 'lineno', 0) or 0) for item in getattr(node, 'decorator_list', []))
    positive = [line for line in starts if line > 0]
    if not positive:
        return set()
    start = min(positive)
    return set(range(start, max(start, body_start - 1) + 1))


def _python_scope_depth(node: ast.AST, parents: dict[ast.AST, ast.AST | None]) -> int:
    value = 0
    parent = parents.get(node)
    while parent is not None:
        value += 1
        parent = parents.get(parent)
    return value


def python_assignment_urllib_urlopen_call_names(text: str, base_call_names: set[str] | None = None) -> set[str]:
    """Return possible urlopen call names introduced by simple assignment aliases."""
    try:
        module = ast.parse(text)
    except (SyntaxError, ValueError, TypeError):
        return set()
    calls = set(base_call_names or ())
    aliases: list[tuple[str, str]] = []
    for item in ast.walk(module):
        value = None
        targets: list[ast.AST] = []
        if isinstance(item, ast.Assign):
            value = item.value
            targets = list(item.targets)
        elif isinstance(item, ast.AnnAssign) and item.value is not None:
            value = item.value
            targets = [item.target]
        elif isinstance(item, ast.NamedExpr):
            value = item.value
            targets = [item.target]
        if not isinstance(value, (ast.Name, ast.Attribute)):
            continue
        value_path = _python_scope_attribute_path(value)
        if not value_path:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                aliases.append((target.id, value_path))
    changed = True
    while changed:
        changed = False
        for target, value_path in aliases:
            candidates: set[str] = set()
            if value_path in calls:
                candidates.add(target)
            if f'{value_path}.urlopen' in calls:
                candidates.add(f'{target}.urlopen')
            if f'{value_path}.request.urlopen' in calls:
                candidates.add(f'{target}.request.urlopen')
            new = candidates - calls
            if new:
                calls.update(new)
                changed = True
    return calls - set(base_call_names or ())


def _python_scope_nearest_nonlocal_owner(
    node: ast.AST,
    name: str,
    infos: dict[ast.AST, dict[str, Any]],
    module: ast.AST,
    lexical_parent: Any,
) -> ast.AST | None:
    parent = lexical_parent(node)
    while parent is not None and parent is not module:
        info = infos[parent]
        local_names = info['local_bindings'] - (info['globals'] | info['nonlocals'])
        if name in local_names:
            return parent
        parent = lexical_parent(parent)
    return None


def _python_scope_binding_event_owner(
    node: ast.AST,
    name: str,
    line: int | None,
    before_sequence: int | None,
    infos: dict[ast.AST, dict[str, Any]],
    module: ast.AST,
    function_scope_types: tuple[type, ...],
    lexical_parent: Any,
    nearest_nonlocal_owner: Any,
    seen: set[tuple[int, str]] | None = None,
) -> tuple[ast.AST, tuple[int, int, set[str] | None]] | None:
    seen = set(seen or ())
    key = (id(node), name)
    if key in seen:
        return None
    seen.add(key)
    info = infos[node]
    cross_scope_line = int(getattr(node, 'lineno', 0) or 0) or line
    if node is not module and name in info['globals']:
        return _python_scope_binding_event_owner(
            module, name, cross_scope_line, None, infos, module, function_scope_types,
            lexical_parent, nearest_nonlocal_owner, seen
        )
    if node is not module and name in info['nonlocals']:
        owner = nearest_nonlocal_owner(node, name)
        return (
            _python_scope_binding_event_owner(
                owner, name, cross_scope_line, None, infos, module, function_scope_types,
                lexical_parent, nearest_nonlocal_owner, seen
            )
            if owner is not None else None
        )
    event = _python_scope_latest_binding(info, name, line, before_sequence)
    if event is not None:
        return node, event
    if name in info['local_bindings'] and (node is module or isinstance(node, function_scope_types)):
        return None
    parent = lexical_parent(node)
    return (
        _python_scope_binding_event_owner(
            parent, name, cross_scope_line, None, infos, module, function_scope_types,
            lexical_parent, nearest_nonlocal_owner, seen
        )
        if parent is not None else None
    )


def _python_scope_alias_sources(infos: dict[ast.AST, dict[str, Any]]) -> dict[tuple[int, str, int, int], str]:
    return {
        (id(scope_node), target_name, line, sequence): value_path
        for scope_node, info in infos.items()
        for line, sequence, target_name, value_path in info.get('alias_assignments', [])
    }


def _python_scope_shadowed_binding_keys(infos: dict[ast.AST, dict[str, Any]], predicate: Any) -> set[tuple[int, str, int, int]]:
    return {
        (id(node), name, event[0], event[1])
        for node, info in infos.items()
        for name, events in info['binding_events'].items()
        for event in events
        if predicate(node, name, event)
    }


def _python_scope_direct_restoration_guaranteed(node: ast.AST, mutation_line: int, restoration_line: int) -> bool:
    body = list(getattr(node, 'body', []) or [])
    mutation_index = next(
        (index for index, statement in enumerate(body) if int(getattr(statement, 'lineno', 0) or 0) == mutation_line),
        None,
    )
    restoration_index = next(
        (index for index, statement in enumerate(body) if int(getattr(statement, 'lineno', 0) or 0) == restoration_line),
        None,
    )
    return (
        mutation_index is not None
        and restoration_index is not None
        and restoration_index == mutation_index + 1
    )


def _python_scope_finalize_restoration_guarantees(events):
    ordered = sorted(events, key=lambda event: (event[0], event[1]))
    active_mutations = {}
    finalized = []
    for event in ordered:
        line, sequence, node, path, restored = event[:5]
        restoration_candidate_safe = bool(event[5]) if len(event) > 5 else True
        key = (id(node), path)
        guaranteed = False
        if restored:
            previous = active_mutations.get(key)
            guaranteed = bool(
                restoration_candidate_safe
                and previous
                and _python_scope_direct_restoration_guaranteed(node, previous[0], line)
            )
            if guaranteed:
                active_mutations.pop(key, None)
        else:
            active_mutations[key] = (line, sequence)
        finalized.append((line, sequence, node, path, restored, guaranteed))
    return finalized


def _python_scope_demote_binding_keys(
    infos: dict[ast.AST, dict[str, Any]],
    keys: set[tuple[int, str, int, int]],
) -> bool:
    changed = False
    for node, info in infos.items():
        for name, events in list(info['binding_events'].items()):
            updated = []
            for event in events:
                key = (id(node), name, event[0], event[1])
                if key in keys and event[2] is not None:
                    updated.append((event[0], event[1], None))
                    changed = True
                else:
                    updated.append(event)
            info['binding_events'][name] = updated
    return changed


def _python_scope_demote_shadowed_mutation_roots(infos, qualified_events, predicate):
    mutation_alias_names = {
        mutation.partition('.')[0]
        for info in infos.values()
        for _line, _sequence, mutation, _value_path, _safe in info['attribute_mutations']
    }
    while True:
        mutation_events = qualified_events()
        keys = _python_scope_shadowed_binding_keys(
            infos, lambda node, name, event: name in mutation_alias_names and predicate(node, name, event)
        )
        if not _python_scope_demote_binding_keys(infos, keys):
            return mutation_events


def _python_scope_submodule_import_binding_keys(infos: dict[ast.AST, dict[str, Any]]) -> set[tuple[int, str, int, int]]:
    return {
        (id(scope_node), name, line, sequence)
        for scope_node, info in infos.items()
        for name, line, sequence in info.get('submodule_import_binding_keys', set())
    }


def _python_scope_guaranteed_binding_keys(infos: dict[ast.AST, dict[str, Any]]) -> set[tuple[int, str, int, int]]:
    return {
        (id(scope_node), name, line, sequence)
        for scope_node, info in infos.items()
        for name, line, sequence in info.get('guaranteed_binding_keys', set())
    }


def _python_scope_guaranteed_restoration_targets(
    source_node,
    value_path,
    line,
    sequence,
    infos,
    module,
    function_scope_types,
    lexical_parent,
    nearest_nonlocal_owner,
    guaranteed_binding_keys,
):
    if not value_path or '.' in value_path:
        return set()
    source = _python_scope_binding_event_owner(
        source_node,
        value_path,
        line,
        sequence,
        infos,
        module,
        function_scope_types,
        lexical_parent,
        nearest_nonlocal_owner,
    )
    if source is None:
        return set()
    key = (id(source[0]), value_path, source[1][0], source[1][1])
    if key not in guaranteed_binding_keys:
        return set()
    source_targets = set(source[1][2] or ())
    if source[0] is not source_node:
        later_events = [
            event for event in infos[source[0]]['binding_events'].get(value_path, [])
            if event[:2] > source[1][:2]
        ]
        if any(set(event[2] or ()) != source_targets for event in later_events):
            return set()
        for writer, writer_info in infos.items():
            if writer is source[0]:
                continue
            writes_owner = (
                value_path in writer_info['globals'] and source[0] is module
            ) or (
                value_path in writer_info['nonlocals']
                and nearest_nonlocal_owner(writer, value_path) is source[0]
            )
            if writes_owner and any(
                set(event[2] or ()) != source_targets
                for event in writer_info['binding_events'].get(value_path, [])
            ):
                return set()
    return source_targets
