def command_option_tokens(body: str, command: str) -> set[str]:
    first_line = body.strip().splitlines()[0].strip() if body.strip() else ""
    if not first_line.startswith(command):
        return set()
    suffix = first_line[len(command) :].strip().lower()
    return {token for token in re.split(r"[\s,]+", suffix) if token}


def review_mode_for_command(body: str, command: str, config: Any, prior_successful_review: bool) -> str:
    tokens = command_option_tokens(body, command)
    if {"deep", "exhaustive"} & tokens:
        return "deep-forced"
    if "diff" in tokens:
        return "diff"
    if getattr(config, "first_pass_deep_review", True) and not prior_successful_review:
        return "first-pass-deep"
    return "diff"


def list_pr_reviews(gh: Any, pr_number: int) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = gh.request("GET", f"/repos/{gh.repo}/pulls/{pr_number}/reviews?per_page=100&page={page}")
        if not batch:
            break
        reviews.extend(batch)
        if len(batch) < 100:
            break
        # Exact multiples of 100 cost one extra empty-page readback, which is
        # acceptable for the small PR review counts this workflow expects.
        page += 1
    return reviews


def has_prior_successful_context_review(gh: Any, pr_number: int) -> bool:
    markers = (base.MARKER, *getattr(base, "LEGACY_MARKERS", ()))
    for review in list_pr_reviews(gh, pr_number):
        body = str(review.get("body", ""))
        if any(marker in body for marker in markers) and CONTEXT_REVIEW_MARKER in body:
            return True
    return False


def language_hint(path: str) -> str:
    suffix = Path(path).suffix.lower()
    # Common review surfaces get language hints; uncommon suffixes safely fall
    # back to plain text instead of expanding the prompt grammar surface.
    return {
        ".bash": "bash",
        ".cjs": "javascript",
        ".js": "javascript",
        ".json": "json",
        ".md": "markdown",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".sh": "bash",
        ".ts": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def fetch_pr_file_text(gh: Any, path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    payload = gh.request("GET", f"/repos/{gh.repo}/contents/{encoded_path}?ref={encoded_ref}")
    if not isinstance(payload, dict) or payload.get("type") != "file":
        raise RuntimeError("content API did not return a file")
    encoding = payload.get("encoding")
    content = payload.get("content")
    if content is None or (content == "" and encoding == "none"):
        raise RuntimeError("file exceeds GitHub content API limit (>1 MB); omitting from deep context")
    if encoding != "base64":
        raise RuntimeError("content API did not return base64 text")
    raw = base64.b64decode(str(content).replace("\n", ""))
    return raw.decode("utf-8")


FIX_SYNTHESIS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Review Fix Synthesis",
    "type": "object",
    "additionalProperties": False,
    "required": ["suggested_replacement", "remove", "replace", "add", "notes", "validation"],
    "properties": {
        "suggested_replacement": {
            "type": "string",
            "description": "Exact replacement code for the anchored review line only. Empty string if unsafe or not exact.",
        },
        "remove": {"type": "string", "description": "Code or behavior to remove when no native suggestion is safe."},
        "replace": {"type": "string", "description": "Replacement code or behavior when no native suggestion is safe."},
        "add": {"type": "string", "description": "Additional guard, validation, or test code to add when needed."},
        "notes": {"type": "string", "description": "Short implementation caveat. Empty when unnecessary."},
        "validation": {"type": "string", "description": "Exact validation command or commands that should pass after the fix."},
    },
}
