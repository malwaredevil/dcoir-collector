def _python_scope_cross_binding_stable(
    owner, name, event, targets, infos, module, function_scope_types,
    lexical_parent, nearest_nonlocal_owner, alias_sources, seen=None,
):
    key = (id(owner), name, event[0], event[1])
    seen = set(seen or ())
    if key in seen:
        return False
    seen.add(key)

    value_path = alias_sources.get(key)
    if value_path:
        root, dot, suffix = value_path.partition('.')
        source = _python_scope_binding_event_owner(
            owner, root, event[0], event[1], infos, module, function_scope_types,
            lexical_parent, nearest_nonlocal_owner,
        )
        if source is None:
            return False
        source_targets = set(source[1][2] or ())
        projected = {f'{target}.{suffix}' if dot and suffix else target for target in source_targets}
        if projected != targets or not _python_scope_cross_binding_stable(
            source[0], root, source[1], source_targets, infos, module, function_scope_types,
            lexical_parent, nearest_nonlocal_owner, alias_sources, seen,
        ):
            return False

    for later in infos[owner]['binding_events'].get(name, []):
        if later[:2] <= event[:2]:
            continue
        later_targets = set(later[2] or ())
        later_key = (id(owner), name, later[0], later[1])
        if later_targets != targets:
            return False
        if later_key in alias_sources and not _python_scope_cross_binding_stable(
            owner, name, later, targets, infos, module, function_scope_types,
            lexical_parent, nearest_nonlocal_owner, alias_sources, seen,
        ):
            return False

    for writer, writer_info in infos.items():
        if writer is owner:
            continue
        writes_owner = (
            name in writer_info['globals'] and owner is module
        ) or (
            name in writer_info['nonlocals']
            and nearest_nonlocal_owner(writer, name) is owner
        )
        if not writes_owner:
            continue
        for writer_event in writer_info['binding_events'].get(name, []):
            writer_targets = set(writer_event[2] or ())
            if writer_targets != targets or not _python_scope_cross_binding_stable(
                writer, name, writer_event, targets, infos, module, function_scope_types,
                lexical_parent, nearest_nonlocal_owner, alias_sources, seen,
            ):
                return False
    return True


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
    has_nested_nonlocal_writer = any(
        writer is not source[0]
        and value_path in writer_info['nonlocals']
        and nearest_nonlocal_owner(writer, value_path) is source[0]
        for writer, writer_info in infos.items()
    )
    if (source[0] is not source_node or has_nested_nonlocal_writer) and not _python_scope_cross_binding_stable(
        source[0], value_path, source[1], source_targets, infos, module, function_scope_types,
        lexical_parent, nearest_nonlocal_owner, _python_scope_alias_sources(infos),
    ):
        return set()
    return source_targets
