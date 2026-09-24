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
            if Path(sentinel.path).suffix.lower() == ".py" and python_line_is_known_urllib_urlopen(
                sentinel.text,
                known_call_names=urllib_urlopen_call_names_by_path.get(sentinel.path),
            ):
                # Historical string matching treated names such as ``urlopen`` as
                # filesystem ``open``. Drop only this known lexical false
                # positive and keep other legacy sentinels unless a dedicated
                # replacement already covers them.
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


def python_line_imports_urllib_urlopen_alias(text: str) -> bool:
    module = python_parse_diff_line(text)
    if module is None:
        return bool(re.search(r"^\s*from\s+urllib\.request\s+import\s+.*\burlopen\b", text))
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
            return any(alias.name == "urlopen" for alias in node.names)
    return False


def python_urllib_urlopen_call_names(text: str) -> set[str]:
    call_names = {"urllib.request.urlopen", "urllib.urlopen"}
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
    return call_names


def python_diff_urllib_urlopen_call_names(diff: str) -> dict[str, set[str]]:
    sources_by_path: dict[str, list[str]] = {}
    for diff_line in iter_python_diff_lines_with_context(diff):
        if Path(diff_line.path).suffix.lower() == ".py":
            sources_by_path.setdefault(diff_line.path, []).append(diff_line.text)
    call_names_by_path: dict[str, set[str]] = {}
    for path, lines in sources_by_path.items():
        call_names = python_urllib_urlopen_call_names("\n".join(lines))
        call_names.update(PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.get(path, set()))
        call_names_by_path[path] = call_names
    return call_names_by_path


def python_line_is_known_urllib_urlopen(
    text: str,
    allow_imported_alias: bool = False,
    known_call_names: set[str] | None = None,
) -> bool:
    call_names = set(known_call_names or {"urllib.request.urlopen", "urllib.urlopen"})
    if allow_imported_alias:
        call_names.add("urlopen")
    module = python_parse_diff_line(text)
    if module is not None:
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and python_call_name(node.func) in call_names:
                return True
        return False
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in sorted(call_names, key=len, reverse=True)) + r")\s*\("
    return bool(re.search(pattern, text))


def command_option_tokens(body: str, command: str) -> set[str]:
    first_line = body.strip().splitlines()[0].strip() if body.strip() else ""
    if not first_line.startswith(command):
        return set()
    suffix = first_line[len(command) :].strip().lower()
    return {token for token in re.split(r"[\s,]+", suffix) if token}


def review_mode_for_command(body: str, command: str, config: Any, prior_successful_review: bool) -> str:
    tokens = command_option_tokens(body, command)
    if {"deep", "exhaustive"} & tokens:
        return "deep-forced"
    if "diff" in tokens:
        return "diff"
    if getattr(config, "first_pass_deep_review", True) and not prior_successful_review:
        return "first-pass-deep"
    return "diff"


def list_pr_reviews(gh: Any, pr_number: int) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = gh.request("GET", f"/repos/{gh.repo}/pulls/{pr_number}/reviews?per_page=100&page={page}")
        if not batch:
            break
        reviews.extend(batch)
        if len(batch) < 100:
            break
        # Exact multiples of 100 cost one extra empty-page readback, which is
        # acceptable for the small PR review counts this workflow expects.
        page += 1
    return reviews


def has_prior_successful_context_review(gh: Any, pr_number: int) -> bool:
    markers = (base.MARKER, *getattr(base, "LEGACY_MARKERS", ()))
    for review in list_pr_reviews(gh, pr_number):
        body = str(review.get("body", ""))
        if any(marker in body for marker in markers) and CONTEXT_REVIEW_MARKER in body:
            return True
    return False


def language_hint(path: str) -> str:
    suffix = Path(path).suffix.lower()
    # Common review surfaces get language hints; uncommon suffixes safely fall
    # back to plain text instead of expanding the prompt grammar surface.
    return {
        ".bash": "bash",
        ".cjs": "javascript",
        ".js": "javascript",
        ".json": "json",
        ".md": "markdown",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".sh": "bash",
        ".ts": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def fetch_pr_file_text(gh: Any, path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    payload = gh.request("GET", f"/repos/{gh.repo}/contents/{encoded_path}?ref={encoded_ref}")
    if not isinstance(payload, dict) or payload.get("type") != "file":
        raise RuntimeError("content API did not return a file")
    encoding = payload.get("encoding")
    content = payload.get("content")
    if content is None or (content == "" and encoding == "none"):
        raise RuntimeError("file exceeds GitHub content API limit (>1 MB); omitting from deep context")
    if encoding != "base64":
        raise RuntimeError("content API did not return base64 text")
    raw = base64.b64decode(str(content).replace("\n", ""))
    return raw.decode("utf-8")


FIX_SYNTHESIS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Review Fix Synthesis",
    "type": "object",
    "additionalProperties": False,
    "required": ["suggested_replacement", "remove", "replace", "add", "notes", "validation"],
    "properties": {
        "suggested_replacement": {
            "type": "string",
            "description": "Exact replacement code for the anchored review line only. Empty string if unsafe or not exact.",
        },
        "remove": {"type": "string", "description": "Code or behavior to remove when no native suggestion is safe."},
        "replace": {"type": "string", "description": "Replacement code or behavior when no native suggestion is safe."},
        "add": {"type": "string", "description": "Additional guard, validation, or test code to add when needed."},
        "notes": {"type": "string", "description": "Short implementation caveat. Empty when unnecessary."},
        "validation": {"type": "string", "description": "Exact validation command or commands that should pass after the fix."},
    },
}
