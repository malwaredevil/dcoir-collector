def iter_added_diff_lines(diff: str) -> list[ChangedLine]:
    lines: list[ChangedLine] = []
    current_path: str | None = None
    right_line: int | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_path = None
            right_line = None
            continue
        if line.startswith("+++ b/"):
            current_path = line[6:]
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,\d+)?", line)
            right_line = int(match.group(1)) if match else None
            continue
        if current_path is None or right_line is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(ChangedLine(current_path, right_line, line[1:]))
            right_line += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            continue
        right_line += 1
    return lines


def build_added_line_index(diff: str) -> dict[tuple[str, int], int]:
    right_line_index = base.build_diff_line_index(diff)
    added_line_index: dict[tuple[str, int], int] = {}
    for changed_line in iter_added_diff_lines(diff):
        key = (changed_line.path, changed_line.line)
        if key in right_line_index:
            added_line_index[key] = right_line_index[key]
    return added_line_index


def is_comment_only_added_line(path: str, text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    suffix = Path(path).suffix.lower()
    if suffix in {".py", ".sh", ".bash", ".yaml", ".yml"}:
        return stripped.startswith("#")
    if suffix in {".ps1", ".psd1", ".psm1"}:
        return stripped.startswith(("#", "<#", "#>"))
    if suffix in {".js", ".cjs", ".mjs", ".ts"}:
        return stripped.startswith(("//", "/*", "*", "*/"))
    return False


def append_risk_sentinel(
    sentinels: list[RiskSentinel],
    seen: set[tuple[str, int, str]],
    changed_line: ChangedLine,
    label: str,
    detail: str,
) -> None:
    key = (changed_line.path, changed_line.line, label)
    if key in seen:
        return
    seen.add(key)
    sentinels.append(
        RiskSentinel(
            path=changed_line.path,
            line=changed_line.line,
            label=label,
            detail=detail,
            text=changed_line.text,
        )
    )


def select_risk_sentinels(sentinels: list[RiskSentinel], max_anchors: int | None) -> list[RiskSentinel]:
    if max_anchors is None or len(sentinels) <= max_anchors:
        return sentinels
    if max_anchors <= 0:
        return []

    indexed = list(enumerate(sentinels))
    by_path: dict[str, list[tuple[int, RiskSentinel]]] = {}
    for index, sentinel in indexed:
        by_path.setdefault(sentinel.path, []).append((index, sentinel))

    def sort_key(item: tuple[int, RiskSentinel]) -> tuple[int, int]:
        index, sentinel = item
        return (RISK_SENTINEL_LABEL_PRIORITY.get(sentinel.label, 1000), index)

    for items in by_path.values():
        items.sort(key=sort_key)

    path_order = sorted(
        by_path,
        key=lambda path: (
            RISK_SENTINEL_LABEL_PRIORITY.get(by_path[path][0][1].label, 1000),
            by_path[path][0][0],
        ),
    )
    selected: list[RiskSentinel] = []
    selected_indexes: set[int] = set()
    selected_labels_by_path: dict[str, set[str]] = {path: set() for path in path_order}
    while len(selected) < max_anchors:
        made_progress = False
        for path in path_order:
            candidates = [item for item in by_path[path] if item[0] not in selected_indexes]
            next_item = next(
                (item for item in candidates if item[1].label not in selected_labels_by_path[path]),
                candidates[0] if candidates else None,
            )
            if next_item is None:
                continue
            index, sentinel = next_item
            selected_indexes.add(index)
            selected_labels_by_path[path].add(sentinel.label)
            selected.append(sentinel)
            made_progress = True
            if len(selected) >= max_anchors:
                break
        if not made_progress:
            break
    return selected


def detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[RiskSentinel]:
    sentinels: list[RiskSentinel] = []
    seen: set[tuple[str, int, str]] = set()
    active_python_subprocess_call: str | None = None
    current_path = ""
    powershell_request_path_vars: set[str] = set()
    shell_subprocess_detail = next(
        detail for label, detail, _pattern in RISK_SENTINEL_RULES if label == "shell=True subprocess invocation"
    )
    powershell_file_write_detail = next(
        detail for label, detail, _pattern in RISK_SENTINEL_RULES if label == "PowerShell unsafe file-write path"
    )
    for changed_line in iter_added_diff_lines(diff):
        if changed_line.path != current_path:
            current_path = changed_line.path
            powershell_request_path_vars = set()
        suffix = Path(changed_line.path).suffix.lower()
        if suffix not in RISK_SENTINEL_EXTENSIONS:
            active_python_subprocess_call = None
            powershell_request_path_vars = set()
            continue
        if is_comment_only_added_line(changed_line.path, changed_line.text):
            continue

        if suffix == ".py":
            if active_python_subprocess_call == changed_line.path and re.search(r"\bshell\s*=\s*True\b", changed_line.text):
                append_risk_sentinel(
                    sentinels,
                    seen,
                    changed_line,
                    "shell=True subprocess invocation",
                    shell_subprocess_detail,
                )
            open_call = re.search(r"\bsubprocess\.\w+\(", changed_line.text)
            if open_call and ")" not in changed_line.text[open_call.end() :]:
                active_python_subprocess_call = changed_line.path
            elif active_python_subprocess_call == changed_line.path and ")" in changed_line.text:
                active_python_subprocess_call = None
        else:
            active_python_subprocess_call = None

        if suffix in {".ps1", ".psd1", ".psm1"}:
            assignment_match = POWERSHELL_REQUEST_PATH_ASSIGNMENT.search(changed_line.text)
            if assignment_match:
                powershell_request_path_vars.add(assignment_match.group("name").lower())
            write_match = POWERSHELL_WRITE_PATH_VARIABLE.search(changed_line.text)
            if write_match and write_match.group("name").lower() in powershell_request_path_vars:
                append_risk_sentinel(
                    sentinels,
                    seen,
                    changed_line,
                    "PowerShell unsafe file-write path",
                    powershell_file_write_detail,
                )

        for label, detail, pattern in RISK_SENTINEL_RULES:
            if pattern.search(changed_line.text):
                append_risk_sentinel(sentinels, seen, changed_line, label, detail)
                break
    return select_risk_sentinels(sentinels, max_anchors)


def risk_sentinel_digest(sentinels: list[RiskSentinel]) -> str:
    return "; ".join(f"{item.path}:{item.line} {item.label}" for item in sentinels[:6])


def risk_sentinel_block(sentinels: list[RiskSentinel], config: Any) -> str:
    lines = [
        "Changed-code risk signals detected before model review:",
        "Any non-empty findings response must cover these anchors by path, nearby line, and risk class. Unrelated findings do not satisfy this gate.",
    ]
    for item in sentinels[: getattr(config, "risk_sentinel_max_anchors", 12)]:
        snippet = item.text.strip().replace("`", "'")
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        lines.append(f"- {item.path}:{item.line} [{item.label}] {item.detail}. Changed code: `{snippet}`")
    return base.sanitize_text("\n".join(lines), config)


def normalized_quality_text(text: str) -> str:
    return re.sub(r"[^a-z0-9_.:=/-]+", " ", text.lower()).strip()


def risk_sentinel_terms(sentinel: RiskSentinel) -> tuple[str, ...]:
    terms = RISK_SENTINEL_FINDING_TERMS.get(sentinel.label, ())
    if terms:
        return terms
    label_terms = tuple(part for part in normalized_quality_text(sentinel.label).split() if len(part) >= 4)
    return label_terms or (normalized_quality_text(sentinel.label),)


def finding_covers_risk_sentinel(finding: dict[str, Any], sentinel: RiskSentinel) -> bool:
    try:
        finding_line = int(finding.get("line", 0))
    except (TypeError, ValueError):
        return False
    finding_path = str(finding.get("path", "")).strip()
    if finding_path != sentinel.path:
        return False
    if abs(finding_line - sentinel.line) > RISK_SENTINEL_COVERAGE_LINE_WINDOW:
        return False
    finding_text = normalized_quality_text(
        "\n".join(
            [
                str(finding.get("title", "") or ""),
                str(finding.get("body", "") or ""),
                str(finding.get("validation", "") or ""),
            ]
        )
    )
    if not finding_text:
        return False
    return any(normalized_quality_text(term) in finding_text for term in risk_sentinel_terms(sentinel))


def is_required_risk_sentinel(sentinel: RiskSentinel) -> bool:
    label = sentinel.label
    if label in OPTIONAL_RISK_SENTINEL_LABELS or any(
        label.startswith(prefix) for prefix in OPTIONAL_RISK_SENTINEL_LABEL_PREFIXES
    ):
        return False
    suffix = Path(sentinel.path).suffix.lower()
    if suffix in PROJECT_TARGET_RISK_SENTINEL_EXTENSIONS:
        return True
    if suffix in {".yml", ".yaml"}:
        return label in YAML_REQUIRED_RISK_SENTINEL_LABELS or any(
            label.startswith(prefix) for prefix in YAML_REQUIRED_RISK_SENTINEL_LABEL_PREFIXES
        )
    return False


def required_risk_sentinels(sentinels: list[RiskSentinel]) -> list[RiskSentinel]:
    return [sentinel for sentinel in sentinels if is_required_risk_sentinel(sentinel)]


def uncovered_risk_sentinels(
    findings: list[dict[str, Any]],
    risk_sentinels: list[RiskSentinel],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> list[RiskSentinel]:
    if not risk_sentinels or not getattr(config, "risk_sentinel_quality_gate", True):
        return []
    candidate_findings = [*findings, *(unanchored_findings or [])]
    return [
        sentinel
        for sentinel in required_risk_sentinels(risk_sentinels)
        if not any(finding_covers_risk_sentinel(finding, sentinel) for finding in candidate_findings)
    ]


def risk_sentinel_coverage_digest(sentinels: list[RiskSentinel]) -> str:
    return "; ".join(f"{item.path}:{item.line} {item.label}" for item in sentinels[:8])


def primary_validation_command(config: Any) -> str:
    commands = getattr(config, "validation_commands", [])
    if isinstance(commands, list) and commands:
        return str(commands[0])
    return "Run the relevant dcoir-review selftests and workflow validation."


