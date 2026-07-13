truncation_config = replace(config, max_prompt_chars=420, guidance_files=[])
truncated_prompt = mod.build_prompt(
    {"number": 281, "title": "Boundary", "body": "A" * 320 + f" password={punctuation_password} " + private_key_block + "B" * 320},
    [],
    f"diff --git a/t.py b/t.py\n+++ b/t.py\n@@ -1 +1 @@\n+Authorization: Bearer {bearer_secret}\n+Cookie: {cookie_secret}\n+URL: {generic_signed_url}\n",
    truncation_config,
)
assert punctuation_password not in truncated_prompt, truncated_prompt
assert bearer_secret not in truncated_prompt, truncated_prompt
assert "cookie-secret" not in truncated_prompt, truncated_prompt
assert signed_url_secret not in truncated_prompt, truncated_prompt
assert "PRIVATE KEY" not in truncated_prompt, truncated_prompt
assert len(truncated_prompt) <= truncation_config.max_prompt_chars + 40

comment = mod.build_inline_comment(
    {
        "title": "Hardcoded token from @codex",
        "severity": "critical",
        "confidence": 1.0,
        "path": "collector/token_probe.py",
        "body": f'The changed line assigns token = "{secret_like}", password={punctuation_password}, and Authorization: Bearer "{bearer_secret}" plus Authorization: Bearer \\"{bearer_secret}\\". Ask @codex to review.',
        "suggested_replacement": 'token = os.getenv("OPENROUTER_TOKEN")',
        "validation": "python3 -m py_compile collector/token_probe.py",
    },
    "openrouter/free",
    config,
)
assert "Confidence:" not in comment
assert "sk_live_demo" not in comment
assert punctuation_password not in comment
assert "os.getenv" in comment
assert "@codex" not in comment
assert "@<!-- -->codex" in comment
assert "Model:" not in comment
assert "openrouter/free" not in comment
assert "<sub>DCOIR Review</sub>" in comment
assert "python3 -m py_compile collector/token_probe.py" in comment
assert "bandit -r collector/token_probe.py" in comment
ps_comment = mod.build_inline_comment(
    {
        "title": "Unsafe PowerShell path write",
        "severity": "high",
        "confidence": 0.95,
        "path": "tools/probe.ps1",
        "body": "Set-Content writes to a request-controlled path.",
        "suggested_replacement": "",
        "validation": "",
    },
    "openrouter/free",
    config,
)
assert 'PSParser]::Tokenize((Get-Content -Raw -LiteralPath "tools/probe.ps1")' in ps_comment
assert 'Invoke-ScriptAnalyzer -Path "tools/probe.ps1"' in ps_comment
sanitized_identity = mod.sanitize_github_output(
    "OpenRouter review quality failure from openrouter/auto using OPENROUTER_API_KEY and openrouter_key",
    config,
)
assert "OpenRouter" not in sanitized_identity
assert "openrouter/" not in sanitized_identity
assert "OPENROUTER_API_KEY" not in sanitized_identity
assert "openrouter_key" not in sanitized_identity
assert "DCOIR Review" in sanitized_identity
assert "REVIEW_PROVIDER_API_KEY" in sanitized_identity
sanitized_progress_identity = mod.sanitize_github_output(
    "openrouter openrouter-attempt openrouter-result openrouter-retry openrouter/pareto-code",
    config,
)
assert sanitized_progress_identity == "provider provider-attempt provider-result provider-retry provider/pareto-code"
with tempfile.TemporaryDirectory() as tmp:
    previous_debug_artifact_dir = os.environ.get("DCOIR_REVIEW_DEBUG_ARTIFACT_DIR")
    os.environ["DCOIR_REVIEW_DEBUG_ARTIFACT_DIR"] = tmp
    try:
        quiet_path = mod.write_debug_text_artifact(config, "quiet.txt", "quiet output")
        assert quiet_path is None
        assert not (Path(tmp) / "quiet.txt").exists()

        debug_path = mod.write_debug_text_artifact(
            debug_config,
            "prompts/01-initial-prompt.txt",
            f"OpenRouter prompt with OPENROUTER_API_KEY={openrouter_key}; ask @codex to inspect",
        )
        assert debug_path == (Path(tmp) / "prompts/01-initial-prompt.txt").resolve(strict=False)
        debug_text = debug_path.read_text(encoding="utf-8")
        assert "OpenRouter" not in debug_text
        assert openrouter_key not in debug_text
        assert "REVIEW_PROVIDER_API_KEY" in debug_text
        assert "@<!-- -->codex" in debug_text

        json_path = mod.write_debug_json_artifact(
            debug_config,
            "metadata/review-context.json",
            {"provider": "OpenRouter", "secret": openrouter_key, "items": ["openrouter", "@codex"]},
        )
        debug_json = json.loads(json_path.read_text(encoding="utf-8"))
        assert debug_json["provider"] == "review provider"
        assert debug_json["secret"] == "[redacted-secret]"
        assert debug_json["items"] == ["provider", "@<!-- -->codex"]

        try:
            mod.write_debug_text_artifact(debug_config, "../escape.txt", "escape")
        except ValueError as exc:
            assert "unsafe debug artifact name" in str(exc)
        else:
            raise AssertionError("debug artifact path traversal should be rejected")
    finally:
        if previous_debug_artifact_dir is None:
            os.environ.pop("DCOIR_REVIEW_DEBUG_ARTIFACT_DIR", None)
        else:
            os.environ["DCOIR_REVIEW_DEBUG_ARTIFACT_DIR"] = previous_debug_artifact_dir

review_body = mod.build_review_body({"summary": "No findings. Ask @codex and @malwaredevil to review."}, [], "openrouter/free", config)
assert "💡 DCOIR Review" in review_body
assert "Reviewed commit: `unavailable`" in review_body
assert "Model:" not in review_body
assert "OpenRouter" not in review_body
assert "@codex" not in review_body
assert "@malwaredevil" not in review_body
assert "@<!-- -->codex" in review_body
assert "@<!-- -->malwaredevil" in review_body

class FakeGitHub:
    def __init__(self) -> None:
        self.comments: list[str] = []
        self.updates: list[str] = []

    def create_issue_comment(self, _number: int, body: str) -> dict[str, int]:
        self.comments.append(body)
        return {"id": 123}

    def update_issue_comment(self, _comment_id: int, body: str) -> dict[str, str]:
        self.updates.append(body)
        return {}

fake_gh = FakeGitHub()
failure_reporter = mod.ProgressReporter(fake_gh, 281, "/or-review", config)
