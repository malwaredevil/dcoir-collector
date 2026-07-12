PRIVATE_KEY_BLOCK = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE | re.DOTALL)
SECRET_VALUE_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9_])sk-(?:or|proj|live|test)?-?[A-Za-z0-9][A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])sk_[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]
URL_PASSWORD_CREDENTIAL = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^/\s:@?#]*):([^@\s/]+)@")
URL_TOKEN_CREDENTIAL = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)((?:gh[pousr]_|github_pat_|sk-(?:or|proj|live|test)?-?)[^@\s/]+)@"
)
SIGNED_URL_QUERY_CREDENTIAL = re.compile(
    r"(?i)([?&](?:x-amz-signature|x-amz-credential|x-amz-security-token|awsaccesskeyid|signature|sig|sas|se|sp|sv|sr|spr|st|skoid|sktid|skt|ske|sks|skv|token|access_token|refresh_token|sessiontoken|session_token)=)([^&#\s\"']+)"
)
HEADER_CREDENTIAL = re.compile(
    r"""(?ix)(?<![A-Z0-9_\-])(?P<name_quote>[\"']?)(?P<name>(?:proxy-)?authorization|x-api-key|api-key|x-auth-token|x-access-token)(?P=name_quote)(?P<sep>\s*[:=]\s*)(?P<quote>[\"']?)(?:(?P<scheme>bearer|basic|token)\s+)?(?P<value>(?![$`])[^\"'\s,;)}\r\n]+)(?P=quote)(?=$|[\s\r\n\"',;)}])"""
)
HEADER_FIELD_CREDENTIAL_START = re.compile(
    r"""(?ix)(?<![A-Z0-9_\-])(?P<name_quote>[\"']?)(?P<name>(?:proxy-)?authorization|x-api-key|api-key|x-auth-token|x-access-token|cookie|set-cookie)(?P=name_quote)(?P<sep>\s*[:=]\s*)(?P<value_prefix>[rubf]{0,2})(?P<value_quote>[\"'])"""
)

UNQUOTED_HEADER_CREDENTIAL_START = re.compile(
    r"""(?ix)(?<![A-Z0-9_\-])(?P<name_quote>[\"']?)(?P<name>(?:proxy-)?authorization|x-api-key|api-key|x-auth-token|x-access-token)(?P=name_quote)(?P<sep>\s*[:=]\s*)(?!\s*[\"'])"""
)

