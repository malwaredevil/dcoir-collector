

def _make_yaml_sentinels(hardened: Any, diff: str) -> list[Any]:
    sentinels: list[Any] = []
    seen: set[tuple[str, int, str]] = set()
    iter_added = getattr(hardened, "iter_added_diff_lines", None)
    if not callable(iter_added):
        return sentinels
    risk_sentinel_type = getattr(hardened, "RiskSentinel", None)
    if risk_sentinel_type is None:
        return sentinels
    for changed_line in iter_added(diff):
        path = str(getattr(changed_line, "path", "") or "")
        text = str(getattr(changed_line, "text", "") or "")
        if Path(path.lower()).suffix not in {".yml", ".yaml"}:
            continue
        if callable(getattr(hardened, "is_comment_only_added_line", None)) and hardened.is_comment_only_added_line(path, text):
            continue
        kind = _line_semantic_kind(path, text)
        if kind not in YAML_SENTINEL_METADATA:
            continue
        try:
            line = int(getattr(changed_line, "line", 0) or 0)
        except (TypeError, ValueError):
            continue
        key = (path, line, kind)
        if key in seen:
            continue
        seen.add(key)
        label, detail = YAML_SENTINEL_METADATA[kind]
        sentinels.append(risk_sentinel_type(path=path, line=line, label=label, detail=detail, text=text))
    return sentinels


