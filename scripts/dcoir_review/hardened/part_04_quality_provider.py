def raw_findings_digest(result: dict[str, Any]) -> str:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return "findings field was not a list"
    details: list[str] = []
    for item in raw_findings[:6]:
        if not isinstance(item, dict):
            details.append("invalid finding shape")
            continue
        raw_path = item.get("path")
        raw_line = item.get("line")
        raw_title = item.get("title")
        path = str(raw_path).strip() if raw_path else "<missing-path>"
        line = str(raw_line).strip() if raw_line else "<missing-line>"
        title = (str(raw_title).strip() if raw_title else "untitled")[:80]
        try:
            confidence = float(item.get("confidence", 0))
            confidence_text = f"{confidence:.2f}"
        except (TypeError, ValueError):
            confidence_text = "invalid"
        details.append(f"{path}:{line} confidence {confidence_text} ({title})")
    return "; ".join(details) if details else "no structured findings"


def finding_text_for_quality(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("title", "") or ""),
        str(item.get("body", "") or ""),
        str(item.get("validation", "") or ""),
    ]
    return re.sub(r"\s+", " ", "\n".join(parts)).strip()


def non_actionable_finding_reason(item: dict[str, Any]) -> str:
    text = finding_text_for_quality(item)
    if not text:
        return ""
    for pattern, reason in NON_ACTIONABLE_FINDING_PATTERNS:
        if pattern.search(text):
            return reason
    return ""


def non_actionable_findings_digest(result: dict[str, Any], config: Any) -> str:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return ""
    details: list[str] = []
    for item in raw_findings[:6]:
        if not isinstance(item, dict):
            continue
        reason = non_actionable_finding_reason(item)
        if not reason:
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < config.minimum_confidence:
            continue
        raw_path = item.get("path")
        raw_line = item.get("line")
        raw_title = item.get("title")
        path = str(raw_path).strip() if raw_path else "<missing-path>"
        line = str(raw_line).strip() if raw_line else "<missing-line>"
        title = (str(raw_title).strip() if raw_title else "untitled")[:80]
        details.append(f"{path}:{line} {reason} ({title})")
    return "; ".join(details)



def has_minimum_confidence_finding(result: dict[str, Any], config: Any) -> bool:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return False
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        try:
            if float(item.get("confidence", 0)) >= config.minimum_confidence:
                return True
        except (TypeError, ValueError):
            continue
    return False



def has_actionable_minimum_confidence_finding(result: dict[str, Any], config: Any) -> bool:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return False
    for item in raw_findings:
        if not isinstance(item, dict) or non_actionable_finding_reason(item):
            continue
        try:
            if float(item.get("confidence", 0)) >= config.minimum_confidence:
                return True
        except (TypeError, ValueError):
            continue
    return False

def has_actionable_changed_line_finding(
    result: dict[str, Any],
    config: Any,
    line_index: dict[tuple[str, int], int],
) -> bool:
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return False
    for item in raw_findings:
        if not isinstance(item, dict) or non_actionable_finding_reason(item):
            continue
        try:
            confidence = float(item.get("confidence", 0))
            line = int(item.get("line", 0))
            path = str(item.get("path", "")).strip()
        except (TypeError, ValueError):
            continue
        if confidence >= config.minimum_confidence and (path, line) in line_index:
            return True
    return False


