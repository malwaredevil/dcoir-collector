def _patch_detect(owner: Any, sentinel_owner: Any | None = None) -> None:
    original = getattr(owner, "_dcoir_required_v16_original_detect_risk_sentinels", None)
    if original is None:
        original = getattr(owner, "detect_risk_sentinels", None)
        owner._dcoir_required_v16_original_detect_risk_sentinels = original
    if not callable(original):
        return

    def detect_risk_sentinels(diff: str, *args: Any, **kwargs: Any) -> list[Any]:
        path_alias_context = {"Path", "pathlib.Path"}
        os_alias_context = {"os"}
        PYTHON_PATH_ALIAS_CONTEXT.clear()
        PYTHON_OS_ALIAS_CONTEXT.clear()
        PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.clear()
        for source in (sentinel_owner, owner):
            path_context = getattr(source, "PYTHON_PATH_ALIAS_CONTEXT", None)
            if isinstance(path_context, dict):
                for key, value in path_context.items():
                    if isinstance(value, set):
                        PYTHON_PATH_ALIAS_CONTEXT[str(key)] = set(value)
            os_context = getattr(source, "PYTHON_OS_ALIAS_CONTEXT", None)
            if isinstance(os_context, dict):
                for key, value in os_context.items():
                    if isinstance(value, set):
                        PYTHON_OS_ALIAS_CONTEXT[str(key)] = set(value)
            urlopen_context = getattr(source, "PYTHON_URLLIB_URLOPEN_CALL_CONTEXT", None)
            if isinstance(urlopen_context, dict):
                for key, value in urlopen_context.items():
                    if isinstance(value, set):
                        PYTHON_URLLIB_URLOPEN_CALL_CONTEXT[str(key)] = set(value)
        diff_path_aliases, diff_os_aliases = _python_diff_import_alias_context(diff)
        for path, names in diff_path_aliases.items():
            PYTHON_PATH_ALIAS_CONTEXT.setdefault(path, set()).update(names)
        for path, names in diff_os_aliases.items():
            PYTHON_OS_ALIAS_CONTEXT.setdefault(path, set()).update(names)
        try:
            sentinels = list(original(diff, *args, **kwargs))
        except TypeError:
            sentinels = list(original(diff))
        urllib_urlopen_call_names_by_path = _python_diff_urllib_urlopen_call_names(diff)
        for path, names in urllib_urlopen_call_names_by_path.items():
            PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.setdefault(path, set()).update(names)
        filtered_sentinels: list[Any] = []
        for item in sentinels:
            path = str(getattr(item, "path", "") or "")
            text = str(getattr(item, "text", "") or "")
            kind = _sentinel_key(item)[2]
            original_kind = _ORIGINAL_V13_SENTINEL_KEY(item)[2]
            if kind == v11.PYTHON_PATH_WRITE or original_kind == v11.PYTHON_PATH_WRITE:
                constructor_names = {"Path", "pathlib.Path"}
                constructor_names.update(PYTHON_PATH_ALIAS_CONTEXT.get(path, set()))
                os_module_names = {"os"}
                os_module_names.update(PYTHON_OS_ALIAS_CONTEXT.get(path, set()))
                if _is_python_test_file(path):
                    continue
                if _python_is_known_urllib_urlopen(
                    text,
                    known_call_names=urllib_urlopen_call_names_by_path.get(path),
                ):
                    continue
                if (
                    Path(path).suffix.lower() == ".py"
                    and _python_has_known_file_open_call(text, constructor_names, os_module_names)
                    and not _python_is_explicit_file_write(text, constructor_names, os_module_names)
                ):
                    continue
            filtered_sentinels.append(item)
        sentinels = filtered_sentinels
        risk_sentinel_type = getattr(owner, "RiskSentinel", None) or getattr(sentinel_owner, "RiskSentinel", None)
        if risk_sentinel_type is None:
            return sentinels
        existing = {_sentinel_key(item) for item in sentinels}
        checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)
        for path, line, text in selection._iter_added_diff_lines(diff):
            if callable(checker) and checker(path, text):
                continue
            kind = _line_kind(path, text)
            if kind not in TRACKED_KINDS and kind not in OPTIONAL_PRESSURE_KINDS:
                continue
            if kind == v11.PYTHON_PATH_WRITE and _is_python_test_file(path):
                continue
            if kind == v11.PYTHON_PATH_WRITE and _python_is_known_urllib_urlopen(
                text,
                known_call_names=PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.get(path, urllib_urlopen_call_names_by_path.get(path)),
            ):
                continue
            constructor_names = set(path_alias_context)
            constructor_names.update(PYTHON_PATH_ALIAS_CONTEXT.get(path, set()))
            os_module_names = set(os_alias_context)
            os_module_names.update(PYTHON_OS_ALIAS_CONTEXT.get(path, set()))
            if kind == v11.PYTHON_PATH_WRITE and not _python_is_explicit_file_write(
                text,
                constructor_names,
                os_module_names,
            ):
                # The wrapped detector already evaluates complete statements. Do not
                # manufacture a path-write sentinel from an incomplete line fragment.
                continue
            key = (path, line, kind)
            if key in existing:
                continue
            title, body, _notes = _template_for_kind(kind)
            sentinels.append(risk_sentinel_type(path=path, line=line, label=title, detail=body, text=text))
            existing.add(key)
        return sentinels

    owner.detect_risk_sentinels = detect_risk_sentinels


