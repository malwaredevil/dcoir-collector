failure_message = "\n".join(
    [
        f"Authorization: Bearer {bearer_secret}",
        f'Authorization: Bearer "{bearer_secret}"',
        f'Authorization: Bearer \\"{bearer_secret}\\"',
        f"Cookie: {cookie_secret}",
        f"DATABASE_URL=postgres://dcoir:{url_password}@db.example.test/dcoir",
        f"curl --user=:{curl_fallback_expression} https://example.test/",
        f"curl --proxy-user=:{curl_proxy_fallback_expression} https://example.test/",
        f"curl --user=:{curl_inner_brace_expression} https://example.test/",
        f"curl --user=:{curl_unclosed_expression} https://example.test/",
        f"curl --user=:{curl_backtick_expression} https://example.test/",
        f"curl --user=:{curl_multiline_backtick_expression} https://example.test/",
        f"curl --user=:{curl_multiline_backtick_tail_expression} https://example.test/",
        f'curl --user "dcoir:benign\n{curl_multiline_double_quote_password}" https://example.test/',
        f"curl --proxy-user 'proxy:benign\n{curl_multiline_single_quote_password}' https://example.test/",
        f"curl --user $'dcoir:benign\n{curl_multiline_ansi_quote_password}' https://example.test/",
        f'curl --proxy-user $"proxy:benign\n{curl_multiline_locale_quote_password}" https://example.test/',
        f"curl --user=$':{curl_ansi_password}' https://example.test/",
        f'curl --user=$":{curl_locale_password}" https://example.test/',
        f"curl --user=:{curl_escaped_space_password} https://example.test/",
        f"curl --user=:concat' {curl_concat_password}' https://example.test/",
        generic_signed_url,
        private_key_block,
        "Ask @codex to review this failure.",
        f'curl --user="dcoir:{curl_unclosed_quoted_password} https://example.test/',
        f"curl --proxy-user='proxy:{curl_proxy_unclosed_quoted_password} https://example.test/",
    ]
)
failure_reporter.fail(failure_message)
assert fake_gh.comments == []

debug_failure_config = replace(config, debug=True, post_progress_comment=True)
debug_fake_gh = FakeGitHub()
debug_failure_reporter = mod.ProgressReporter(debug_fake_gh, 281, "/or-review", debug_failure_config)
debug_failure_reporter.fail(failure_message)
failure_body = debug_fake_gh.comments[-1]
for leaked in [
    bearer_secret,
    "cookie-secret",
    url_password,
    signed_url_secret,
    "fallback curl secret",
    "proxy fallback secret",
    "fallback }} curl secret",
    "unclosed curl secret",
    "backtick curl secret",
    "multiline backtick curl secret",
    "multiline backtick tail secret",
    curl_unclosed_quoted_password,
    curl_proxy_unclosed_quoted_password,
    curl_multiline_double_quote_password,
    curl_multiline_single_quote_password,
    curl_multiline_ansi_quote_password,
    curl_multiline_locale_quote_password,
    "ansi curl secret",
    "locale curl secret",
    r"escaped\ curl\ secret",
    "concat curl secret",
    "PRIVATE KEY",
    "private-key-secret-material",
    "@codex",
]:
    assert leaked not in failure_body, failure_body
assert "@<!-- -->codex" in failure_body
assert "[redacted-secret]" in failure_body

previous_run_id = os.environ.get("GITHUB_RUN_ID")
previous_repo = os.environ.get("GITHUB_REPOSITORY")
previous_server = os.environ.get("GITHUB_SERVER_URL")
try:
    os.environ["GITHUB_RUN_ID"] = "28186071891"
    os.environ["GITHUB_REPOSITORY"] = "DCOIR-Collector/dcoir-collector"
    os.environ["GITHUB_SERVER_URL"] = "https://github.com"
    debug_run_fake_gh = FakeGitHub()
    debug_run_reporter = mod.ProgressReporter(debug_run_fake_gh, 314, "/dcoir-review", debug_failure_config)
    debug_run_reporter.start()
    debug_run_body = debug_run_fake_gh.comments[-1]
    assert "- Workflow run: [`28186071891`](https://github.com/DCOIR-Collector/dcoir-collector/actions/runs/28186071891)." in debug_run_body
finally:
    if previous_run_id is None:
        os.environ.pop("GITHUB_RUN_ID", None)
    else:
        os.environ["GITHUB_RUN_ID"] = previous_run_id
    if previous_repo is None:
        os.environ.pop("GITHUB_REPOSITORY", None)
    else:
        os.environ["GITHUB_REPOSITORY"] = previous_repo
    if previous_server is None:
        os.environ.pop("GITHUB_SERVER_URL", None)
    else:
        os.environ["GITHUB_SERVER_URL"] = previous_server

