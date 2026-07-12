"""Tenth required-coverage layer for DCOIR Review.

This layer fixes the #334 overflow failure without widening the large reviewer
script. It keeps v9 prompt accounting and rendering, then adds:

- ranked required selection when required sentinels exceed the inline budget
- explicit omitted-sentinel overflow metadata instead of a pre-post crash
- workflow token-to-PR-body URL classification
- workflow PR-label shell metadata classification
- broad write-permission coalescing
- final wording cleanup for HTTPS shell-pipe findings
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v9_core as core
import dcoir_review_required_runtime_patch_v9_selection as selection

SentinelKey = tuple[str, int, str]
_BASE_VALIDATION_FOR_KEY = core._validation_for_key

YAML_TOKEN_TO_PR_URL = "yaml_token_to_pr_body_url"
YAML_PR_LABEL_SHELL = v4.YAML_METADATA_SHELL

TOKEN_TO_PR_URL_RE = re.compile(
    r"(?:secrets\.github_token|authorization\s*:?\s*bearer|\bauthorization\b).*(?:github\.event\.pull_request\.body|pull_request\.body)"
    r"|(?:github\.event\.pull_request\.body|pull_request\.body).*(?:secrets\.github_token|authorization\s*:?\s*bearer|\bauthorization\b)",
    re.I,
)
PR_LABEL_SHELL_RE = re.compile(
    r"(?:\b(?:bash|sh|pwsh|powershell)\b|-\s*(?:lc|c)\b).*(?:github\.event\.pull_request\.labels|pull_request\.labels)"
    r"|(?:github\.event\.pull_request\.labels|pull_request\.labels).*(?:\b(?:bash|sh|pwsh|powershell)\b|-\s*(?:lc|c)\b)",
    re.I,
)
RUN_LABEL_RE = re.compile(r"\brun\s*:\s*.*(?:github\.event\.pull_request\.labels|pull_request\.labels)", re.I)

REQUIRED_KIND_PRIORITY = {
    YAML_TOKEN_TO_PR_URL: 0,
    v4.YAML_METADATA_SHELL: 1,
    v4.YAML_SHELL_PIPE: 2,
    v4.YAML_PULL_REQUEST_TARGET: 3,
    v4.YAML_UNTRUSTED_CHECKOUT: 4,
    v4.YAML_BROAD_WRITE: 5,
    v9.PYTHON_PICKLE_LOAD: 6,
    v5.PYTHON_YAML_LOAD: 7,
    v5.PYTHON_SHELL_EXEC: 8,
    v5.PYTHON_ENV_TOKEN: 9,
    v9.PS_DYNAMIC_EXEC: 10,
    v4.PS_ACL: 11,
    v5.PS_ENV_TOKEN: 12,
    v4.PS_PROCESS_LAUNCH: 13,
}


def _normalize(value: Any) -> str:
    return v5._normalize(value)


def _original_line_kind(path: str, text: str) -> str:
    original = getattr(core, "_dcoir_required_v10_original_line_kind", None)
    if callable(original):
        return original(path, text)
    return core._line_kind(path, text)


def _workflow_token_to_pr_url(text: str) -> bool:
    normalized = _normalize(text)
    return bool(TOKEN_TO_PR_URL_RE.search(normalized))


def _workflow_pr_label_shell(text: str) -> bool:
    normalized = _normalize(text)
    return bool(RUN_LABEL_RE.search(normalized) or PR_LABEL_SHELL_RE.search(normalized))


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    if suffix in {".yml", ".yaml"}:
        if _workflow_token_to_pr_url(text):
            return YAML_TOKEN_TO_PR_URL
        if _workflow_pr_label_shell(text):
            return v4.YAML_METADATA_SHELL
    return _original_line_kind(path, text)


def _original_claimed_kinds(finding: dict[str, Any]) -> set[str]:
    original = getattr(core, "_dcoir_required_v10_original_claimed_kinds", None)
    if callable(original):
        return set(original(finding))
    return set(core._claimed_kinds(finding))


def _claimed_kinds(finding: dict[str, Any]) -> set[str]:
    kinds = _original_claimed_kinds(finding)
    text = "\n".join(
        str(finding.get(name, "") or "")
        for name in ("title", "body", "description", "_anchored_line_text")
    )
    if _workflow_token_to_pr_url(text):
        kinds.add(YAML_TOKEN_TO_PR_URL)
    if _workflow_pr_label_shell(text):
        kinds.add(v4.YAML_METADATA_SHELL)
    return kinds


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind == v4.YAML_BROAD_WRITE:
        return path, 0, kind
    return path, line, kind


def _required_sort_key(item: Any) -> tuple[int, str, int]:
    path, line, kind = core._sentinel_key(item)
    return REQUIRED_KIND_PRIORITY.get(kind, 50), path, line


def _coalesce_required(required: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    targets: list[Any] = []
    seen: set[SentinelKey] = set()
    duplicates: list[dict[str, Any]] = []
    for sentinel in sorted(required, key=_required_sort_key):
        key = core._sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in seen:
            duplicates.append(
                {
                    "path": key[0],
                    "line": key[1],
                    "kind": key[2],
                    "reason": "duplicate_covered",
                    "label": str(getattr(sentinel, "label", "") or ""),
                    "detail": str(getattr(sentinel, "detail", "") or "")[:240],
                    "text": str(getattr(sentinel, "text", "") or "")[:240],
                }
            )
            continue
        seen.add(coverage)
        targets.append(sentinel)
    return targets, duplicates


def _priority_bucket_for_key(key: SentinelKey, required_coverage: set[SentinelKey]) -> str:
    path, _line, kind = key
    suffix = Path(path.lower()).suffix
    if _coverage_key(key) in required_coverage:
        return "hard-required"
    if kind in {v9.PYTHON_PICKLE_LOAD, v9.PS_DYNAMIC_EXEC, YAML_TOKEN_TO_PR_URL}:
        return "required-adjacent"
    if suffix in {".py", ".ps1", ".psm1", ".psd1", ".yml", ".yaml"}:
        return "high-risk"
    return "optional"


def _sentinel_summary_record(
    sentinel: Any,
    required_coverage: set[SentinelKey],
    selected_coverage: set[SentinelKey],
    limit: int,
) -> dict[str, Any]:
    key = core._sentinel_key(sentinel)
    covered = _coverage_key(key) in selected_coverage
    return {
        "path": key[0],
        "line": key[1],
        "kind": key[2],
        "priority_bucket": _priority_bucket_for_key(key, required_coverage),
        "reason": "duplicate_covered" if covered else "omitted_due_to_inline_budget" if len(selected_coverage) >= limit else "not_selected",
        "label": str(getattr(sentinel, "label", "") or ""),
        "detail": str(getattr(sentinel, "detail", "") or "")[:240],
        "text": str(getattr(sentinel, "text", "") or "")[:240],
    }


def _quote_py(value: str) -> str:
    return repr(str(value))


def _validation_for_token_to_pr_url(path: str) -> str:
    return (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        f"path = Path({_quote_py(path)})\n"
        "text = path.read_text(encoding='utf-8')\n"
        "lower = text.lower()\n"
        "has_token = 'secrets.github_token' in lower or 'authorization' in lower or 'bearer' in lower\n"
        "has_pr_body_url = 'github.event.pull_request.body' in lower or 'pull_request.body' in lower\n"
        "assert not (has_token and has_pr_body_url), 'workflow token can still be sent to a PR-controlled URL'\n"
        "PY"
    )


def _validation_for_pr_metadata_shell(path: str) -> str:
    return (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "import re\n"
        f"path = Path({_quote_py(path)})\n"
        "text = path.read_text(encoding='utf-8')\n"
        "lower = text.lower()\n"
        "label_in_run = re.search(r'\\brun\\s*:\\s*.*github\\.event\\.pull_request\\.labels', lower)\n"
        "label_in_shell = 'github.event.pull_request.labels' in lower and any(token in lower for token in ('bash', ' sh ', 'sh -c', 'pwsh', 'powershell', '-lc', '-c'))\n"
        "title_body_in_shell = any(token in lower for token in ('github.event.pull_request.title', 'github.event.pull_request.body', 'github.head_ref')) and any(shell in lower for shell in ('bash', ' sh ', 'sh -c', 'pwsh', 'powershell', '-lc', '-c'))\n"
        "assert not (label_in_run or label_in_shell or title_body_in_shell), 'pull request metadata can still reach shell execution'\n"
        "PY"
    )


def _original_validation_for_key(kind: str, path: str, line: int = 0) -> str:
    original = getattr(core, "_dcoir_required_v10_original_validation_for_key", None)
    if callable(original):
        return original(kind, path, line)
    return _BASE_VALIDATION_FOR_KEY(kind, path, line)


def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    if kind == YAML_TOKEN_TO_PR_URL:
        return _validation_for_token_to_pr_url(path)
    if kind == v4.YAML_METADATA_SHELL:
        return _validation_for_pr_metadata_shell(path)
    return _original_validation_for_key(kind, path, line)
