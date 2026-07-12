# Continuation of part_01.py, split at the 15KB connector-safe segment size
# limit enforced by dcoir_review_runtime_module_loader_selftest.py. Holds the
# required-sentinel coalescing, dedupe, and balanced-ordering logic that
# builds on the kind-detection helpers defined in part_01.py. Both files
# execute into the same shared namespace, so no re-imports are needed here.


def _coalesce_required(required: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    targets: list[Any] = []
    seen: set[SentinelKey] = set()
    duplicates: list[dict[str, Any]] = []
    for sentinel in sorted(required, key=_sentinel_sort_key):
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in seen:
            duplicates.append(_sentinel_record(sentinel, "duplicate_covered", required=set(), selected=set(), limit=0))
            continue
        seen.add(coverage)
        targets.append(sentinel)
    return targets, duplicates


def _required_sentinels(hardened: Any, risk_sentinels: list[Any]) -> list[Any]:
    required = _base_required_sentinels(hardened, risk_sentinels)
    seen = {_sentinel_key(item) for item in required}
    for sentinel in risk_sentinels:
        key = _sentinel_key(sentinel)
        kind = key[2]
        if kind in {
            v10.YAML_TOKEN_TO_PR_URL,
            v4.YAML_METADATA_SHELL,
            v4.YAML_SHELL_PIPE,
            v4.YAML_PULL_REQUEST_TARGET,
            v4.YAML_UNTRUSTED_CHECKOUT,
            v4.YAML_BROAD_WRITE,
            v9.PYTHON_PICKLE_LOAD,
            v5.PYTHON_YAML_LOAD,
            v5.PYTHON_SHELL_EXEC,
            v5.PYTHON_ENV_TOKEN,
            PYTHON_ARCHIVE_EXTRACT,
            PYTHON_PATH_WRITE,
            v9.PS_DYNAMIC_EXEC,
            v4.PS_ACL,
            v4.PS_PROCESS_LAUNCH,
            v5.PS_ENV_TOKEN,
        } and key not in seen:
            required.append(sentinel)
            seen.add(key)
    return required


def _expected_by_line(hardened: Any, risk_sentinels: list[Any]) -> dict[tuple[str, int], set[str]]:
    expected: dict[tuple[str, int], set[str]] = {}
    for sentinel in _required_sentinels(hardened, risk_sentinels):
        path, line, kind = _sentinel_key(sentinel)
        expected.setdefault((path, line), set()).add(kind)
    return expected


def _semantic_mismatch(finding: dict[str, Any], expected: dict[tuple[str, int], set[str]]) -> bool:
    path = str(finding.get("path", "") or "")
    line = core._line_number(finding.get("line", 0))
    allowed = expected.get((path, line), set())
    if not allowed:
        return False
    explicit = _explicit_kind(finding)
    if explicit and explicit not in allowed:
        return True
    if explicit:
        return False
    title_kinds = _title_kinds(finding)
    if title_kinds and not (title_kinds & allowed):
        return True
    primary = _primary_kind(finding, allowed)
    if not primary:
        return True
    return primary not in allowed


def _dedupe(findings: list[dict[str, Any]], expected: dict[tuple[str, int], set[str]]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: dict[SentinelKey, dict[str, Any]] = {}
    order: list[SentinelKey] = []
    dropped: list[str] = []
    for finding in findings:
        item = v5._normalize_comment_finding(finding)
        key = _postable_key(item)
        if _semantic_mismatch(item, expected):
            dropped.append(f"{key[0]}:{key[1]} expected={','.join(sorted(expected.get((key[0], key[1]), set())))} actual={key[2]}")
            continue
        if not key[2]:
            dropped.append(f"{key[0]}:{key[1]} empty semantic kind")
            continue
        if key not in kept:
            kept[key] = item
            order.append(key)
            continue
        dropped.append(f"{key[0]}:{key[1]} duplicate {key[2]}")
        if (core._severity_rank(item), -core._confidence(item)) < (
            core._severity_rank(kept[key]),
            -core._confidence(kept[key]),
        ):
            kept[key] = item
    return [kept[key] for key in order], dropped


def _spare_priority(finding: dict[str, Any]) -> tuple[int, int, int, float, str, int]:
    path, line, kind = _postable_key(finding)
    optional = "/optional_" in path.lower() or path.rsplit("/", 1)[-1].startswith("optional_")
    family_rank = {"yaml": 0, "powershell": 1, "python": 2, "kubernetes": 4, "other": 5}.get(_family(kind), 5)
    if optional:
        family_rank += 5
    return family_rank, _kind_rank(kind), core._severity_rank(finding), -core._confidence(finding), path, line


def _bucket_required_targets(targets: list[Any]) -> dict[str, list[Any]]:
    buckets: dict[str, list[Any]] = {}
    for sentinel in targets:
        buckets.setdefault(_family(_sentinel_key(sentinel)[2]), []).append(sentinel)
    for family, values in buckets.items():
        buckets[family] = sorted(values, key=_sentinel_sort_key)
    return buckets


def _balanced_required_order(targets: list[Any]) -> list[Any]:
    buckets = _bucket_required_targets(targets)
    order: list[Any] = []
    family_order = ["yaml", "powershell", "python", "other", "kubernetes"]
    while any(buckets.get(family) for family in family_order):
        for family in family_order:
            bucket = buckets.get(family) or []
            if bucket:
                order.append(bucket.pop(0))
    return order
