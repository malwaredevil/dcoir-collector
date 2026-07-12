def summary_suggests_problem(summary: str) -> bool:
    positive_terms = (
        "finding",
        "issue",
        "problem",
        "regression",
        "risk",
        "bypass",
        "unsafe",
        "missing",
        "misleading",
        "failure",
        "should",
        "must",
        "breaks",
    )
    negative_phrases = (
        "nothing actionable",
        "no high confidence inline findings were found",
        "no high confidence findings were found",
        "no high confidence inline findings",
        "no high confidence findings",
        "no high signal findings",
        "no high confidence",
        "no high signal",
        "no actionable",
        "no findings",
        "no problems",
        "no issues",
        "no issue",
        "looks good",
        "clean review",
    )
    problem_noun_pattern = r"(?:findings?|issues?|problems?|regressions?|risks?|failures?|bypasses?)"
    remaining_problem_noun_pattern = r"(?:issues?|problems?|regressions?|risks?|failures?|bypasses?)"
    introduced_problem_noun_pattern = (
        r"(?:findings?|issues?|problems?|defects?|vulnerabilities?|regressions?|risks?|failures?|bypasses?|injection paths?)"
    )
    modified_problem_noun_pattern = rf"(?:[a-z0-9-]+\s+){{0,4}}{problem_noun_pattern}"
    clean_two_item_problem_noun_pattern = (
        rf"(?!(?:a|an|the|this|that|these|those)\b)"
        rf"(?:[a-z0-9-]+\s+){{0,4}}{problem_noun_pattern}"
    )
    clean_two_item_remaining_noun_pattern = (
        rf"(?!(?:a|an|the|this|that|these|those)\b)"
        rf"(?:[a-z0-9-]+\s+){{1,4}}{remaining_problem_noun_pattern}"
    )
    clean_two_item_following_remaining_noun_pattern = (
        rf"(?!(?:a|an|the|this|that|these|those)\b)"
        rf"(?:[a-z0-9-]+\s+){{0,4}}{remaining_problem_noun_pattern}"
    )
    clean_two_item_result_verb_pattern = r"(?:(?:were|was|are|is)\s+)?(?:found|identified|detected|observed)"
    negated_list_patterns = (
        rf"\bno\b\s+{clean_two_item_problem_noun_pattern}"
        rf"\s+(?:and|or)\s+{clean_two_item_problem_noun_pattern}"
        rf"\s+{clean_two_item_result_verb_pattern}",
        rf"\bno\b\s+{clean_two_item_problem_noun_pattern}"
        rf"\s+or\s+{clean_two_item_problem_noun_pattern}"
        r"\s+(?:present|remaining|remain)",
        rf"\bno\b\s+{clean_two_item_remaining_noun_pattern}"
        rf"\s+and\s+{clean_two_item_following_remaining_noun_pattern}"
        r"\s+(?:present|remaining|remain)",
        rf"\bno\b\s+{modified_problem_noun_pattern}"
        rf"(?:,\s*(?!\b(?:and|or)\b){modified_problem_noun_pattern})+"
        rf"(?:,\s*|\s+)(?:and|or)\s+{modified_problem_noun_pattern}"
        r"(?:\s+(?:were|was|are|is|found|identified|detected|observed|present|remaining|remain))*",
        rf"\bno\b\s+{modified_problem_noun_pattern}"
        rf"(?:,\s*(?!\b(?:and|or)\b){modified_problem_noun_pattern})*"
        rf",\s*(?:and|or)\s+{modified_problem_noun_pattern}"
        r"(?:\s+(?:were|was|are|is|found|identified|detected|observed|present|remaining|remain))*",
    )
    negated_introduced_problem_patterns = (
        rf"\b(?:does not|doesn't)(?: itself)?\s+(?:introduce|create|pose|add)\b"
        rf"(?:(?:\.\d)|[^.;:!?\n]){{0,220}}\b{introduced_problem_noun_pattern}\b",
    )
    negated_problem_patterns = (
        *negated_list_patterns,
        *negated_introduced_problem_patterns,
        r"\bno\b(?:\s+[a-z0-9]+){0,8}\s+(?:findings?|issues?|problems?|regressions?|risks?|failures?|bypasses?)\b"
        r"(?:\s+(?:were|was|are|is|found|identified|detected|observed|present|remaining|remain))*",
        r"\bnot\b(?:\s+[a-z0-9]+){0,5}\s+(?:found|identified|detected|observed)\b",
    )

    def clause_suggests_problem(clause: str) -> bool:
        stripped = re.sub(r"[^a-z0-9]+", " ", clause.lower()).strip()
        for pattern in negated_problem_patterns:
            stripped = re.sub(pattern, " ", stripped)
        for phrase in negative_phrases:
            stripped = stripped.replace(phrase, " ")
        return any(re.search(rf"\b{re.escape(term)}s?\b", stripped) for term in positive_terms)

    cleaned_summary = summary.lower()
    for pattern in (*negated_introduced_problem_patterns, *negated_list_patterns):
        cleaned_summary = re.sub(pattern, " ", cleaned_summary)
    clauses = re.split(r"(?:[.;:!?]+|,\s+|\b(?:and|but|however|though|although|yet|except|nevertheless|still)\b)", cleaned_summary)
    return any(clause_suggests_problem(clause.strip()) for clause in clauses if clause.strip())


