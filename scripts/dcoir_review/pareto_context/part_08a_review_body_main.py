def review_assist_context_path(raw_path: str) -> Path | None:
    """Return the trusted review-assist context path or reject unexpected paths."""
    if not raw_path.strip():
        return None

    root = REVIEW_ASSIST_CONTEXT_ROOT.resolve(strict=False)
    expected = (root / REVIEW_ASSIST_CONTEXT_REPORT).resolve(strict=False)
    candidate = Path(raw_path).resolve(strict=False)
    if candidate != expected:
        raise ValueError(f"unexpected review-assist context path: {candidate}")
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"review-assist context path escapes trusted extraction root: {candidate}")
    return candidate


def load_review_assist_context(config: Any) -> str:
    """Read the trusted PSScriptAnalyzer/review-assist markdown context if set."""
    context_path = os.environ.get("REVIEW_ASSIST_CONTEXT_PATH", "").strip()
    if not context_path:
        return ""
    try:
        trusted_context_path = review_assist_context_path(context_path)
        if trusted_context_path is None:
            return ""
        content = trusted_context_path.read_text(encoding="utf-8")
        max_chars = int(getattr(config, "deep_review_max_total_chars", 24000)) // 2
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...(review-assist context truncated)"
        return content.strip()
    except Exception as exc:
        print(f"WARN: could not load review-assist context from {context_path}: {exc}", file=sys.stderr, flush=True)
        return ""


