

assert mod.has_prior_successful_context_review(FakeGitHubClient([{"body": mod.base.MARKER}]), 287) is False
assert (
    mod.has_prior_successful_context_review(
        FakeGitHubClient([{"body": f"{mod.base.MARKER}\n\n{mod.CONTEXT_REVIEW_MARKER} `first-pass-deep`"}]),
        287,
    )
    is True
)
assert mod.has_prior_successful_context_review(FakeGitHubClient([{"body": mod.base.MARKER}] * 100), 287) is False

alias_context = mod.build_python_path_alias_context(
    FakeGitHubClient(),
    {"head": {"sha": "abc123def4567890"}},
    [
        {"filename": "tools/aliased_writer.py", "status": "modified"},
        {"filename": "docs/review.md", "status": "modified"},
    ],
)
assert alias_context == {"tools/aliased_writer.py": {"P", "pl.Path"}}
os_alias_context = mod.build_python_os_alias_context(
    FakeGitHubClient(),
    {"head": {"sha": "abc123def4567890"}},
    [
        {"filename": "tools/aliased_writer.py", "status": "modified"},
        {"filename": "docs/review.md", "status": "modified"},
    ],
)
assert os_alias_context == {"tools/aliased_writer.py": {"operating_system"}}

deep_block, deep_summary = mod.build_deep_context_block(
    FakeGitHubClient(),
    {"head": {"sha": "abc123def4567890"}},
    [
        {"filename": "tools/review_probe.py", "status": "added"},
        {"filename": "docs/review.md", "status": "modified"},
        {"filename": "old/deleted.py", "status": "removed"},
    ],
    config,
    "first-pass-deep",
)
assert "Deep changed-file context" in deep_block
assert "tools/review_probe.py" in deep_block
assert "subprocess.run(command, shell=True)" in deep_block
assert "included 2 file context block" in deep_summary
assert "old/deleted.py (deleted)" in deep_summary

diff_block, diff_summary = mod.build_deep_context_block(FakeGitHubClient(), {}, [], config, "diff")
assert diff_block == ""
assert "diff-focused" in diff_summary

limited_config = mod.copy.copy(config)
limited_config.deep_review_max_files = 1
mixed_block, mixed_summary = mod.build_deep_context_block(
    FakeGitHubClient(),
    {"head": {"sha": "abc123def4567890"}},
    [
        {"filename": "old/deleted.py", "status": "removed"},
        {"filename": "missing/unavailable.py", "status": "modified"},
        {"filename": "tools/later_probe.py", "status": "modified"},
    ],
    limited_config,
    "first-pass-deep",
)
assert "tools/later_probe.py" in mixed_block
assert "included 1 file context block" in mixed_summary
assert "old/deleted.py (deleted)" in mixed_summary
assert "missing/unavailable.py" in mixed_summary

large_block, large_summary = mod.build_deep_context_block(
    FakeGitHubClient(),
    {"head": {"sha": "abc123def4567890"}},
    [
        {"filename": "large/oversized.py", "status": "modified"},
        {"filename": "tools/later_probe.py", "status": "modified"},
    ],
    limited_config,
    "first-pass-deep",
)
assert "tools/later_probe.py" in large_block
assert "large/oversized.py (file exceeds GitHub content API limit (>1 MB)" in large_summary

budget_config = mod.copy.copy(config)
budget_config.deep_review_max_files = 1
budget_config.deep_review_max_file_chars = 5000
budget_config.deep_review_max_total_chars = 520
budget_block, budget_summary = mod.build_deep_context_block(
    FakeGitHubClient(),
    {"head": {"sha": "abc123def4567890"}},
    [{"filename": "tools/huge_probe.py", "status": "modified"}],
    budget_config,
    "first-pass-deep",
)
assert "tools/huge_probe.py" in budget_summary
assert "[deep context budget exhausted]" in budget_block
assert budget_block.count("~~~") % 2 == 0

