from pathlib import Path
import sys

repo = Path(sys.argv[1])
script_path = repo / "scripts" / "openrouter_pr_review.py"
selftest_path = repo / "scripts" / "openrouter_pr_review_selftest.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_function(text: str, name: str, replacement: str) -> str:
    marker = f"def {name}("
    start = text.find(marker)
    if start == -1:
        raise SystemExit(f"Function not found: {name}")
    next_start = text.find("\ndef ", start + 1)
    if next_start == -1:
        raise SystemExit(f"Could not find function boundary after: {name}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[next_start + 1 :]


source = read(script_path)
source = replace_function(
    source,
    "find_unquoted_header_credential_end",
    r'''def skip_line_continuation_whitespace(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text[index] != "\\":
            return index
        if index + 2 < len(text) and text[index + 1] == "\r" and text[index + 2] == "\n":
            index += 3
        elif index + 1 < len(text) and text[index + 1] in {"\r", "\n"}:
            index += 2
        else:
            return index
        while index < len(text) and text[index] in {" ", "\t"}:
            index += 1
    return index


def find_unquoted_header_credential_end(text: str, start: int) -> int:
    index = start
    while index < len(text):
        continuation_index = skip_line_continuation_whitespace(text, index)
        if continuation_index != index:
            index = continuation_index
            continue
        if text.startswith("${{", index):
            expression_end = find_github_expression_end(text, index + 3)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end
            continue
        if text.startswith("${", index):
            expression_end = text.find("}", index + 2)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text.startswith("$(", index):
            expression_end = find_command_substitution_end(text, index + 2)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text[index] == "$" and index + 1 < len(text) and text[index + 1] in {'"', "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 2, text[index + 1])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
        if text[index] == "`":
            expression_end = find_backtick_substitution_end(text, index + 1)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text[index] == "\\" and index + 1 < len(text):
            index += 2
            continue
        if text[index] in {"\r", "\n", "\t", " ", '"', "'", ",", ";", ")", "}", "]"}:
            return index
        index += 1
    return index''',
)
source = replace_function(
    source,
    "skip_curl_line_continuation_whitespace",
    r'''def skip_curl_line_continuation_whitespace(text: str, start: int) -> int:
    return skip_line_continuation_whitespace(text, start)''',
)
source = replace_function(
    source,
    "find_unquoted_curl_credential_end",
    r'''def find_unquoted_curl_credential_end(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text.startswith("${{", index):
            expression_end = find_github_expression_end(text, index + 3)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end
            continue
        if text.startswith("${", index):
            expression_end = text.find("}", index + 2)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text.startswith("$(", index):
            expression_end = find_command_substitution_end(text, index + 2)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text[index] == "$" and index + 1 < len(text) and text[index + 1] in {'"', "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 2, text[index + 1])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
        if text[index] == "`":
            expression_end = find_backtick_substitution_end(text, index + 1)
            if expression_end < 0:
                return find_curl_credential_line_end(text, index)
            index = expression_end + 1
            continue
        if text[index] == "\\":
            continuation_index = skip_line_continuation_whitespace(text, index)
            if continuation_index != index:
                index = continuation_index
                continue
            if index + 1 < len(text):
                index += 2
                continue
        if text[index] in {'"', "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 1, text[index])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
        if text[index] in {"\r", "\n", "\t", " ", '"', "'"}:
            return index
        index += 1
    return index''',
)
for needle in [
    "def skip_line_continuation_whitespace",
    "continuation_index = skip_line_continuation_whitespace(text, index)",
    "return skip_line_continuation_whitespace(text, start)",
    "if text[index] in {'\"', \"'\"}:",
]:
    if needle not in source:
        raise SystemExit(f"source patch missing expected marker: {needle}")
write(script_path, source)

selftest = read(selftest_path)
if "header_line_continuation_secret" not in selftest:
    regression_block = r'''
header_fallback_secret = "fallback header secret 12345"
header_command_secret = "command header secret 12345"
header_ansi_secret = "ansi header secret 12345"
header_line_continuation_secret = "header continuation secret 12345"
header_fallback_expression = "${{ secrets.AUTH_TOKEN || '" + header_fallback_secret + "' }}"
header_command_expression = "$(printf '" + header_command_secret + "')"
header_ansi_expression = "$'" + header_ansi_secret + "'"
header_line_continuation = "\\" + "\n  " + header_line_continuation_secret
header_regression_cases = [
    (f"Authorization: Bearer {header_fallback_expression}", header_fallback_secret),
    (f"Proxy-Authorization: Basic {header_command_expression}", header_command_secret),
    (f"Authorization: Bearer {header_ansi_expression}", header_ansi_secret),
    (f"Authorization: Bearer {header_line_continuation}", header_line_continuation_secret),
]
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
    curl_continuation_password,
    curl_proxy_continuation_password,
    curl_inline_continuation_password,
]:
    assert leaked not in combined_regression_prompt, combined_regression_prompt
'''
    selftest = selftest.replace('\nprint("offline selftest passed")', "\n" + regression_block + '\nprint("offline selftest passed")', 1)
for needle in [
    "header_fallback_expression",
    "header_line_continuation_secret",
    "curl_inline_continuation_password",
    "combined_regression_prompt",
]:
    if needle not in selftest:
        raise SystemExit(f"selftest patch missing expected marker: {needle}")
write(selftest_path, selftest)
