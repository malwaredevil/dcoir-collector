def build_prompt(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    config: Any,
    risk_sentinels: list[hardened.RiskSentinel],
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
) -> str:
    mode_lines = [
        f"{CONTEXT_REVIEW_MARKER} {review_mode}",
        f"Context readback: {context_summary}",
        "When deep context is present, use it to reason about full changed-file behavior, but anchor actionable findings to changed lines when practical.",
        "Every finding must include exact correction guidance or the smallest safe patch direction, plus validation/readback guidance.",
        "Prefer GitHub apply-ready suggestions only when a finding has a precise single-line replacement for the commented line; put only that exact replacement code in suggested_replacement so the renderer emits a Suggested fix with a ```suggestion block; leave suggested_replacement empty for multiline, range, or speculative fixes.",
        "Inspect dynamic path construction and file writes for traversal, arbitrary overwrite, missing root-containment checks, and unsafe staging side effects.",
        "For this repository, give extra attention to PowerShell, Python, and GitHub Actions/YAML because they carry most operational and workflow risk; keep findings generalizable and do not tune to any single fixture.",
    ]
    context = base.sanitize_text(deep_context_block.strip(), config)
    suffix = ""
    # Extremely small budgets preserve the hardened core review prompt and rely
    # on workflow progress/review readback for context-mode visibility.
    if config.max_prompt_chars >= 3000:
        suffix_budget = config.max_prompt_chars // 3
        budget = max(0, min(len(context), int(getattr(config, "deep_review_max_total_chars", 24000)), suffix_budget))
        if len(context) > budget:
            context = truncate_with_balanced_fences(context, budget, DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER)
        suffix = "\n\n".join(["\n".join(mode_lines), context]).strip()
        if len(suffix) > suffix_budget:
            suffix = truncate_with_balanced_fences(suffix, suffix_budget, DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER)

    prompt_config = copy.copy(config)
    separator = "\n\n"
    reserve = min(len(suffix), config.max_prompt_chars // 3) if suffix else 0
    prompt_config.max_prompt_chars = max(0, config.max_prompt_chars - reserve - len(separator))
    prompt = hardened.build_prompt(pr, files, diff, prompt_config, risk_sentinels)
    if not suffix:
        return prompt[: config.max_prompt_chars]
    if len(prompt) + len(separator) + len(suffix) <= config.max_prompt_chars:
        return f"{prompt}{separator}{suffix}"
    remaining = config.max_prompt_chars - len(prompt) - len(separator)
    if remaining <= len(DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER):
        retained_prompt = max(0, config.max_prompt_chars - len(DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER))
        return f"{prompt[:retained_prompt]}{DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER}"
    return f"{prompt}{separator}{truncate_with_balanced_fences(suffix, remaining, DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER)}"


def neutralize_github_mentions(text: str) -> str:
    return re.sub(r"@(?=[A-Za-z0-9])", "@<!-- -->", text)


def sanitize_context_summary(context_summary: str, config: Any) -> str:
    return neutralize_github_mentions(hardened.sanitize_github_output(context_summary, config))


def append_context_to_review_body(body: str, review_mode: str, context_summary: str, config: Any) -> str:
    safe_context_summary = sanitize_context_summary(context_summary, config)
    return base.github_safe_body(f"{body}\n\n{CONTEXT_REVIEW_MARKER} `{review_mode}`\n\nContext readback: {safe_context_summary}")


FINDING_ANCHOR_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("pickle", "deserial"), ("pickle.loads", "pickle.load", "pickle")),
    (("yaml", "loader", "deserial"), ("yaml.load", "yaml.loader", "loader=yaml.loader")),
    (("ssrf", "outbound", "request url"), ("requests.get", "requests.post", "requests.request", "httpx.", "url")),
    (("securestring", "plain text", "plaintext"), ("convertto-securestring", "-asplaintext", "securestring")),
    (("start-process", "process launch"), ("start-process", "-filepath", "-argumentlist")),
    (("run key", "persistence", "set-itemproperty"), ("set-itemproperty", "currentversion\\run", "\\run", "run")),
    (("pull_request_target", "privileged pr"), ("pull_request_target",)),
    (("broad write", "write permission", "permissions"), ("permissions:", "contents:", "pull-requests:", "write")),
    (("checkout", "untrusted", "head sha", "head ref"), ("actions/checkout", "github.event.pull_request.head.sha", "github.event.pull_request.head.ref")),
    (("curl", "pipe", "bash"), ("curl", "bash", "|")),
    (("eval", "exec", "dynamic code"), ("eval(", "exec(")),
)
ANCHOR_TERM_STOP_WORDS = {
    "actionable",
    "affected",
    "anchored",
    "changed",
    "command",
    "confidence",
    "correction",
    "expected",
    "finding",
    "github",
    "impact",
    "line",
    "review",
    "risk",
    "security",
    "should",
    "source",
    "validation",
}


def normalized_anchor_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def finding_anchor_terms(finding: dict[str, Any]) -> list[str]:
    haystack = normalized_anchor_text(
        "\n".join(
            [
                str(finding.get("title", "") or ""),
                str(finding.get("body", "") or ""),
                str(finding.get("validation", "") or ""),
            ]
        )
    )
    terms: set[str] = set()
    for triggers, anchors in FINDING_ANCHOR_HINTS:
        if any(trigger in haystack for trigger in triggers):
            terms.update(anchors)
    for token in re.findall(r"[a-z_][a-z0-9_.:-]{3,}", haystack):
        if token not in ANCHOR_TERM_STOP_WORDS and len(token) <= 48:
            terms.add(token)
    return sorted(terms, key=lambda term: (-len(term), term))[:24]


