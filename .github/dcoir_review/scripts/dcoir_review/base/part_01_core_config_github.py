#!/usr/bin/env python3
"""Summoned DCOIR PR reviewer for GitHub Actions.

This script is intentionally dependency-free. It reads a PR diff through the
GitHub API, asks OpenRouter for structured findings, and posts a GitHub PR
review with inline suggestion blocks when safe. It never pushes commits and it
never checks out or executes untrusted PR code.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GITHUB_API = "https://api.github.com"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"
MARKER = "<!-- dcoir-review -->"
LEGACY_MARKERS = ("<!-- openrouter-pr-review -->",)
REVIEW_DISPLAY_NAME = "DCOIR Review"
DEBUG_ARTIFACT_DIR_ENV = "DCOIR_REVIEW_DEBUG_ARTIFACT_DIR"
DEBUG_ARTIFACT_DEFAULT_DIR = "dcoir-review-debug"
DEBUG_ARTIFACT_MAX_CHARS = 250_000
DEBUG_ARTIFACT_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-/]+$")
PUBLIC_IDENTITY_REPLACEMENTS = (
    ("OPENROUTER_API_KEY", "REVIEW_PROVIDER_API_KEY"),
    ("OPENROUTER_REVIEW_CONFIG", "REVIEW_PROVIDER_CONFIG"),
    ("OPENROUTER_", "REVIEW_PROVIDER_"),
    ("OpenRouter PR Review", REVIEW_DISPLAY_NAME),
    ("OpenRouter PR review", REVIEW_DISPLAY_NAME),
    ("OpenRouter Review", REVIEW_DISPLAY_NAME),
    ("OpenRouter review", REVIEW_DISPLAY_NAME),
    ("OpenRouter", "review provider"),
    ("openrouter_key", "review_provider_key"),
    ("openrouter-pr-review", "dcoir-review"),
    ("openrouter-review", "dcoir-review"),
    ("openrouter/", "provider/"),
    ("openrouter:", "provider:"),
    ("openrouter-", "provider-"),
    ("openrouter_", "provider_"),
    ("openrouter", "provider"),
)
REDACTION = "[redacted-secret]"
GITHUB_MENTION = re.compile(
    r"(?<![A-Za-z0-9_.+-])@(?P<mention>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?(?:/[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?)?)(?=$|[^A-Za-z0-9_/-])"
)
CODEX_TRIGGER_MENTION = re.compile(
    r"(?<![A-Za-z0-9_.+-])@(?P<mention>codex|chatgpt-codex-connector)(?=$|[^A-Za-z0-9_-])", re.IGNORECASE
)


@dataclass
class Config:
    commands: list[str]
    model: str
    model_stack: list[str]
    max_prompt_chars: int
    max_files: int
    max_inline_comments: int
    request_changes_on_findings: bool
    minimum_confidence: float
    validation_commands: list[str]
    guidance_files: list[str]
    ignored_authors: list[str]
    allowed_authors: list[str]
    post_summary_when_findings: bool
    include_confidence: bool
    redact_secret_literals: bool
    openrouter_max_attempts: int
    openrouter_retry_max_seconds: int
    ignored_providers: list[str]
    script_timeout_seconds: int
    post_progress_comment: bool
    debug: bool


def read_text(path: str, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def workflow_run_id() -> str:
    return os.environ.get("GITHUB_RUN_ID", "").strip()


def workflow_run_url() -> str:
    run_id = workflow_run_id()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").strip() or "https://github.com"
    if not run_id or not repo:
        return ""
    return f"{server.rstrip('/')}/{repo}/actions/runs/{run_id}"


def workflow_run_status_lines(config: Config) -> list[str]:
    run_id = sanitize_github_output(workflow_run_id(), config)
    if not run_id:
        return []
    url = sanitize_github_output(workflow_run_url(), config)
    if url:
        return [f"- Workflow run: [`{run_id}`]({url})."]
    return [f"- Workflow run id: `{run_id}`."]


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_yaml_like_config(path: str) -> Config:
    """Parse the tiny YAML subset used by .github/dcoir_review/openrouter-pr-review.yml."""

    raw = read_text(path)
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            data[key] = [] if value == "" else parse_scalar(value)
        elif current_key and stripped.startswith("-"):
            item = stripped[1:].strip()
            data.setdefault(current_key, []).append(parse_scalar(item))

    model = str(data.get("model", "openrouter/free"))
    raw_stack = data.get("model_stack", [])
    model_stack = [str(item) for item in raw_stack] if isinstance(raw_stack, list) else []
    if not model_stack:
        model_stack = [model]

    return Config(
        commands=list(data.get("commands", ["/or-review", "/openrouter-review", "/dcoir-review"])),
        model=model,
        model_stack=model_stack,
        max_prompt_chars=int(data.get("max_prompt_chars", 60000)),
        max_files=int(data.get("max_files", 30)),
        max_inline_comments=int(data.get("max_inline_comments", 12)),
        request_changes_on_findings=bool(data.get("request_changes_on_findings", False)),
        minimum_confidence=float(data.get("minimum_confidence", 0.70)),
        validation_commands=list(data.get("validation_commands", [])),
        guidance_files=list(data.get("guidance_files", [])),
        ignored_authors=list(data.get("ignored_authors", [])),
        allowed_authors=list(data.get("allowed_authors", [])),
        post_summary_when_findings=bool(data.get("post_summary_when_findings", False)),
        include_confidence=bool(data.get("include_confidence", False)),
        redact_secret_literals=bool(data.get("redact_secret_literals", True)),
        openrouter_max_attempts=int(data.get("openrouter_max_attempts", 4)),
        openrouter_retry_max_seconds=int(data.get("openrouter_retry_max_seconds", 45)),
        ignored_providers=list(data.get("ignored_providers", [])),
        script_timeout_seconds=int(data.get("script_timeout_seconds", 1500)),
        post_progress_comment=bool(data.get("post_progress_comment", False)),
        debug=bool(data.get("debug", False)),
    )


def env_required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"missing required environment variable {name}")
    return value


class ReviewTimeoutError(TimeoutError):
    """Raised by the script-level timeout before the workflow job timeout."""


class GitHubClient:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo

    def request(
        self,
        method: str,
        path: str,
        body: Any | None = None,
        accept: str = "application/vnd.github+json",
    ) -> Any:
        url = f"{GITHUB_API}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dcoir-review",
        }
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = response.read()
                if accept.endswith(".diff") or accept == "application/vnd.github.v3.diff":
                    return payload.decode("utf-8", errors="replace")
                if not payload:
                    return {}
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc

    def get_pr(self, number: int) -> dict[str, Any]:
        return self.request("GET", f"/repos/{self.repo}/pulls/{number}")

    def get_pr_diff(self, number: int) -> str:
        return self.request("GET", f"/repos/{self.repo}/pulls/{number}", accept="application/vnd.github.v3.diff")

    def list_files(self, number: int) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.request("GET", f"/repos/{self.repo}/pulls/{number}/files?per_page=100&page={page}")
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    def create_issue_comment(self, number: int, body: str) -> dict[str, Any]:
        return self.request("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": body})

    def update_issue_comment(self, comment_id: int, body: str) -> dict[str, Any]:
        return self.request("PATCH", f"/repos/{self.repo}/issues/comments/{comment_id}", {"body": body})

    def create_issue_comment_reaction(self, comment_id: int, content: str) -> dict[str, Any]:
        return self.request("POST", f"/repos/{self.repo}/issues/comments/{comment_id}/reactions", {"content": content})

    def delete_issue_comment_reaction(self, comment_id: int, reaction_id: int) -> dict[str, Any]:
        return self.request("DELETE", f"/repos/{self.repo}/issues/comments/{comment_id}/reactions/{reaction_id}")

    def create_review(self, number: int, body: str, event: str, comments: list[dict[str, Any]], commit_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"event": event, "comments": comments, "commit_id": commit_id}
        if body.strip():
            payload["body"] = body
        return self.request("POST", f"/repos/{self.repo}/pulls/{number}/reviews", payload)


def github_safe_body(text: str, limit: int = 65000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 200] + f"\n\n[truncated by {REVIEW_DISPLAY_NAME}]"


def actions_notice_escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def append_step_summary(stage: str, message: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not summary_path:
        return
    try:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(f"- **{stage}:** {message}\n")
    except OSError as exc:
        print(f"WARN: unable to write step summary: {exc}", file=sys.stderr, flush=True)


def emit_status(stage: str, message: str) -> None:
    print(f"[dcoir-review] {stage}: {message}", flush=True)
    print(f"::notice title={REVIEW_DISPLAY_NAME}::{actions_notice_escape(stage + ': ' + message)}", flush=True)
    append_step_summary(stage, message)


def matching_command(body: str, commands: list[str]) -> str | None:
    first_line = body.strip().splitlines()[0].strip() if body.strip() else ""
    for command in commands:
        if re.fullmatch(rf"{re.escape(command)}(?:\s+.*)?", first_line):
            return command
    return None


def command_arguments(body: str, command: str) -> str:
    first_line = body.strip().splitlines()[0].strip() if body.strip() else ""
    match = re.fullmatch(rf"{re.escape(command)}(?:\s+(?P<args>.*))?", first_line)
    return (match.group("args") or "").strip() if match else ""


def command_requests_debug(body: str, command: str) -> bool:
    args = command_arguments(body, command).lower()
    if not args:
        return False
    if re.search(r"(?:^|[\s,])(?:--)?debug\s*[:=]?\s*(?:false|0|no|off)\b", args):
        return False
    if re.search(r"(?:^|[\s,])(?:--)?debug(?:\s*[:=]\s*|\s+)(?:true|1|yes|on)\b", args):
        return True
    tokens = re.split(r"[\s,]+", args)
    truthy = {"debug", "--debug", "debug=true", "debug:true", "debug=1", "debug:1", "verbose", "verbose=true"}
    falsy = {"debug=false", "debug:false", "debug=0", "debug:0", "nodebug", "no-debug", "--no-debug"}
    if any(token in falsy for token in tokens):
        return False
    return any(token in truthy for token in tokens)


def apply_debug_flag(config: Config, body: str, command: str) -> None:
    if config.debug or command_requests_debug(body, command):
        config.debug = True
        config.post_progress_comment = True


def command_matches(body: str, commands: list[str]) -> bool:
    return matching_command(body, commands) is not None


def provider_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower()).strip("-")


def model_stack_label(config: Config) -> str:
    return ", ".join(config.model_stack)


def neutralize_github_mentions(text: str) -> str:
    return GITHUB_MENTION.sub(lambda match: f"@<!-- -->{match.group('mention')}", text)


def neutralize_codex_trigger_mentions(text: str) -> str:
    return CODEX_TRIGGER_MENTION.sub(lambda match: f"@<!-- -->{match.group('mention')}", text)


def sanitize_public_identity(text: str) -> str:
    cleaned = text
    for old, new in PUBLIC_IDENTITY_REPLACEMENTS:
        cleaned = cleaned.replace(old, new)
    return cleaned


