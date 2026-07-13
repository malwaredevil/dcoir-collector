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


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_after(text: str, anchor: str, old: str, new: str, label: str) -> str:
    anchor_start = text.find(anchor)
    if anchor_start == -1:
        raise SystemExit(f"{label}: anchor not found")
    old_start = text.find(old, anchor_start)
    if old_start == -1:
        raise SystemExit(f"{label}: target not found after anchor")
    return text[:old_start] + new + text[old_start + len(old) :]


source = read(script_path)
source = replace_function(
    source,
    "find_unquoted_header_credential_end",
    r'''def find_unquoted_header_credential_end(text: str, start: int) -> int:
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
        if text[index] in {'"', "'"}:
            expression_end = find_curl_quoted_value_end(text, index + 1, text[index])
            if expression_end < 0:
                return len(text)
            index = expression_end + 1
            continue
        if text[index] == "\\" and index + 1 < len(text):
            index += 2
            continue
        if text[index] in {"\r", "\n", "\t", " ", ",", ";", ")", "}", "]"}:
            return index
        index += 1
    return index''',
)
source = replace_function(
    source,
    "redact_unquoted_header_credentials",
    r'''def is_safe_header_secret_value(value: str) -> bool:
    stripped = value.strip()
    if is_safe_reference(stripped):
        return True
    if len(stripped) >= 2 and stripped[0] in {'"', "'"} and stripped[-1] == stripped[0]:
        return is_safe_reference(stripped[1:-1].strip())
    if len(stripped) >= 3 and stripped[0] == "$" and stripped[1] in {'"', "'"} and stripped[-1] == stripped[1]:
        return is_safe_reference(stripped[2:-1].strip())
    return False


def redact_unquoted_header_credentials(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in UNQUOTED_HEADER_CREDENTIAL_START.finditer(text):
        if match.start() < cursor:
            continue
        value_start = match.end()
        value_end = find_unquoted_header_value_end(text, value_start)
        value = text[value_start:value_end]
        stripped_value = value.strip()
        if not stripped_value or stripped_value == REDACTION:
            continue
        scheme_match = HEADER_VALUE_SCHEME.fullmatch(value)
        secret_value = scheme_match.group("secret").strip() if scheme_match else stripped_value
        if is_safe_header_secret_value(stripped_value) or (scheme_match and is_safe_header_secret_value(secret_value)):
            continue
        result.append(text[cursor:value_start])
        if scheme_match:
            result.append(f"{scheme_match.group('prefix')}{REDACTION}")
        else:
            leading = value[: len(value) - len(value.lstrip())]
            result.append(f"{leading}{REDACTION}")
        cursor = value_end
    if not result:
        return text
    result.append(text[cursor:])
    return "".join(result)''',
)
for needle in [
    "def is_safe_header_secret_value",
    "if text[index] in {'\"', \"'\"}:",
]:
    if needle not in source:
        raise SystemExit(f"source patch missing expected marker: {needle}")
write(script_path, source)