def finding_text_matches_sentinel(finding: dict[str, Any], sentinel: hardened.RiskSentinel) -> bool:
    haystack = normalized_anchor_text(
        "\n".join(
            [
                str(finding.get("title", "") or ""),
                str(finding.get("body", "") or ""),
                str(finding.get("validation", "") or ""),
            ]
        )
    )
    return any(normalized_anchor_text(term) in haystack for term in hardened.risk_sentinel_terms(sentinel))


def anchor_candidate_score(
    finding: dict[str, Any],
    candidate: hardened.ChangedLine,
    original_line: int,
    terms: list[str],
    risk_sentinels: list[hardened.RiskSentinel],
) -> int:
    distance = abs(candidate.line - original_line) if original_line > 0 else 1000
    score = max(0, 24 - distance)
    line_text = normalized_anchor_text(candidate.text)
    for term in terms:
        normalized_term = normalized_anchor_text(term)
        if normalized_term and normalized_term in line_text:
            score += 36 if len(normalized_term) >= 8 or any(char in normalized_term for char in ".:-_\\|") else 14
    if candidate.line == original_line:
        score += 3
    for sentinel in risk_sentinels:
        if sentinel.path == candidate.path and sentinel.line == candidate.line and finding_text_matches_sentinel(finding, sentinel):
            score += 90
    return score


def reanchor_finding_to_changed_line(
    finding: dict[str, Any],
    line_index: dict[tuple[str, int], int],
    changed_lines_by_path: dict[str, list[hardened.ChangedLine]],
    risk_sentinels: list[hardened.RiskSentinel],
) -> dict[str, Any]:
    path = str(finding.get("path", "") or "").strip()
    try:
        original_line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        return finding
    candidates = changed_lines_by_path.get(path, [])
    if not path or not candidates:
        return finding
    terms = finding_anchor_terms(finding)
    if not terms and (path, original_line) in line_index:
        return finding
    scored = [
        (
            anchor_candidate_score(finding, candidate, original_line, terms, risk_sentinels),
            -abs(candidate.line - original_line) if original_line > 0 else 0,
            candidate.line,
            candidate,
        )
        for candidate in candidates
    ]
    scored.sort(reverse=True)
    best_score, _best_distance_sort, _best_line_sort, best_candidate = scored[0]
    exact_candidate = next((candidate for candidate in candidates if candidate.line == original_line), None)
    exact_score = (
        anchor_candidate_score(finding, exact_candidate, original_line, terms, risk_sentinels)
        if exact_candidate is not None
        else -1
    )
    if exact_candidate is not None and best_score < exact_score + 8:
        return finding
    if best_score < 24:
        return finding
    anchored = dict(finding)
    anchored["line"] = best_candidate.line
    if original_line != best_candidate.line:
        anchored["_reanchored_from_line"] = original_line
    return anchored


def split_findings_with_review_body_fallback(
    result: dict[str, Any],
    config: Any,
    line_index: dict[tuple[str, int], int],
    diff: str = "",
    risk_sentinels: list[hardened.RiskSentinel] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list) or not raw_findings:
        return hardened.split_findings(result, config, line_index)
    changed_paths = {path for path, _line in line_index}
    changed_lines_by_path: dict[str, list[hardened.ChangedLine]] = {}
    if diff:
        for changed_line in hardened.iter_added_diff_lines(diff):
            changed_lines_by_path.setdefault(changed_line.path, []).append(changed_line)
    risk_sentinels = risk_sentinels or []
    findings: list[dict[str, Any]] = []
    unanchored_findings: list[dict[str, Any]] = []
    track_unanchored = bool(getattr(config, "fail_on_unanchored_findings", True))
    for item in raw_findings:
        try:
            confidence = float(item.get("confidence", 0))
            line = int(item.get("line", 0))
            path = str(item.get("path", "")).strip()
        except (AttributeError, TypeError, ValueError):
            continue
        if not path or line <= 0:
            continue
        if confidence < config.minimum_confidence or hardened.non_actionable_finding_reason(item):
            continue
        if path not in changed_paths:
            continue
        anchored_item = reanchor_finding_to_changed_line(dict(item), line_index, changed_lines_by_path, risk_sentinels)
        try:
            line = int(anchored_item.get("line", 0) or 0)
            path = str(anchored_item.get("path", "")).strip()
        except (AttributeError, TypeError, ValueError):
            continue
        if (path, line) in line_index:
            findings.append(anchored_item)
            continue
        if track_unanchored:
            unanchored = dict(anchored_item)
            location_text = hardened.finding_location_text(path, line)
            unanchored["_unanchored_reason"] = f"{location_text} is not an added changed line for this PR"
            unanchored_findings.append(unanchored)
    findings = rank_findings_for_required_budget(findings, config)
    unanchored_findings = dedupe_findings_for_ranking(unanchored_findings)
    unanchored_findings.sort(key=hardened.severity_sort_key)
    unanchored_findings = unanchored_findings[: config.max_inline_comments]
    if findings or unanchored_findings:
        return findings, unanchored_findings
    return hardened.split_findings(result, config, line_index)