prompt_context = (
    "Deep changed-file context:\n\n"
    "### tools/huge_probe.py\n"
    "Status: modified; head ref: abc123def456\n"
    "~~~python\n"
    + ("print('large prompt context')\n" * 3000)
    + "\n~~~"
)
prompt_truncated = mod.build_prompt(
    {"number": 287, "title": "Prompt fence balance", "body": "Exercise prompt-level context truncation."},
    [{"filename": "tools/huge_probe.py", "status": "modified", "additions": 500, "deletions": 0, "changes": 500}],
    "diff --git a/tools/huge_probe.py b/tools/huge_probe.py\n",
    config,
    [],
    prompt_context,
    "first-pass-deep",
    "first-pass-deep; included 1 file context block(s): tools/huge_probe.py (truncated)",
)
assert mod.DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER.strip() in prompt_truncated
assert prompt_truncated.count("~~~") % 2 == 0

prompt = mod.build_prompt(
    {"number": 287, "title": "Deep context probe", "body": "Test first-pass context."},
    [{"filename": "tools/review_probe.py", "status": "added", "additions": 2, "deletions": 0, "changes": 2}],
    "diff --git a/tools/review_probe.py b/tools/review_probe.py\n",
    config,
    [],
    deep_block,
    "first-pass-deep",
    deep_summary,
)
assert "Context mode: first-pass-deep" in prompt
assert "Deep changed-file context" in prompt
assert "subprocess.run(command, shell=True)" in prompt
assert "exact correction guidance" in prompt
assert "smallest safe patch direction" in prompt
assert "GitHub apply-ready suggestions" in prompt
assert "precise single-line replacement for the commented line" in prompt
assert "multiline, range, or speculative fixes" in prompt
assert "selected range" not in prompt

small_config = mod.copy.copy(config)
small_config.max_prompt_chars = 900
small_prompt = mod.build_prompt(
    {"number": 287, "title": "Small prompt", "body": "Ensure hardening survives."},
    [{"filename": "tools/review_probe.py", "status": "added", "additions": 2, "deletions": 0, "changes": 2}],
    "diff --git a/tools/review_probe.py b/tools/review_probe.py\n",
    small_config,
    [],
    deep_block + ("\nextra context" * 500),
    "first-pass-deep",
    deep_summary,
)
assert len(small_prompt) <= small_config.max_prompt_chars
assert small_prompt.startswith("Governed review hardening requirements:")
assert "Every semantic, Markdown, governance, validation, or review-gate concern" in small_prompt
assert mod.CONTEXT_REVIEW_MARKER not in small_prompt
assert mod.DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER.strip() not in small_prompt


# Review-assist artifact context must only be loaded from the trusted extraction path.
class ReviewAssistContextConfig:
    deep_review_max_total_chars = 80


original_context_root = mod.REVIEW_ASSIST_CONTEXT_ROOT
original_context_report = mod.REVIEW_ASSIST_CONTEXT_REPORT
original_context_env = os.environ.get("REVIEW_ASSIST_CONTEXT_PATH")
try:
    with tempfile.TemporaryDirectory() as context_tmp:
        context_root = Path(context_tmp) / "review-assist-context"
        report_rel = Path("project_sources/collector/powershell_review_assist_workflow_report.md")
        report_path = context_root / report_rel
        report_path.parent.mkdir(parents=True)
        report_path.write_text("review assist findings\n" * 10, encoding="utf-8")

        mod.REVIEW_ASSIST_CONTEXT_ROOT = context_root
        mod.REVIEW_ASSIST_CONTEXT_REPORT = report_rel
        os.environ["REVIEW_ASSIST_CONTEXT_PATH"] = str(report_path)
        loaded_context = mod.load_review_assist_context(ReviewAssistContextConfig())
        assert loaded_context.startswith("review assist findings")
        assert "review-assist context truncated" in loaded_context

        outside_path = Path(context_tmp) / "outside.md"
        outside_path.write_text("secret-ish outside context", encoding="utf-8")
        os.environ["REVIEW_ASSIST_CONTEXT_PATH"] = str(outside_path)
        assert mod.load_review_assist_context(ReviewAssistContextConfig()) == ""
finally:
    mod.REVIEW_ASSIST_CONTEXT_ROOT = original_context_root
    mod.REVIEW_ASSIST_CONTEXT_REPORT = original_context_report
    if original_context_env is None:
        os.environ.pop("REVIEW_ASSIST_CONTEXT_PATH", None)
    else:
        os.environ["REVIEW_ASSIST_CONTEXT_PATH"] = original_context_env