def main() -> None:
    repo = base.env_required("GITHUB_REPOSITORY")
    pr_number = int(base.env_required("PR_NUMBER"))
    token = base.env_required("GITHUB_TOKEN")
    trigger_comment_id = int(base.env_required("TRIGGER_COMMENT_ID"))
    comment_body = os.environ.get("TRIGGER_COMMENT_BODY", "")
    author = os.environ.get("TRIGGER_AUTHOR", "")
    config_path = os.environ.get("OPENROUTER_REVIEW_CONFIG", ".github/openrouter-pr-review-pareto.yml")
    config = load_pareto_context_config(config_path)

    if author in config.ignored_authors:
        print(f"Ignoring denied author {author}")
        return
    if config.allowed_authors and author not in config.allowed_authors:
        print(f"Ignoring unauthorized author {author}")
        return
    command = hardened.matching_command(comment_body, config.commands)
    if not command:
        print("Comment does not match configured review commands")
        return
    if hasattr(base, "apply_debug_flag"):
        base.apply_debug_flag(config, comment_body, command)

    def timeout_handler(_signum: int, _frame: Any) -> None:
        raise hardened.ReviewTimeoutError(f"{base.REVIEW_DISPLAY_NAME} exceeded script timeout of {config.script_timeout_seconds} seconds")

    schema = json.loads(base.read_text("schemas/openrouter-pr-review.schema.json"))
    gh = base.GitHubClient(token, repo)
    reporter = hardened.ProgressReporter(gh, pr_number, command, config)
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
        base.env_required("OPENROUTER_API_KEY")  # Validate required secret; request code reads it again.
        reporter.start()
        reporter.update("reaction", f"eyes add: {reaction_status['added']}")
        reporter.update("github", "fetching PR metadata")
        pr = gh.get_pr(pr_number)
        reporter.update("github", "fetching PR diff")
        diff = gh.get_pr_diff(pr_number)
        reporter.update("github", "fetching changed file list")
        files = gh.list_files(pr_number)
        set_python_path_alias_context(build_python_path_alias_context(gh, pr, files))
        set_python_os_alias_context(build_python_os_alias_context(gh, pr, files))
        try:
            prior_successful_review = has_prior_successful_context_review(gh, pr_number)
            reporter.update("review-mode", f"prior context review found: {str(prior_successful_review).lower()}")
        except Exception as exc:
            prior_successful_review = False
            reporter.update("review-mode", f"prior context review readback failed; using first-pass posture: {str(exc)[:240]}")
        review_mode = review_mode_for_command(comment_body, command, config, prior_successful_review)
        deep_context_block, context_summary = build_deep_context_block(gh, pr, files, config, review_mode)
        review_assist_ctx = load_review_assist_context(config)
        if review_assist_ctx:
            ra_header = "PowerShell static analysis context from last validate-on-pr run (PSScriptAnalyzer + review-assist):"
            deep_context_block = f"{ra_header}\n\n{review_assist_ctx}\n\n---\n\n{deep_context_block}".strip()
            reporter.update("review-assist-context", f"injected {len(review_assist_ctx)} chars of PSScriptAnalyzer context")
        safe_context_summary = sanitize_context_summary(context_summary, config)
        reporter.update("context", safe_context_summary)
        risk_sentinels = hardened.detect_risk_sentinels(diff, getattr(config, "risk_sentinel_max_anchors", 12))
        if risk_sentinels and getattr(config, "risk_sentinel_quality_gate", True):
            reporter.update("risk-sentinel", f"detected {len(risk_sentinels)} high-risk changed-line signals: {hardened.risk_sentinel_digest(risk_sentinels)}")
        line_index = hardened.build_added_line_index(diff)
        prompt_mode = "per-file first-pass prompts" if should_use_per_file_first_pass(review_mode, config) else "bounded whole-PR prompt"
        reporter.update("prompt", f"building {prompt_mode} from {len(files)} changed files")
        hardened.write_debug_json_artifact_safely(
            config,
            "metadata/review-context.json",
            {
                "pr_number": pr_number,
                "reviewed_head_sha": str(pr.get("head", {}).get("sha", "") or ""),
                "command": command,
                "debug": bool(getattr(config, "debug", False)),
                "workflow_run_id": base.workflow_run_id() if hasattr(base, "workflow_run_id") else os.environ.get("GITHUB_RUN_ID", ""),
                "workflow_run_url": base.workflow_run_url() if hasattr(base, "workflow_run_url") else "",
                "review_mode": review_mode,
                "context_summary": context_summary,
                "review_assist_context_chars": len(review_assist_ctx),
                "deep_context_chars": len(deep_context_block),
                "prompt_mode": prompt_mode,
                "prompt_chars": 0 if should_use_per_file_first_pass(review_mode, config) else "",
                "risk_sentinel_count": len(risk_sentinels),
                "risk_sentinel_digest": hardened.risk_sentinel_digest(risk_sentinels) if risk_sentinels else "",
                "line_index_entries": len(line_index),
                "changed_files": [
                    {
                        "filename": str(item.get("filename", "")),
                        "status": str(item.get("status", "")),
                        "additions": item.get("additions"),
                        "deletions": item.get("deletions"),
                        "changes": item.get("changes"),
                    }
                    for item in files
                ],
            },
        )
        hardened.write_debug_text_artifact_safely(config, "context/deep-context.md", deep_context_block or "(no deep context block)")
        if review_assist_ctx:
            hardened.write_debug_text_artifact_safely(config, "context/static-validation-context.md", review_assist_ctx)
        result, model_used, service_tier = openrouter_review_with_hybrid_first_pass(
            pr,
            files,
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
        )
        reporter.update("normalize", "mapping model findings to changed diff lines")
        findings, unanchored_findings = split_findings_with_review_body_fallback(result, config, line_index, diff, risk_sentinels)
        findings = hardened.add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        hardened.enforce_risk_sentinel_findings(findings, risk_sentinels, config, unanchored_findings)
        findings = synthesize_fixes_for_findings(findings, gh, pr, FIX_SYNTHESIS_SCHEMA, config, reporter)

        comments: list[dict[str, Any]] = []
        for finding in findings:
            path = str(finding["path"])
            line = int(finding["line"])
            comments.append({"path": path, "line": line, "side": "RIGHT", "body": base.build_inline_comment(finding, model_used, config)})

        event = "REQUEST_CHANGES" if comments and config.request_changes_on_findings else "COMMENT"
        reviewed_commit = str(pr.get("head", {}).get("sha", "") or "")
        review_body = append_context_to_review_body(
            hardened.build_review_body_with_unanchored(result, findings, unanchored_findings, model_used, config, reviewed_commit),
            review_mode,
            context_summary,
            config,
        )
        unanchored_note = f" and {len(unanchored_findings)} unanchored review-body findings" if unanchored_findings else ""
        reporter.update("github-review", f"posting GitHub review with {len(comments)} inline comments{unanchored_note}")
        gh.create_review(pr_number, review_body, event, comments, reviewed_commit)
        hardened.remove_eyes_reaction(gh, trigger_comment_id, reaction_id, reaction_status)
        tier_note = f"; service_tier={service_tier}" if service_tier else ""
        reporter.update("reaction", f"eyes add: {reaction_status['added']}; eyes remove: {reaction_status['removed']}")
        reporter.complete(f"{model_used}{tier_note}", len(comments), event)
    except Exception as exc:
        hardened.remove_eyes_reaction(gh, trigger_comment_id, reaction_id, reaction_status)
        try:
            reporter.update("reaction", f"eyes add: {reaction_status['added']}; eyes remove: {reaction_status['removed']}")
        except Exception as reporter_exc:
            print(f"WARN: unable to update reaction status: {reporter_exc}", file=sys.stderr, flush=True)
        reporter.fail(hardened.sanitize_github_output(str(exc), config))
        raise
    finally:
        set_python_path_alias_context({})
        set_python_os_alias_context({})
        if config.script_timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
            signal.alarm(0)


if __name__ == "__main__":
    main()
