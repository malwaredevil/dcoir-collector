def is_python_test_file_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    return normalized.endswith(".py") and (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "/test/" in normalized
        or "/tests/" in normalized
    )


def detect_github_actions_yaml_sentinels(diff: str) -> list[hardened.RiskSentinel]:
    sentinels: list[hardened.RiskSentinel] = []
    seen: set[tuple[str, int, str]] = set()
    for changed_line in hardened.iter_added_diff_lines(diff):
        if Path(changed_line.path).suffix.lower() not in {".yml", ".yaml"}:
            continue
        if hardened.is_comment_only_added_line(changed_line.path, changed_line.text):
            continue
        line_text = changed_line.text
        if GITHUB_ACTIONS_WRITE_PERMISSION_RE.search(line_text):
            key = (changed_line.path, changed_line.line, GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_LABEL)
            if key not in seen:
                seen.add(key)
                sentinels.append(
                    hardened.RiskSentinel(
                        path=changed_line.path,
                        line=changed_line.line,
                        label=GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_LABEL,
                        detail=GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_DETAIL,
                        text=changed_line.text,
                    )
                )
        if GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_RE.search(line_text):
            key = (changed_line.path, changed_line.line, GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_LABEL)
            if key not in seen:
                seen.add(key)
                sentinels.append(
                    hardened.RiskSentinel(
                        path=changed_line.path,
                        line=changed_line.line,
                        label=GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_LABEL,
                        detail=GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_DETAIL,
                        text=changed_line.text,
                    )
                )
    return sentinels


def detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[hardened.RiskSentinel]:
    diff_fixture_added_lines = python_diff_fixture_added_line_keys(diff)
    urllib_urlopen_call_names_by_path = python_diff_urllib_urlopen_call_names(diff)
    shadowed_name_roots_by_line = python_diff_shadowed_name_roots_by_line(diff)
    skipped_test_file_write_labels = {
        FILE_WRITE_PATH_LABEL,
        "Python request-controlled file write",
        "Python writes to a request-controlled filesystem path",
    }
    legacy_sentinels: list[hardened.RiskSentinel] = []
    for sentinel in _original_detect_risk_sentinels(diff, None):
        if (sentinel.path, sentinel.line) in diff_fixture_added_lines:
            continue
        if sentinel.label in skipped_test_file_write_labels:
            if is_python_test_file_path(sentinel.path):
                continue
            if Path(sentinel.path).suffix.lower() == ".py":
                path_constructor_names = set(DEFAULT_PYTHON_PATH_CONSTRUCTORS)
                path_constructor_names.update(PYTHON_PATH_ALIAS_CONTEXT.get(sentinel.path, set()))
                os_module_names = set(DEFAULT_PYTHON_OS_MODULES)
                os_module_names.update(PYTHON_OS_ALIAS_CONTEXT.get(sentinel.path, set()))
                known_call_names = urllib_urlopen_call_names_by_path.get(sentinel.path)
                statement_text = python_diff_statement_text_for_anchor(diff, sentinel.path, sentinel.line, sentinel.text)
                is_known_urlopen = python_line_is_known_urllib_urlopen(
                    statement_text,
                    known_call_names=known_call_names,
                    shadowed_names=shadowed_name_roots_by_line.get(sentinel.path, {}).get(sentinel.line),
                )
                has_known_open_call = is_known_urlopen or python_has_known_file_open_call(
                    statement_text,
                    path_constructor_names,
                    os_module_names,
                )
                if (
                    has_known_open_call
                    and not python_line_has_explicit_file_write_call(
                        statement_text,
                        path_constructor_names,
                        os_module_names,
                        known_call_names=known_call_names,
                        shadowed_names=shadowed_name_roots_by_line.get(sentinel.path, {}).get(sentinel.line),
                    )
                ):
                    # Historical string matching treated parseable, non-writing
                    # ``open`` lookalikes (for example ``urlopen`` and read-only
                    # ``open(..., "r")``) as filesystem writes. Drop only these
                    # lexical false positives and keep other legacy sentinels
                    # unless dedicated replacement coverage already exists.
                    continue
        legacy_sentinels.append(sentinel)

    combined = [
        *detect_python_file_write_path_sentinels(diff),
        *detect_python_dynamic_exec_sentinels(diff),
        *detect_github_actions_yaml_sentinels(diff),
        *legacy_sentinels,
    ]
    deduped: list[hardened.RiskSentinel] = []
    seen: set[tuple[str, int, str]] = set()
    for sentinel in combined:
        key = (sentinel.path, sentinel.line, sentinel.label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentinel)
    return hardened.select_risk_sentinels(deduped, max_anchors)


hardened.detect_risk_sentinels = detect_risk_sentinels
