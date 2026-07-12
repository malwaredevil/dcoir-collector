def format_unanchored_finding(finding: dict[str, Any], model_used: str, config: Any) -> str:
    title = sanitize_github_output(str(finding.get("title", "Finding")).strip(), config)
    severity = str(finding.get("severity", "medium")).upper()
    path = sanitize_github_output(str(finding.get("path", "<missing-path>")).strip(), config)
    line = sanitize_github_output(str(finding.get("line", "<missing-line>")).strip(), config)
    body = sanitize_github_output(str(finding.get("body", "")).strip(), config)
    validation = sanitize_github_output(base.validation_text_for_finding(finding), config)
    reason = sanitize_github_output(str(finding.get("_unanchored_reason", "not anchored to an added changed line")), config)
    try:
        confidence = float(finding.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    parts = [
        f"**{severity}: {title}**",
        f"- Location: `{path}:{line}`.",
        f"- Inline anchor: {reason}.",
        f"- Confidence: `{confidence:.2f}`.",
    ]
    if body:
        parts.extend(["", body])
    if validation:
        parts.extend(["", "Validation expected after fix:", "", "```text", validation, "```"])
    parts.extend(["", f"<sub>{base.REVIEW_DISPLAY_NAME}</sub>"])
    return "\n".join(parts)


def build_review_body_with_unanchored(
    result: dict[str, Any],
    findings: list[dict[str, Any]],
    unanchored_findings: list[dict[str, Any]],
    model_used: str,
    config: Any,
    reviewed_commit: str = "",
) -> str:
    if not unanchored_findings:
        return base.build_review_body(result, findings, model_used, config, reviewed_commit)
    summary = sanitize_github_output(str(result.get("summary", f"{base.REVIEW_DISPLAY_NAME} completed.")).strip(), config)
    inline_plural = "finding" if len(findings) == 1 else "findings"
    body_plural = "finding" if len(unanchored_findings) == 1 else "findings"
    formatted_unanchored = "\n\n".join(
        format_unanchored_finding(finding, model_used, config) for finding in unanchored_findings
    )
    result_line = (
        f"Review posted with `{len(findings)}` inline {inline_plural} and "
        f"`{len(unanchored_findings)}` unanchored review-body {body_plural}."
    )
    lines = [
        base.MARKER,
        f"💡 {base.REVIEW_DISPLAY_NAME}",
        "Here are some review suggestions for this pull request.",
        "",
        f"Reviewed commit: `{base.short_commit(reviewed_commit)}`",
    ]
    if summary and getattr(config, "post_summary_when_findings", False):
        lines.extend(["", summary])
    lines.extend(
        [
            "",
            f"Result: {result_line}",
            "",
            "Unanchored findings:",
            "",
            formatted_unanchored,
        ]
    )
    return base.github_safe_body(
        "\n".join(lines).strip(),
        limit=12000,
    )


def remove_eyes_reaction(gh: Any, trigger_comment_id: int, reaction_id: int, status: dict[str, str]) -> None:
    if not reaction_id:
        status["removed"] = "not attempted; no eyes reaction id was recorded"
        return
    try:
        gh.delete_issue_comment_reaction(trigger_comment_id, reaction_id)
        status["removed"] = "success"
    except Exception as exc:
        status["removed"] = f"failed: {str(exc)[:500]}"


def main() -> None:
    repo = base.env_required("GITHUB_REPOSITORY")
    pr_number = int(base.env_required("PR_NUMBER"))
    token = base.env_required("GITHUB_TOKEN")
    trigger_comment_id = int(base.env_required("TRIGGER_COMMENT_ID"))
    comment_body = os.environ.get("TRIGGER_COMMENT_BODY", "")
    author = os.environ.get("TRIGGER_AUTHOR", "")
    config_path = os.environ.get("OPENROUTER_REVIEW_CONFIG", ".github/dcoir_review/openrouter-pr-review-governed.yml")
    config = load_hardened_config(config_path)

    if author in config.ignored_authors:
        print(f"Ignoring denied author {author}")
        return
    if config.allowed_authors and author not in config.allowed_authors:
        print(f"Ignoring unauthorized author {author}")
        return
    command = matching_command(comment_body, config.commands)
    if not command:
        print("Comment does not match configured review commands")
        return
    if hasattr(base, "apply_debug_flag"):
        base.apply_debug_flag(config, comment_body, command)

    def timeout_handler(_signum: int, _frame: Any) -> None:
        raise ReviewTimeoutError(f"{base.REVIEW_DISPLAY_NAME} exceeded script timeout of {config.script_timeout_seconds} seconds")

    schema = json.loads(base.read_text(".github/dcoir_review/schemas/openrouter-pr-review.schema.json"))
    gh = base.GitHubClient(token, repo)
    reporter = ProgressReporter(gh, pr_number, command, config)
    reaction_id = 0
    reaction_status = {"added": "not attempted", "removed": "not attempted"}

    try:
        reaction = gh.create_issue_comment_reaction(trigger_comment_id, "eyes")
        reaction_id = int(reaction.get("id", 0))
        reaction_status["added"] = f"success id={reaction_id}" if reaction_id else "success without returned id"
    except Exception as exc:
        reaction_status["added"] = f"failed: {str(exc)[:500]}"
        print(f"WARN: unable to add eyes reaction: {exc}", file=sys.stderr, flush=True)

    try:
        if config.script_timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(config.script_timeout_seconds)
        base.env_required("OPENROUTER_API_KEY")
        reporter.start()
        reporter.update("reaction", f"eyes add: {reaction_status['added']}")
        reporter.update("github", "fetching PR metadata")
        pr = gh.get_pr(pr_number)
        reporter.update("github", "fetching PR diff")
        diff = gh.get_pr_diff(pr_number)
        reporter.update("github", "fetching changed file list")
        files = gh.list_files(pr_number)
        risk_sentinels = detect_risk_sentinels(diff, getattr(config, "risk_sentinel_max_anchors", 12))
        if risk_sentinels and getattr(config, "risk_sentinel_quality_gate", True):
            reporter.update("risk-sentinel", f"detected {len(risk_sentinels)} high-risk changed-line signals: {risk_sentinel_digest(risk_sentinels)}")
        reporter.update("prompt", f"building bounded prompt from {len(files)} changed files")
        prompt = build_prompt(pr, files, diff, config, risk_sentinels)
        line_index = build_added_line_index(diff)
        result, model_used, service_tier = openrouter_review_with_quality_retry(prompt, schema, config, reporter, risk_sentinels, line_index)
        reporter.update("normalize", "mapping model findings to changed diff lines")
        findings, unanchored_findings = split_findings(result, config, line_index)
        findings = add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        enforce_risk_sentinel_findings(findings, risk_sentinels, config, unanchored_findings)

        comments: list[dict[str, Any]] = []
        for finding in findings:
            path = str(finding["path"])
            line = int(finding["line"])
            comments.append({"path": path, "line": line, "side": "RIGHT", "body": base.build_inline_comment(finding, model_used, config)})

        event = "REQUEST_CHANGES" if comments and config.request_changes_on_findings else "COMMENT"
        reviewed_commit = str(pr.get("head", {}).get("sha", "") or "")
        review_body = build_review_body_with_unanchored(result, findings, unanchored_findings, model_used, config, reviewed_commit)
        unanchored_note = f" and {len(unanchored_findings)} unanchored review-body findings" if unanchored_findings else ""
        reporter.update("github-review", f"posting GitHub review with {len(comments)} inline comments{unanchored_note}")
        gh.create_review(pr_number, review_body, event, comments, reviewed_commit)
        remove_eyes_reaction(gh, trigger_comment_id, reaction_id, reaction_status)
        tier_note = f"; service_tier={service_tier}" if service_tier else ""
        reporter.update("reaction", f"eyes add: {reaction_status['added']}; eyes remove: {reaction_status['removed']}")
        reporter.complete(f"{model_used}{tier_note}", len(comments), event)
    except Exception as exc:
        remove_eyes_reaction(gh, trigger_comment_id, reaction_id, reaction_status)
        try:
            reporter.update("reaction", f"eyes add: {reaction_status['added']}; eyes remove: {reaction_status['removed']}")
        except Exception as reporter_exc:
            print(f"WARN: unable to update reaction status: {reporter_exc}", file=sys.stderr, flush=True)
        safe_error = sanitize_github_output(str(exc), config)
        reporter.fail(safe_error)
        raise
    finally:
        if config.script_timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
            signal.alarm(0)


if __name__ == "__main__":
    main()
