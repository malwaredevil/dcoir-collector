safe_reference = mod.sanitize_text(
    'token = os.getenv("OPENROUTER_TOKEN")\npassword = process.env.DB_PASSWORD\napi_key=${OPENROUTER_API_KEY}\nsecret: ${{ secrets.OPENROUTER_TOKEN }}',
    config,
)
assert 'os.getenv("OPENROUTER_TOKEN")' in safe_reference
assert "process.env.DB_PASSWORD" in safe_reference
assert "${OPENROUTER_API_KEY}" in safe_reference
assert "${{ secrets.OPENROUTER_TOKEN }}" in safe_reference

original_read_text = mod.read_text

def fake_read_text(path: str, default: str = "") -> str:
    if path == "guidance-secret.md":
        return "\n".join(
            [
                f"Guidance bearer Authorization: Bearer {bearer_secret}",
                f"Guidance object header \"Authorization\": \"Bearer {bearer_secret}\"",
                f"Guidance cookie Cookie: {cookie_secret}",
                f"Guidance URL postgres://dcoir:{url_password}@db.example.test/dcoir",
                f"Guidance signed {aws_signed_url}",
                f"Guidance token={unsafe_getenv_suffix}",
                f"Guidance safe token: {github_secret_reference}",
                private_key_block,
            ]
        )
    return original_read_text(path, default)

mod.read_text = fake_read_text
try:
    prompt_config = replace(config, guidance_files=["guidance-secret.md"])
    prompt = mod.build_prompt(
        {
            "number": 281,
            "title": f"Prompt redaction {openrouter_key}",
            "body": "\n".join(
                [
                    f"body token {secret_like}",
                    f"OPENROUTER_API_KEY={openrouter_key}",
                    f'"password": "{quoted_json_password}"',
                    f'"Authorization": "Bearer {bearer_secret}"',
                    f'"Cookie": "{cookie_secret}"',
                    f"Authorization: Bearer {bearer_secret}",
                    f'Authorization: Bearer "{bearer_secret}"',
                    f'Authorization: Bearer \\"{bearer_secret}\\"',
                    f"Cookie: {cookie_secret}",
                    f"DATABASE_URL=postgres://dcoir:{url_password}@db.example.test/dcoir",
                    f'curl --user "dcoir:benign\n{curl_multiline_double_quote_password}" https://example.test/',
                    aws_signed_url,
                    private_key_block,
                    f'"token": "{process_env_reference}"',
                    f'"password": "{unsafe_process_reference}"',
                    f"token={unsafe_getenv_default}",
                ]
            ),
        },
        [
            {
                "filename": f"example-{openai_key}.py",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
                "patch": "\n".join(
                    [
                        f"+token = '{secret_like}'",
                        f"+password={punctuation_password}",
                        f"+Authorization: Bearer {bearer_secret}",
                        f'+Authorization: Bearer "{bearer_secret}"',
                        f'+Authorization: Bearer \\"{bearer_secret}\\"',
                        f"+Cookie: {cookie_secret}",
                        f'+headers = {{"Authorization": "Bearer {bearer_secret}", "Cookie": "{cookie_secret}"}}',
                        f"+DATABASE_URL=postgres://dcoir:{url_password}@db.example.test/dcoir",
                        f'+curl --proxy-user "proxy:benign\n{curl_multiline_single_quote_password}" https://example.test/',
                        f"+SIGNED={generic_signed_url}",
                        "+" + private_key_block.replace("\n", "\n+"),
                        f'+\"password\": \"{quoted_json_password}\"',
                        f'+\"password\": \"{apostrophe_password}\"',
                        f'+\"password\": \"{escaped_quote_password}\"',
                        f'+\"token\": \"{process_env_reference}\"',
                        f'+\"token\": \"{github_secret_reference}\"',
                        f'+\"password\": \"{unsafe_process_reference}\"',
                        f"+token={unsafe_getenv_suffix}",
                        f"+token={unsafe_f_string}",
                    ]
                ),
            }
        ],
        "\n".join(
            [
                "diff --git a/example.py b/example.py",
                "+++ b/example.py",
                "@@ -1,0 +1,14 @@",
                f"+token = '{secret_like}'",
                f"+OPENAI_API_KEY={openai_key}",
                f"+PASSWORD={delimiter_password}",
                f"+Authorization: Basic {basic_secret}",
                f'+Authorization: Basic "{basic_secret}"',
                f'+Authorization: Basic \\"{basic_secret}\\"',
                f"+Set-Cookie: {set_cookie_secret}",
                f'+headers = {{"Authorization": "Basic {basic_secret}", "Set-Cookie": "{set_cookie_secret}"}}',
                f"+NETRC machine example.test login dcoir password {netrc_password}",
                f"+SIGNED {azure_sas_url}",
                "+" + private_key_block.replace("\n", "\n+"),
                f'+\"password\": \"{quoted_json_password}\"',
                f'+\"password\": \"{escaped_quote_password}\"',
                f'+\"token\": \"{process_env_reference}\"',
                f'+\"password\": \"{unsafe_process_reference}\"',
                f"+password={unsafe_shell_suffix}",
                "",
            ]
        ),
        prompt_config,
    )
finally:
    mod.read_text = original_read_text

for leaked in [
    "sk_live_demo",
    "sk-or-v1",
    "sk-proj",
    punctuation_password,
    delimiter_password,
    quoted_json_password,
    apostrophe_password,
    escaped_quote_password,
    bearer_secret,
    basic_secret,
    "cookie-secret",
    "connect-secret",
    "csrf-secret",
    "refresh-cookie-secret",
    curl_multiline_double_quote_password,
    curl_multiline_single_quote_password,
    url_password,
    netrc_password,
    signed_url_secret,
    sas_secret,
    "PRIVATE KEY",
    "private-key-secret-material",
    unsafe_process_reference,
    unsafe_getenv_suffix,
    unsafe_getenv_default,
    unsafe_shell_suffix,
    "tail-secret",
    "fallback-secret",
    "actual-secret",
]:
    assert leaked not in prompt, prompt
assert process_env_reference in prompt, prompt
assert github_secret_reference in prompt, prompt
assert "[redacted-secret]" in prompt
assert r"\"quoted-json-password" not in prompt, prompt
assert r"bearer-secret" not in prompt, prompt
assert r"cookie-secret" not in prompt, prompt