err = mod.parse_openrouter_error('{"error":{"message":"Provider returned error","metadata":{"provider_name":"Venice","retry_after_seconds":21}}}')
assert err["provider"] == "Venice"
assert err["retry_after"] == 21

assert mod.is_safe_suggestion('token = os.getenv("OPENROUTER_TOKEN")')
assert not mod.is_safe_suggestion("Use environment variables for secrets.")


header_fallback_secret = "fallback header secret 12345"
header_command_secret = "command header secret 12345"
header_ansi_secret = "ansi header secret 12345"
header_line_continuation_secret = "header continuation secret 12345"
header_quoted_secret = "quoted header secret 12345"
escaped_quoted_header_secret = "escaped quoted header secret 12345"
header_fallback_expression = "${{ secrets.AUTH_TOKEN || '" + header_fallback_secret + "' }}"
header_command_expression = "$(printf '" + header_command_secret + "')"
header_ansi_expression = "$'" + header_ansi_secret + "'"
header_line_continuation = "\\" + "\n  " + header_line_continuation_secret
header_regression_cases = [
    (f"Authorization: Bearer {header_fallback_expression}", header_fallback_secret),
    (f"Proxy-Authorization: Basic {header_command_expression}", header_command_secret),
    (f"Authorization: Bearer {header_ansi_expression}", header_ansi_secret),
    (f"Authorization: Bearer {header_line_continuation}", header_line_continuation_secret),
    (f'Authorization: Bearer "{header_quoted_secret}"', header_quoted_secret),
    (f"Proxy-Authorization: Basic '{header_quoted_secret}'", header_quoted_secret),
    (f'Authorization: Bearer \\"{escaped_quoted_header_secret}\\"', escaped_quoted_header_secret),
    (f'Proxy-Authorization: Basic \\"{escaped_quoted_header_secret}\\"', escaped_quoted_header_secret),
]
for safe_quoted_header in [
    'Authorization: Bearer "${OPENROUTER_API_KEY}"',
    "Proxy-Authorization: Basic '${OPENROUTER_API_KEY}'",
    'Authorization: Bearer \\"${OPENROUTER_API_KEY}\\"',
]:
    assert mod.sanitize_text(safe_quoted_header, config) == safe_quoted_header

for header_form, header_secret in header_regression_cases:
    sanitized_header = mod.sanitize_text(header_form, config)
    assert header_secret not in sanitized_header, sanitized_header
    assert "[redacted-secret]" in sanitized_header, sanitized_header

curl_continuation_password = "continued curl secret 12345"
curl_proxy_continuation_password = "continued-proxy-curl-secret-12345"
curl_inline_continuation_password = "inline-continued-curl-secret-12345"
line_continuation = "\\" + "\n"
crlf_line_continuation = "\\" + "\r\n"
curl_continuation_cases = [
    (f'curl --user {line_continuation}  "dcoir:{curl_continuation_password}" https://example.test/', curl_continuation_password),
    (f"curl --proxy-user {crlf_line_continuation}  dcoir:{curl_proxy_continuation_password} https://example.test/", curl_proxy_continuation_password),
    (f"curl --user dcoir:{line_continuation}  {curl_inline_continuation_password} https://example.test/", curl_inline_continuation_password),
]
for curl_form, curl_secret in curl_continuation_cases:
    sanitized_curl = mod.sanitize_text(curl_form, config)
    assert curl_secret not in sanitized_curl, sanitized_curl
    assert "[redacted-secret]" in sanitized_curl, sanitized_curl

combined_regression_prompt = mod.build_prompt(
    {
        "number": 281,
        "title": "Continuation redaction",
        "body": "\n".join([
            f"Authorization: Bearer {header_fallback_expression}",
            f'Authorization: Bearer "{header_quoted_secret}"',
            f'Authorization: Bearer \\"{escaped_quoted_header_secret}\\"',
            f"Proxy-Authorization: Basic {header_command_expression}",
            f"curl --user dcoir:{line_continuation}  {curl_inline_continuation_password} https://example.test/",
        ]),
    },
    [],
    "",
    config,
)
for leaked in [
    header_fallback_secret,
    header_command_secret,
    header_ansi_secret,
    header_line_continuation_secret,
    header_quoted_secret,
    escaped_quoted_header_secret,
    curl_continuation_password,
    curl_proxy_continuation_password,
    curl_inline_continuation_password,
]:
    assert leaked not in combined_regression_prompt, combined_regression_prompt

print("offline selftest passed")