def _dedupe_sentinels(sentinels: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[tuple[str, int, str]] = set()
    for sentinel in sentinels:
        try:
            line = int(getattr(sentinel, "line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        key = (str(getattr(sentinel, "path", "") or ""), line, _sentinel_kind(sentinel) or str(getattr(sentinel, "label", "") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentinel)
    return deduped


def _select_sentinels(hardened: Any, sentinels: list[Any], max_anchors: int | None) -> list[Any]:
    deduped = _dedupe_sentinels(sentinels)
    if max_anchors is None or len(deduped) <= max_anchors:
        return deduped
    if max_anchors <= 0:
        return []
    required_yaml = [sentinel for sentinel in deduped if _sentinel_kind(sentinel) in YAML_REQUIRED_KIND_TITLES]
    selected: list[Any] = []
    seen: set[tuple[str, int, str]] = set()

    def add(item: Any) -> None:
        try:
            line = int(getattr(item, "line", 0) or 0)
        except (TypeError, ValueError):
            line = 0
        key = (str(getattr(item, "path", "") or ""), line, _sentinel_kind(item) or str(getattr(item, "label", "") or ""))
        if key not in seen and len(selected) < max_anchors:
            seen.add(key)
            selected.append(item)

    for sentinel in required_yaml:
        add(sentinel)
    remaining = [sentinel for sentinel in deduped if sentinel not in selected]
    original_select = getattr(hardened, "_dcoir_required_original_select_risk_sentinels", None)
    if not callable(original_select):
        original_select = getattr(hardened, "select_risk_sentinels", None)
    if callable(original_select):
        remaining = original_select(remaining, max_anchors - len(selected))
    for sentinel in remaining:
        add(sentinel)
    return selected


def _yaml_fallback_body(kind: str, sentinel: Any) -> str:
    changed = str(getattr(sentinel, "text", "") or "").strip()
    if kind == "yaml_pull_request_target":
        return "`pull_request_target` runs with base-repository privileges. Do not execute untrusted pull request code in this context."
    if kind == "yaml_broad_write":
        return "This workflow grants broad write permissions. Narrow the token permissions to the minimum scopes needed."
    if kind == "yaml_untrusted_checkout":
        return "This privileged workflow checks out pull request controlled code. Use an unprivileged event, avoid checking out PR head refs in privileged jobs, or split trusted labeling from untrusted code execution."
    if kind == "yaml_shell_pipe":
        return f"This workflow pipes network-fetched content into a shell: `{changed}`. Download a pinned artifact, verify its checksum or signature, then execute only verified content."
    return "Review this GitHub Actions security boundary before merging."


def _validation_for_path(path: str, kind: str = "") -> str:
    lower_path = path.lower()
    quoted = shlex.quote(path)
    if lower_path.endswith(".py"):
        return f"python3 -m py_compile {quoted}"
    if lower_path.endswith((".ps1", ".psm1", ".psd1")):
        ps_path = "'" + path.replace("'", "''") + "'"
        return (
            "pwsh -NoProfile -Command \"$errors=$null; "
            f"[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath {ps_path}), [ref]$errors) | Out-Null; "
            "if ($errors) { throw ($errors | Out-String) }\""
        )
    if lower_path.endswith((".yml", ".yaml")):
        assertions = ["assert path.exists(), path"]
        if kind == "yaml_pull_request_target":
            assertions.append("assert 'pull_request_target' not in text")
        elif kind == "yaml_broad_write":
            assertions.append("assert 'write-all' not in text and ': write' not in text")
        elif kind == "yaml_untrusted_checkout":
            assertions.append("assert 'github.event.pull_request.head' not in text and 'github.head_ref' not in text")
        elif kind == "yaml_shell_pipe":
            assertions.append("assert '| bash' not in text and '| sh' not in text")
        else:
            assertions.append("assert text.strip()")
        body = "\n".join(assertions)
        return f"python3 - <<'PY'\nfrom pathlib import Path\npath = Path({path!r})\ntext = path.read_text(encoding='utf-8')\n{body}\nPY"
    if lower_path.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        return f"npx tsc --noEmit --pretty false  # include {quoted} in the nearest project tsconfig"
    return f"Run the nearest syntax/static check for {quoted} and a focused test for the changed behavior."


def _validation_needs_replacement(validation: str, path: str) -> bool:
    if not validation.strip():
        return True
    if INTERNAL_VALIDATION_RE.search(validation) and not path.startswith("scripts/"):
        return True
    return False


def _normalize_token_hallucinations(value: str) -> str:
    value = REDACTED_SECRET_RE.sub("the environment token value", value)
    value = HARDCODED_SECRET_RE.sub("environment token value", value)
    lines = [line for line in value.splitlines() if "syntax error" not in line.lower()]
    return "\n".join(lines).strip()


def _normalize_comment_finding(finding: dict[str, Any]) -> dict[str, Any]:
    item = dict(finding)
    kind = _semantic_kind(item)
    title = _clean_public_text(item.get("title", "") or "Finding").replace("Deterministic risk sentinel:", "").strip()
    if kind in YAML_REQUIRED_KIND_TITLES:
        title = YAML_REQUIRED_KIND_TITLES[kind]
    item["title"] = title or "Finding"
    body = _clean_public_text(item.get("body", ""))
    if kind == "python_ssrf":
        body = _normalize_token_hallucinations(body)
    item["body"] = body
    validation = _clean_public_text(item.get("validation", ""))
    if _validation_needs_replacement(validation, str(item.get("path", "") or "")):
        validation = _validation_for_path(str(item.get("path", "") or ""), kind)
    item["validation"] = validation
    guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
    if guidance:
        cleaned_guidance = dict(guidance)
        notes = _clean_public_text(cleaned_guidance.get("notes", ""))
        if kind == "python_ssrf":
            notes = _normalize_token_hallucinations(notes)
        if notes:
            cleaned_guidance["notes"] = notes
        item["fix_guidance"] = cleaned_guidance
    return item


def _dedupe_line_key(kind: str, finding: dict[str, Any]) -> str:
    if kind in COLLAPSE_TO_FILE_KINDS:
        return ""
    return str(finding.get("line", "") or "").strip()


def _dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    kind = _semantic_kind(finding)
    path = str(finding.get("path", "") or "").strip()
    if kind:
        return (path, _dedupe_line_key(kind, finding), kind, "")
    return (
        path,
        str(finding.get("line", "") or "").strip(),
        _normalize(finding.get("title", ""))[:120],
        _normalize(finding.get("body", ""))[:120],
    )


def _finding_quality_score(hardened: Any, finding: dict[str, Any]) -> tuple[int, float, int]:
    scorer = getattr(hardened, "finding_quality_score", None)
    if callable(scorer):
        return scorer(finding)
    try:
        confidence = float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    severity = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(finding.get("severity", "")).lower(), 0)
    return severity, confidence, len(str(finding.get("body", "") or ""))


def _dedupe_findings(hardened: Any, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str, str]] = []
    for finding in findings:
        key = _dedupe_key(finding)
        if key not in by_key:
            by_key[key] = finding
            order.append(key)
            continue
        if _finding_quality_score(hardened, finding) >= _finding_quality_score(hardened, by_key[key]):
            by_key[key] = finding
    return [by_key[key] for key in order]