def review_quality_retry_reason(
    result: dict[str, Any],
    config: Any,
    risk_sentinels: list[RiskSentinel],
    line_index: dict[tuple[str, int], int] | None = None,
) -> str:
    gated_sentinels = required_risk_sentinels(risk_sentinels)
    if (
        gated_sentinels
        and getattr(config, "risk_sentinel_quality_gate", True)
        and getattr(config, "risk_sentinel_retry_on_empty", True)
        and has_no_structured_findings(result)
    ):
        return "model returned zero findings despite high-risk changed-line signals"

    if not getattr(config, "review_quality_retry_on_rejected_output", True):
        return ""

    summary = str(result.get("summary", "")).strip()
    if has_no_structured_findings(result):
        if getattr(config, "fail_on_summary_only_problem", True) and summary_suggests_problem(summary):
            return "model summary indicated a possible issue while the structured findings array was empty"
        return ""

    raw_findings = result.get("findings", [])
    if raw_findings and getattr(config, "fail_on_unanchored_findings", True):
        non_actionable_details = non_actionable_findings_digest(result, config)
        if non_actionable_details and not has_actionable_minimum_confidence_finding(result, config):
            return (
                "model returned only self-described non-actionable or informational findings: "
                f"{non_actionable_details}"
            )
        if not has_minimum_confidence_finding(result, config):
            return (
                "model returned structured findings, but none met the configured minimum confidence "
                f"{config.minimum_confidence:.2f}: {raw_findings_digest(result)}"
            )
        if line_index is not None and not has_actionable_changed_line_finding(result, config, line_index):
            return (
                "model returned high-confidence structured findings, but none were anchored to changed diff lines: "
                f"{raw_findings_digest(result)}"
            )
        if (
            gated_sentinels
            and line_index is not None
            and getattr(config, "risk_sentinel_quality_gate", True)
        ):
            try:
                findings, unanchored_findings = split_findings(result, config, line_index)
            except ReviewQualityError:
                findings, unanchored_findings = [], []
            uncovered = uncovered_risk_sentinels(findings, gated_sentinels, config, unanchored_findings)
            if uncovered:
                return (
                    "model returned actionable findings, but they did not cover high-risk changed-line signals: "
                    f"{risk_sentinel_coverage_digest(uncovered)}"
                )

    return ""


def build_quality_retry_prompt(
    prompt: str,
    previous_result: dict[str, Any],
    risk_sentinels: list[RiskSentinel],
    config: Any,
    quality_issue: str | None = None,
) -> str:
    previous_summary = str(previous_result.get("summary", "")).strip() or "No previous summary returned."
    raw_findings = previous_result.get("findings", [])
    try:
        previous_findings = json.dumps(raw_findings[:6] if isinstance(raw_findings, list) else raw_findings, ensure_ascii=False, indent=2)
    except TypeError:
        previous_findings = str(raw_findings)
    if len(previous_findings) > 1800:
        previous_findings = f"{previous_findings[:1770]}... [truncated]"
    issue_line = quality_issue or "the previous response did not clear review-quality checks"
    anchor_block = risk_sentinel_block(risk_sentinels, config) if risk_sentinels else "No high-risk changed-line anchors were detected."
    retry_guidance = f"""
Review quality retry:
The previous response failed review-quality checks: {issue_line}.
Re-review the changed diff and return one of two valid outputs:
- Actionable findings anchored to changed right-side file/line entries with confidence at or above {config.minimum_confidence:.2f}, covering every high-risk anchor by path, nearby line, and risk class; or
- An empty findings array with a clean summary that does not imply a remaining issue.
Return the full corrected finding set. Preserve previous real actionable findings while adding or repairing missing anchor coverage; do not narrow the retry response to only the uncovered anchor.
Do not place actionable concerns only in the summary. Do not return low-confidence, unanchored, or speculative findings.
Do not return informational/advisory findings that explain there is no realized risk; use a clean summary for those.
Do not satisfy a high-risk anchor with an unrelated finding on another risk class.
If a previous finding was real but poorly anchored or below confidence threshold, convert it into a valid finding with exact file, changed line, observed behavior, impact, correction guidance, and validation/readback guidance.

{anchor_block}

Previous summary:
{previous_summary}

Previous structured findings:
{previous_findings}
""".strip()
    return append_with_budget(prompt, base.sanitize_text(retry_guidance, config), config.max_prompt_chars)


def has_no_structured_findings(result: dict[str, Any]) -> bool:
    findings = result.get("findings", [])
    return not isinstance(findings, list) or len(findings) == 0