def _patch_core_semantics() -> None:
    from dcoir_review import finding_family as v15
    v12.REQUIRED_KINDS = set(getattr(v12, "REQUIRED_KINDS", set())) | CORE_REQUIRED_KINDS
    v13.REQUIRED_KINDS = set(getattr(v13, "REQUIRED_KINDS", set())) | CORE_REQUIRED_KINDS
    v13.TRACKED_HIGH_RISK_KINDS = set(getattr(v13, "TRACKED_HIGH_RISK_KINDS", set())) | TRACKED_KINDS
    v14.SELECTION_KIND_RANK.update({kind: _kind_rank(kind) for kind in CORE_REQUIRED_KINDS | {v10.YAML_TOKEN_TO_PR_URL}})
    v14.FAMILY_ORDER = ("yaml", "python", "powershell", "other", "typescript")
    v15.FAMILY_ORDER = ("yaml", "python", "powershell", "other", "typescript")
    v13._line_kind = _line_kind
    v13._sentinel_key = _sentinel_key
    v13._postable_key = _postable_key
    v13._coverage_key = _coverage_key
    v13._validation_for_key = _validation_for_key
    v13._spare_priority = _candidate_priority
    v14._family = _family
    v14._spare_priority = _candidate_priority
    core._sentinel_key = _sentinel_key
    core._postable_key = _postable_key
    core._coverage_key = _coverage_key
    core._spare_priority = _candidate_priority
    core._validation_for_key = _validation_for_key
    v11._line_kind = _line_kind
    v12._sentinel_key = _sentinel_key
    v12._postable_key = _postable_key
    v12._coverage_key = _coverage_key
    v12._spare_priority = _candidate_priority


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    _patch_core_semantics()
    _patch_detect(module, hardened)
    module.rank_findings_for_required_budget = lambda findings, config: sorted(
        [v5._normalize_comment_finding(item) for item in findings if isinstance(item, dict)],
        key=_candidate_priority,
    )[: max(0, int(getattr(config, "max_inline_comments", 12)))]
    if hardened is not None:
        _patch_detect(hardened)
        hardened.add_risk_sentinel_fallback_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: _select_required_postable(
            hardened, findings, risk_sentinels, config, unanchored_findings
        )
        hardened.enforce_risk_sentinel_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: findings.__setitem__(
            slice(None), _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)
        )
        _patch_review_body_overflow(hardened)
    if base is not None:
        v11._patch_progress_comment(base, hardened)
