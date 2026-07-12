def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    if kind == PYTHON_ARCHIVE_EXTRACT:
        quoted = shlex.quote(path)
        return f"python3 -m py_compile {quoted}\n" + v8._py_here_doc(path, "assert '.extractall(' not in text\nassert 'extractall(' not in text")
    if kind == PYTHON_PATH_WRITE:
        quoted = shlex.quote(path)
        body = (
            "import re\n"
            "pathlib_write = re.search(r'\\.(write_text|write_bytes)\\s*\\(', text)\n"
            "open_write = re.search(r'\\bopen\\s*\\([^\\n)]*,\\s*[\\'\\\"][^\\'\\\"]*(?:[wax]|r\\+)[^\\'\\\"]*[\\'\\\"]', text) or re.search(r'\\bopen\\s*\\([^\\n)]*\\bmode\\s*=\\s*[\\'\\\"][^\\'\\\"]*(?:[wax]|r\\+)[^\\'\\\"]*[\\'\\\"]', text)\n"
            "path_open_write = re.search(r'\\.open\\s*\\(\\s*(?:mode\\s*=\\s*)?[\\'\\\"][^\\'\\\"]*(?:[wax]|r\\+)[^\\'\\\"]*[\\'\\\"]', text)\n"
            "assert not (pathlib_write or open_write or path_open_write)"
        )
        return f"python3 -m py_compile {quoted}\n" + v8._py_here_doc(path, body)
    return v10._validation_for_key(kind, path, line)