selftest = read(selftest_path)
selftest = replace_after(
    selftest,
    'assignment_text = "\\n".join(\n',
    '        f"Authorization: Bearer {bearer_secret}",\n',
    '        f"Authorization: Bearer {bearer_secret}",\n'
    '        f\'Authorization: Bearer "{bearer_secret}"\',\n'
    '        f"Proxy-Authorization: Basic \'{basic_secret}\'",\n'
    '        f\'Authorization: token "{github_secret_fallback}"\',\n',
    "assignment_text quoted auth cases",
)
selftest = replace_once(
    selftest,
    '    \'headers = { Authorization: "Bearer ${OPENROUTER_API_KEY}" }\',\n',
    '    \'headers = { Authorization: "Bearer ${OPENROUTER_API_KEY}" }\',\n'
    '    \'Authorization: Bearer "${OPENROUTER_API_KEY}"\',\n',
    "safe_header quoted auth reference",
)
selftest = replace_once(
    selftest,
    '    f\'Authorization: Bearer {bearer_secret}\': \'Authorization: Bearer [redacted-secret]\',\n',
    '    f\'Authorization: Bearer {bearer_secret}\': \'Authorization: Bearer [redacted-secret]\',\n'
    '    f\'Authorization: Bearer "{bearer_secret}"\': \'Authorization: Bearer [redacted-secret]\',\n'
    '    f"Proxy-Authorization: Basic \'{basic_secret}\'": \'Proxy-Authorization: Basic [redacted-secret]\',\n'
    '    f\'Authorization: token "{github_secret_fallback}"\': \'Authorization: token [redacted-secret]\',\n'
    '    \'Authorization: Bearer "${OPENROUTER_API_KEY}"\': \'Authorization: Bearer "${OPENROUTER_API_KEY}"\',\n',
    "header_cases quoted auth expectations",
)
selftest = replace_after(
    selftest,
    '            "body": "\\n".join(\n',
    '                    f"Authorization: Bearer {bearer_secret}",\n',
    '                    f"Authorization: Bearer {bearer_secret}",\n'
    '                    f\'Authorization: Bearer "{bearer_secret}"\',\n',
    "prompt body quoted auth case",
)
selftest = replace_once(
    selftest,
    '                        f"+Authorization: Bearer {bearer_secret}",\n',
    '                        f"+Authorization: Bearer {bearer_secret}",\n'
    '                        f\'+Authorization: Bearer "{bearer_secret}"\',\n',
    "changed file quoted auth case",
)
selftest = replace_once(
    selftest,
    '                f"+Authorization: Basic {basic_secret}",\n',
    '                f"+Authorization: Basic {basic_secret}",\n'
    '                f\'+Authorization: Basic "{basic_secret}"\',\n',
    "unified diff quoted auth case",
)
selftest = replace_once(
    selftest,
    '        "body": f\'The changed line assigns token = "{secret_like}" and password={punctuation_password}. Ask @codex to review.\',\n',
    '        "body": f\'The changed line assigns token = "{secret_like}", password={punctuation_password}, and Authorization: Bearer "{bearer_secret}". Ask @codex to review.\',\n',
    "inline comment quoted auth output",
)
selftest = replace_after(
    selftest,
    "failure_reporter.fail(\n",
    '            f"Authorization: Bearer {bearer_secret}",\n',
    '            f"Authorization: Bearer {bearer_secret}",\n'
    '            f\'Authorization: Bearer "{bearer_secret}"\',\n',
    "failure output quoted auth case",
)
selftest = replace_once(
    selftest,
    'header_line_continuation_secret = "header continuation secret 12345"\n',
    'header_line_continuation_secret = "header continuation secret 12345"\n'
    'header_quoted_secret = "quoted header secret 12345"\n',
    "header regression quoted secret variable",
)
selftest = replace_once(
    selftest,
    '    (f"Authorization: Bearer {header_line_continuation}", header_line_continuation_secret),\n',
    '    (f"Authorization: Bearer {header_line_continuation}", header_line_continuation_secret),\n'
    '    (f\'Authorization: Bearer "{header_quoted_secret}"\', header_quoted_secret),\n'
    '    (f"Proxy-Authorization: Basic \'{header_quoted_secret}\'", header_quoted_secret),\n',
    "header regression quoted cases",
)
selftest = replace_once(
    selftest,
    'for header_form, header_secret in header_regression_cases:\n',
    'for safe_quoted_header in [\n'
    '    \'Authorization: Bearer "${OPENROUTER_API_KEY}"\',\n'
    '    "Proxy-Authorization: Basic \'${OPENROUTER_API_KEY}\'",\n'
    ']:\n'
    '    assert mod.sanitize_text(safe_quoted_header, config) == safe_quoted_header\n'
    '\n'
    'for header_form, header_secret in header_regression_cases:\n',
    "header regression safe quoted references",
)
selftest = replace_once(
    selftest,
    '            f"Authorization: Bearer {header_fallback_expression}",\n',
    '            f"Authorization: Bearer {header_fallback_expression}",\n'
    '            f\'Authorization: Bearer "{header_quoted_secret}"\',\n',
    "combined prompt quoted auth case",
)
selftest = replace_once(
    selftest,
    '    header_line_continuation_secret,\n',
    '    header_line_continuation_secret,\n'
    '    header_quoted_secret,\n',
    "combined prompt quoted auth leaked list",
)
for needle in [
    'Authorization: Bearer "{bearer_secret}"',
    'Authorization: Bearer "${OPENROUTER_API_KEY}"',
    "header_quoted_secret",
]:
    if needle not in selftest:
        raise SystemExit(f"selftest patch missing expected marker: {needle}")
write(selftest_path, selftest)
