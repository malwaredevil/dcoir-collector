def find_unquoted_curl_credential_end(text: str, start: int) -> int:
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
    return index

def find_command_substitution_end(text: str, start: int) -> int:
    depth = 1
    quote = ""
    escaped = False
    index = start
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in {"\"", "'"}:
            quote = char
            index += 1
            continue
        if text.startswith("$(", index):
            depth += 1
            index += 2
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def find_backtick_substitution_end(text: str, start: int) -> int:
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "`":
            return index
    return -1


def skip_curl_line_continuation_whitespace(text: str, start: int) -> int:
    return skip_line_continuation_whitespace(text, start)

def redact_curl_user_credentials(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in CURL_USER_OPTION.finditer(text):
        if match.start() < cursor:
            continue
        value_start = skip_curl_line_continuation_whitespace(text, match.end())
        if value_start >= len(text):
            continue
        quote_prefix_length = 0
        if text[value_start] == "$" and value_start + 1 < len(text) and text[value_start + 1] in {"\"", "'"}:
            quote_prefix_length = 1
            quote = text[value_start + 1]
        else:
            quote = text[value_start] if text[value_start] in {"\"", "'"} else ""
        if quote:
            credential_start = value_start + quote_prefix_length + 1
            credential_end = find_curl_quoted_value_end(text, credential_start, quote)
            if credential_end < 0:
                credential_end = len(text)
            credential = text[credential_start:credential_end]
        else:
            credential_start = value_start
            credential_end = find_unquoted_curl_credential_end(text, credential_start)
            credential = text[credential_start:credential_end]
        colon_index = credential.find(":")
        if colon_index < 0 or len(credential[colon_index + 1 :].strip()) < 4:
            continue
        password_start = credential_start + colon_index + 1
        result.append(text[cursor:password_start])
        result.append(REDACTION)
        cursor = credential_end
    if not result:
        return text
    result.append(text[cursor:])
    return "".join(result)


def redact_quoted_assignments(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in SECRET_QUOTED_ASSIGNMENT_START.finditer(text):
        if match.start() < cursor:
            continue
        value_start = match.end()
        value_end = find_quoted_value_end(text, value_start, match.group("value_quote"))
        if value_end < 0 or value_end - value_start < 8:
            continue
        value = text[value_start:value_end]
        result.append(text[cursor:value_start])
        result.append(value if is_safe_quoted_reference(value) else REDACTION)
        cursor = value_end
    if not result:
        return text
    result.append(text[cursor:])
    return "".join(result)


def redact_unquoted_assignment(match: re.Match[str]) -> str:
    value = match.group("value")
    if is_safe_unquoted_reference(value):
        return match.group(0)
    stripped = value.rstrip()
    trailing_whitespace = value[len(stripped) :]
    if stripped.endswith(","):
        candidate = stripped[:-1].rstrip()
        candidate_trailing = stripped[len(candidate) :]
        if is_safe_unquoted_reference(candidate):
            return f"{match.group('prefix')}{candidate}{candidate_trailing}{trailing_whitespace}"
    return f"{match.group('prefix')}{REDACTION}"


def sanitize_text(text: str, config: Config) -> str:
    if not config.redact_secret_literals:
        return text
    cleaned = text
    cleaned = redact_private_key_blocks(cleaned)
    cleaned = redact_url_credentials(cleaned)
    cleaned = redact_header_field_credentials(cleaned)
    cleaned = redact_unquoted_cookie_credentials(cleaned)
    cleaned = redact_unquoted_header_credentials(cleaned)
    cleaned = HEADER_CREDENTIAL.sub(redact_header_credential, cleaned)
    cleaned = redact_curl_user_credentials(cleaned)
    cleaned = NETRC_PASSWORD_CREDENTIAL.sub(lambda match: f"{match.group(1)}{REDACTION}", cleaned)
    cleaned = redact_quoted_assignments(cleaned)
    cleaned = SECRET_UNQUOTED_ASSIGNMENT.sub(redact_unquoted_assignment, cleaned)
    for pattern in SECRET_VALUE_PATTERNS:
        cleaned = pattern.sub(REDACTION, cleaned)
    return cleaned


def sanitize_github_output(text: str, config: Config, neutralize_mentions: bool = True) -> str:
    cleaned = sanitize_public_identity(sanitize_text(text, config))
    if neutralize_mentions:
        return neutralize_github_mentions(cleaned)
    return neutralize_codex_trigger_mentions(cleaned)