def _fallback_for_sentinel(hardened: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    path, line, kind = key
    line_text = str(getattr(sentinel, "text", "") or "")
    if kind == PYTHON_ARCHIVE_EXTRACT:
        fallback = {
            "title": "Archive extraction trusts archive paths",
            "severity": "high",
            "confidence": 0.98,
            "path": path,
            "line": line,
            "body": "This extraction can write files outside the destination if the archive contains absolute paths or parent traversal. Validate every archive member before extraction.",
            "validation": _validation_for_key(kind, path, line),
            "fix_guidance": {
                "language": "python",
                "notes": "Validate archive member paths before extracting, or use a safe extraction helper.",
                "validation": _validation_for_key(kind, path, line),
            },
        }
    elif kind == PYTHON_PATH_WRITE:
        fallback = {
            "title": "Request-controlled path can be written",
            "severity": "high",
            "confidence": 0.96,
            "path": path,
            "line": line,
            "body": "This write path can be influenced by request data. Resolve it under an allowlisted base directory and reject traversal before writing.",
            "validation": _validation_for_key(kind, path, line),
            "fix_guidance": {
                "language": "python",
                "notes": "Resolve and validate the destination path before writing.",
                "validation": _validation_for_key(kind, path, line),
            },
        }
    else:
        fallback = v10._fallback_for_sentinel(hardened, sentinel, config)
    fallback["_risk_sentinel_key"] = [path, line, kind]
    fallback["_risk_sentinel_kind"] = kind
    fallback["_anchored_line_text"] = line_text
    return fallback


def _sentinel_record(
    sentinel: Any,
    reason: str,
    required: set[SentinelKey],
    selected: set[SentinelKey],
    limit: int,
) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    coverage = _coverage_key(key)
    bucket = "hard-required" if coverage in required else "optional-pressure" if key[2].startswith("k8s_") else "high-risk"
    actual_reason = reason
    if reason == "auto":
        actual_reason = "duplicate_covered" if coverage in selected else "omitted_due_to_inline_budget" if len(selected) >= limit else "not_selected"
    return {
        "path": key[0],
        "line": key[1],
        "kind": key[2],
        "priority_bucket": bucket,
        "reason": actual_reason,
        "label": str(getattr(sentinel, "label", "") or ""),
        "detail": str(getattr(sentinel, "detail", "") or "")[:240],
        "text": str(getattr(sentinel, "text", "") or "")[:240],
    }


def _record_from_key_text(key_text: str, reason: str) -> dict[str, Any]:
    try:
        path_line, kind = str(key_text).rsplit(" ", 1)
        path, line_text = path_line.rsplit(":", 1)
        line = int(line_text)
    except (ValueError, TypeError):
        path, line, kind = str(key_text), 0, ""
    return {
        "path": path,
        "line": line,
        "kind": kind,
        "priority_bucket": "hard-required",
        "reason": reason,
        "label": "",
        "detail": "",
        "text": "",
    }


def _select_once(
    hardened: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    required_all = _required_sentinels(hardened, risk_sentinels)
    required_targets, duplicate_covered = _coalesce_required(required_all)
    expected = _expected_by_line(hardened, risk_sentinels)
    required_coverage = {_coverage_key(_sentinel_key(item)) for item in required_targets}

    candidates, dropped = _dedupe([item for item in findings if isinstance(item, dict)], expected)
    by_key = {_postable_key(item): item for item in candidates}
    for sentinel in required_targets:
        key = _sentinel_key(sentinel)
        if key not in by_key:
            fallback = _fallback_for_sentinel(hardened, sentinel, config)
            normalized = v5._normalize_comment_finding(fallback)
            normalized["_risk_sentinel_key"] = list(key)
            normalized["_risk_sentinel_kind"] = key[2]
            normalized["_anchored_line_text"] = str(getattr(sentinel, "text", "") or "")
            by_key[key] = normalized
            candidates.append(normalized)

    selected: list[dict[str, Any]] = []
    selected_coverage: set[SentinelKey] = set()
    for sentinel in _balanced_required_order(required_targets):
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in selected_coverage or len(selected) >= limit:
            continue
        item = by_key.get(key)
        if not item:
            continue
        selected.append(item)
        selected_coverage.add(coverage)

    for item in sorted(candidates, key=_spare_priority):
        key = _postable_key(item)
        coverage = _coverage_key(key)
        if len(selected) >= limit:
            break
        if coverage in selected_coverage or not key[2]:
            continue
        selected.append(item)
        selected_coverage.add(coverage)

    for item in selected:
        path, line, kind = _postable_key(item)
        validation = _validation_for_key(kind, path, line)
        if validation:
            item["validation"] = validation
            guidance = item.get("fix_guidance")
            if isinstance(guidance, dict):
                guidance["validation"] = validation
        v10._scrub_shell_pipe_wording(item)

    final_invalid = [_key_text(_postable_key(item)) for item in selected if _semantic_mismatch(item, expected)]
    selected_keys = [_postable_key(item) for item in selected]
    selected_coverage = {_coverage_key(key) for key in selected_keys}
    omitted_required = [
        _sentinel_record(item, "auto", required_coverage, selected_coverage, limit)
        for item in required_targets
        if _coverage_key(_sentinel_key(item)) not in selected_coverage
    ]
    optional_high_risk = [
        _sentinel_record(item, "auto", required_coverage, selected_coverage, limit)
        for item in risk_sentinels
        if _coverage_key(_sentinel_key(item)) not in selected_coverage
        and _coverage_key(_sentinel_key(item)) not in required_coverage
        and _sentinel_key(item)[2]
    ]
    metadata = {
        "version": "v11",
        "hard_required_count": len(required_all),
        "coalesced_required_count": len(required_targets),
        "final_postable_count": len(selected),
        "inline_limit": limit,
        "partial_overflow": bool(omitted_required or optional_high_risk),
        "overflow_required_count": len(omitted_required),
        "overflow_optional_high_risk_count": len(optional_high_risk),
        "selected_keys": [_key_text(key) for key in selected_keys],
        "duplicate_covered_sentinels": duplicate_covered[:80],
        "dropped_invalid_or_duplicate_candidates": dropped[:120],
        "final_invalid_selected_keys": final_invalid,
        "omitted_required_sentinels": omitted_required[:80],
        "omitted_optional_high_risk_sentinels": optional_high_risk[:80],
        "omitted_sentinels": (omitted_required + optional_high_risk)[:80],
        "final_uncovered": [f"{item.get('path')}:{item.get('line')} {item.get('kind')}" for item in omitted_required],
    }
    return selected, metadata