def finding_location_text(path: str, line: int) -> str:
    path_text = path if path else "<missing-path>"
    line_text = str(line) if line else "<missing-line>"
    return f"{path_text}:{line_text}"


def normalize_findings(result: dict[str, Any], config: Any, line_index: dict[tuple[str, int], int]) -> list[dict[str, Any]]:
    findings, _unanchored_findings = split_findings(result, config, line_index)
    return findings


def severity_sort_key(finding: dict[str, Any]) -> tuple[int, float]:
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    try:
        confidence = float(finding.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    return severity_order.get(str(finding.get("severity", "low")).lower(), 9), -confidence


def is_github_actions_yaml_path(path: str) -> bool:
    lower_path = path.lower()
    suffix = Path(lower_path).suffix
    if suffix not in {".yml", ".yaml"}:
        return False
    name = Path(lower_path).name
    return (
        lower_path.startswith(".github/workflows/")
        or "workflow" in name
        or "github" in lower_path
        or "actions" in lower_path
    )


def is_required_review_target_path(path: str) -> bool:
    suffix = Path(path.lower()).suffix
    if suffix in PROJECT_TARGET_RISK_SENTINEL_EXTENSIONS:
        return True
    return is_github_actions_yaml_path(path)


def is_required_review_target_finding(finding: dict[str, Any]) -> bool:
    path = str(finding.get("path", "") or "").strip()
    if is_required_review_target_path(path):
        return True
    text = normalized_quality_text(
        "\n".join(
            [
                str(finding.get("title", "") or ""),
                str(finding.get("body", "") or ""),
                str(finding.get("validation", "") or ""),
            ]
        )
    )
    required_terms = (
        "powershell",
        "python",
        "github actions",
        "pull_request_target",
        "github.event.pull_request",
        "github_token",
        "ci token",
    )
    return any(term in text for term in required_terms)


def select_findings_for_inline(findings: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    required = [finding for finding in findings if is_required_review_target_finding(finding)]
    optional = [finding for finding in findings if not is_required_review_target_finding(finding)]
    required.sort(key=severity_sort_key)
    optional.sort(key=severity_sort_key)
    return [*required, *optional][:limit]


def split_findings(
    result: dict[str, Any],
    config: Any,
    line_index: dict[tuple[str, int], int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    unanchored_findings: list[dict[str, Any]] = []
    rejected: list[str] = []
    raw_findings = result.get("findings", [])
    changed_paths = {path for path, _line in line_index}
    for item in raw_findings:
        try:
            confidence = float(item.get("confidence", 0))
            line = int(item.get("line", 0))
            path = str(item.get("path", "")).strip()
        except (AttributeError, TypeError, ValueError):
            rejected.append("invalid finding shape")
            continue
        title = str(item.get("title", "untitled")).strip()[:80]
        if confidence < config.minimum_confidence:
            location_text = finding_location_text(path, line)
            rejected.append(f"{location_text} low confidence {confidence:.2f} ({title})")
            continue
        non_actionable_reason = non_actionable_finding_reason(item)
        if non_actionable_reason:
            location_text = finding_location_text(path, line)
            rejected.append(f"{location_text} non-actionable ({non_actionable_reason}; {title})")
            continue
        if (path, line) not in line_index:
            if path and path in changed_paths:
                unanchored = dict(item)
                unanchored["_unanchored_reason"] = f"{path}:{line} is in a changed file but not an added changed line"
                unanchored_findings.append(unanchored)
                continue
            location_text = finding_location_text(path, line)
            rejected.append(f"{location_text} not in changed diff ({title})")
            continue
        findings.append(item)

    findings = select_findings_for_inline(findings, int(config.max_inline_comments))
    unanchored_findings = select_findings_for_inline(unanchored_findings, int(config.max_inline_comments))
    if findings or unanchored_findings:
        return findings, unanchored_findings

    if raw_findings and getattr(config, "fail_on_unanchored_findings", True):
        details = "; ".join(rejected[:6]) if rejected else "no accepted findings"
        raise ReviewQualityError(
            f"{base.REVIEW_DISPLAY_NAME} quality failure: the model returned findings, but none became actionable inline comments. "
            f"Rejected findings: {details}."
        )

    summary = str(result.get("summary", "")).strip()
    if getattr(config, "fail_on_summary_only_problem", True) and summary_suggests_problem(summary):
        raise ReviewQualityError(
            f"{base.REVIEW_DISPLAY_NAME} quality failure: the model summary indicated a possible issue, but the structured findings "
            "array was empty. The review must produce actionable file/line findings or a clean summary."
        )

    return [], []


def enforce_risk_sentinel_findings(
    findings: list[dict[str, Any]],
    risk_sentinels: list[RiskSentinel],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> None:
    if not risk_sentinels or not getattr(config, "risk_sentinel_quality_gate", True):
        return
    uncovered = uncovered_risk_sentinels(findings, risk_sentinels, config, unanchored_findings)
    if not uncovered:
        return
    raise ReviewQualityError(
        f"{base.REVIEW_DISPLAY_NAME} quality failure: the changed diff contained high-risk changed-line signals, but the model "
        "did not produce actionable findings covering those signals after quality retry. Uncovered signals: "
        f"{risk_sentinel_coverage_digest(uncovered)}."
    )