COOKIE_UNQUOTED_FIELD_START = re.compile(
    r"""(?ix)(?<![A-Z0-9_\-])(?P<name_quote>[\"']?)(?P<name>cookie|set-cookie)(?P=name_quote)(?P<sep>\s*[:=]\s*)(?!\s*[\"'])"""
)
# Cookie pairs use name=value, so only colon-delimited object fields end inline cookies.
OBJECT_FIELD_AFTER_COMMA = re.compile(r"""(?ix)^\s*[\"']?[A-Z0-9_\-]+[\"']?\s*:""")
HEADER_VALUE_SCHEME = re.compile(r"(?is)^(?P<prefix>\s*(?:bearer|basic|token)\s+)(?P<secret>.+)$")
CURL_USER_OPTION = re.compile(r"""(?ix)(?P<prefix>(?<!\S)(?:--(?:proxy-)?user(?:\s+|=)|-u\s*))""")
NETRC_PASSWORD_CREDENTIAL = re.compile(r"(?i)\b(machine\s+\S+\s+login\s+\S+\s+password\s+)(\S{4,})")
SECRET_QUOTED_ASSIGNMENT_START = re.compile(
    r"""(?ix)(?<![A-Z0-9_\-])(?P<key_quote>[\"']?)(?P<key>[A-Z0-9_\-]*(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY)[A-Z0-9_\-]*)(?P=key_quote)(?P<sep>\s*[:=]\s*)(?P<value_prefix>[rubf]{0,2})(?P<value_quote>[\"'])"""
)
SECRET_UNQUOTED_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<prefix>(?<![A-Z0-9_\-])(?P<key_quote>[\"']?)(?P<key>[A-Z0-9_\-]*(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY)[A-Z0-9_\-]*)(?P=key_quote)(?P<sep>\s*[:=]\s*))
    (?P<value>
        \$\{\{[^\r\n]*\}\}
        | os\.getenv\([^\r\n]*?\)[^\r\n]*
        | os\.environ\.get\([^\r\n]*?\)[^\r\n]*
        | os\.environ\[[^\r\n]*?\][^\r\n]*
        | os\.environ\b[^\r\n]*
        | env\.get\([^\r\n]*?\)[^\r\n]*
        | getenv\([^\r\n]*?\)[^\r\n]*
        | process\.env[^\r\n]*
        | import\.meta\.env[^\r\n]*
        | secrets\.get\([^\r\n]*?\)[^\r\n]*
        | [^\s\"']{8,}
    )"""
)
SAFE_REFERENCE = re.compile(
    r"""(?ix)^(?:
    os\.getenv\(\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*(?:,\s*(?:""|''|None)\s*)?\)
    | os\.environ(?:\.get\(\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*(?:,\s*(?:""|''|None)\s*)?\)|\[\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*\])
    | env\.get\(\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*(?:,\s*(?:""|''|None)\s*)?\)
    | getenv\(\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*(?:,\s*(?:""|''|None)\s*)?\)
    | process\.env(?:\.[A-Z_][A-Z0-9_]*|\[\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*\])
    | import\.meta\.env(?:\.[A-Z_][A-Z0-9_]*|\[\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*\])
    | secrets\.get\(\s*[\"'][A-Z_][A-Z0-9_]*[\"']\s*\)
    | \$\{\{\s*(?:secrets|env|vars)\.[A-Z_][A-Z0-9_]*\s*\}\}
)$"""
)
ENV_REFERENCE = re.compile(r"^(?:\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\})$")


def is_safe_reference(value: str) -> bool:
    stripped = value.strip()
    return bool(SAFE_REFERENCE.fullmatch(stripped) or ENV_REFERENCE.fullmatch(stripped))


def is_safe_unquoted_reference(value: str) -> bool:
    return is_safe_reference(value)


def is_safe_quoted_reference(value: str) -> bool:
    return is_safe_reference(value)


def find_quoted_value_end(text: str, start: int, quote: str) -> int:
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == quote:
            return index
        if char in {"\r", "\n"}:
            return -1
    return -1


def find_curl_quoted_value_end(text: str, start: int, quote: str) -> int:
    escaped = False
    line_start = start
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"\r", "\n"}:
            line_start = index + 1
            continue
        if char == quote:
            if line_start > start and CURL_USER_OPTION.search(text[line_start:index]):
                return -1
            return index
    return -1


def redact_private_key_blocks(text: str) -> str:
    return PRIVATE_KEY_BLOCK.sub(REDACTION, text)


def redact_url_credentials(text: str) -> str:
    cleaned = URL_PASSWORD_CREDENTIAL.sub(lambda match: f"{match.group(1)}{match.group(2)}:{REDACTION}@", text)
    cleaned = URL_TOKEN_CREDENTIAL.sub(lambda match: f"{match.group(1)}{REDACTION}@", cleaned)
    return SIGNED_URL_QUERY_CREDENTIAL.sub(lambda match: f"{match.group(1)}{REDACTION}", cleaned)


def redact_header_credential(match: re.Match[str]) -> str:
    value = match.group("value").strip()
    if not value or is_safe_header_secret_value(value):
        return match.group(0)
    scheme = match.group("scheme")
    tail = match.string[match.end():].lstrip()
    if scheme is None and value.lower() in {"bearer", "basic", "token"}:
        if tail[:1] in {'"', "'"}:
            return match.group(0)
    if scheme is not None and value == "\\" and tail[:1] in {'"', "'"}:
        return match.group(0)
    scheme_prefix = f"{scheme} " if scheme else ""
    return f"{match.group('name_quote')}{match.group('name')}{match.group('name_quote')}{match.group('sep')}{match.group('quote')}{scheme_prefix}{REDACTION}{match.group('quote')}"

def is_inline_object_cookie_context(text: str, field_start: int) -> bool:
    line_start = text.rfind("\n", 0, field_start) + 1
    last_open = max(text.rfind("{", line_start, field_start), text.rfind("[", line_start, field_start))
    if last_open < 0:
        return False
    last_close = max(text.rfind("}", line_start, field_start), text.rfind("]", line_start, field_start))
    return last_close < last_open


def find_unquoted_cookie_value_end(text: str, start: int, inline_object: bool) -> int:
    interpolation_depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "$" and index + 1 < len(text) and text[index + 1] == "{":
            if index + 2 < len(text) and text[index + 2] == "{":
                interpolation_depth += 2
                index += 3
            else:
                interpolation_depth += 1
                index += 2
            continue
        if char == "}" and interpolation_depth:
            interpolation_depth -= 1
            index += 1
            continue
        if char in {"\r", "\n"}:
            return index
        if inline_object and char in {"}", "]"}:
            return index
        if inline_object and char == "," and OBJECT_FIELD_AFTER_COMMA.match(text[index + 1 :]):
            return index
        index += 1
    return len(text)


def redact_unquoted_cookie_credentials(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in COOKIE_UNQUOTED_FIELD_START.finditer(text):
        if match.start() < cursor:
            continue
        value_start = match.end()
        inline_object = is_inline_object_cookie_context(text, match.start())
        value_end = find_unquoted_cookie_value_end(text, value_start, inline_object)
        value = text[value_start:value_end].strip()
        if not value or value == REDACTION or is_safe_reference(value):
            continue
        result.append(text[cursor:value_start])
        result.append(REDACTION)
        cursor = value_end
    if not result:
        return text
    result.append(text[cursor:])
    return "".join(result)


