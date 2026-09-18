def main() -> None:
    repo = env_required("GITHUB_REPOSITORY")
    pr_number = int(env_required("PR_NUMBER"))
    token = env_required("GITHUB_TOKEN")
    trigger_comment_id = int(env_required("TRIGGER_COMMENT_ID"))
    comment_body = os.environ.get("TRIGGER_COMMENT_BODY", "")
    author = os.environ.get("TRIGGER_AUTHOR", "")
    config_path = os.environ.get("OPENROUTER_REVIEW_CONFIG", ".github/dcoir_review/openrouter-pr-review.yml")
    config = load_yaml_like_config(config_path)

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
    apply_debug_flag(config, comment_body, command)

    def timeout_handler(_signum: int, _frame: Any) -> None:
        raise ReviewTimeoutError(f"{REVIEW_DISPLAY_NAME} exceeded script timeout of {config.script_timeout_seconds} seconds")

    schema = json.loads(read_text(".github/dcoir_review/schemas/openrouter-pr-review.schema.json"))
    gh = GitHubClient(token, repo)
    reporter = ProgressReporter(gh, pr_number, command, config)
    eyes_reaction_id = 0

    try:
        reaction = gh.create_issue_comment_reaction(trigger_comment_id, "eyes")
        eyes_reaction_id = int(reaction.get("id", 0))
    except Exception as exc:
        print(f"WARN: unable to add eyes reaction: {exc}", file=sys.stderr, flush=True)

    try:
        if config.script_timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(config.script_timeout_seconds)
        env_required("OPENROUTER_API_KEY")
        reporter.start()
        reporter.update("github", "fetching PR metadata")
        pr = gh.get_pr(pr_number)
        reviewed_commit = str(pr.get("head", {}).get("sha", "") or "")
        set_reviewed_commit = getattr(reporter, "set_reviewed_commit", None)
        if callable(set_reviewed_commit):
            set_reviewed_commit(reviewed_commit)
        reporter.update("github", "fetching PR diff")
        diff = gh.get_pr_diff(pr_number)
        reporter.update("github", "fetching changed file list")
        files = gh.list_files(pr_number)
        reporter.update("prompt", f"building bounded prompt from {len(files)} changed files")
        prompt = build_prompt(pr, files, diff, config)
        result, model_used = openrouter_review(prompt, schema, config, reporter)
        reporter.update("normalize", "mapping model findings to changed diff lines")
        line_index = build_diff_line_index(diff)
        findings = normalize_findings(result, config, line_index)

        comments: list[dict[str, Any]] = []
        for finding in findings:
            path = str(finding["path"])
            line = int(finding["line"])
            comments.append({"path": path, "line": line, "side": "RIGHT", "body": build_inline_comment(finding, model_used, config)})

        event = "REQUEST_CHANGES" if comments and config.request_changes_on_findings else "COMMENT"
        review_body = build_review_body(result, findings, model_used, config, reviewed_commit)
        reporter.update("github-review", f"posting GitHub review with {len(comments)} inline comments")
        review = gh.create_review(pr_number, review_body, event, comments, reviewed_commit)
        set_formal_review = getattr(reporter, "set_formal_review", None)
        if callable(set_formal_review):
            set_formal_review(review)
        reporter.complete(model_used, len(comments), event)
    except Exception as exc:
        safe_error = sanitize_github_output(str(exc), config)
        reporter.fail(safe_error)
        raise
    finally:
        if config.script_timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
            signal.alarm(0)
        if eyes_reaction_id:
            try:
                gh.delete_issue_comment_reaction(trigger_comment_id, eyes_reaction_id)
            except Exception as exc:
                print(f"WARN: unable to remove eyes reaction: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
