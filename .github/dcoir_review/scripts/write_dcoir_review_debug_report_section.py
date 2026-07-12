#!/usr/bin/env python3
"""Write a readable markdown section from DCOIR Review debug artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Any


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def read_json(path: Path) -> dict[str, Any]:
    text = read_text(path)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def cell(value: object) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", "<br>")


def table(rows: list[tuple[object, object]]) -> list[str]:
    lines = ["| Field | Value |", "| --- | --- |"]
    lines.extend(f"| {cell(key)} | {cell(value)} |" for key, value in rows)
    return lines


def details(title: str, text: str, language: str = "text") -> str:
    body = html.escape(text or "(empty)")
    safe_title = html.escape(title)
    safe_language = html.escape(language)
    return (
        "<details>\n"
        f"<summary>{safe_title}</summary>\n\n"
        f"<pre><code class=\"language-{safe_language}\">{body}</code></pre>\n\n"
        "</details>"
    )


def github_run_url(run_id: object) -> str:
    run_id_text = str(run_id or "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/") or "https://github.com"
    if not run_id_text or not repo:
        return ""
    return f"{server}/{repo}/actions/runs/{run_id_text}"


def write_report(debug_dir: Path, output: Path) -> Path:
    context = read_json(debug_dir / "metadata" / "review-context.json")
    initial_request = read_json(debug_dir / "metadata" / "01-initial-request.json")
    retry_request = read_json(debug_dir / "metadata" / "02-quality-retry-request.json")
    initial_result = read_json(debug_dir / "responses" / "01-initial-result.json")
    retry_result = read_json(debug_dir / "responses" / "02-quality-retry-result.json")
    changed_files = context.get("changed_files") if isinstance(context.get("changed_files"), list) else []

    run_id = context.get("workflow_run_id") or os.environ.get("SOURCE_RUN_ID", "")
    run_url = context.get("workflow_run_url") or github_run_url(run_id)
    run_link = f"[{run_id}]({run_url})" if run_id and run_url else run_id

    lines: list[str] = [
        "## DCOIR Review debug context",
        "",
        "> Debug-only source workflow report section for reviewer prompt/context readback.",
        "",
        "### Run",
    ]
    lines.extend(
        table(
            [
                ("workflow", os.environ.get("SOURCE_WORKFLOW_NAME", "DCOIR Review")),
                ("workflow_run_id", run_link),
                ("workflow_run_attempt", os.environ.get("SOURCE_RUN_ATTEMPT", "")),
                ("pull_request", context.get("pr_number") or os.environ.get("PR_NUMBER", "")),
                ("reviewed_head_sha", context.get("reviewed_head_sha", "")),
                ("review_mode", context.get("review_mode", "")),
                ("debug", context.get("debug", "")),
                ("report_created_utc", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
            ]
        )
    )

    lines.extend(["", "---", "", "### Review Context"])
    lines.extend(
        table(
            [
                ("context_summary", context.get("context_summary", "")),
                ("prompt_chars", context.get("prompt_chars") or initial_request.get("prompt_chars", "")),
                ("line_index_entries", initial_request.get("line_index_entries", "")),
                ("deep_context_chars", context.get("deep_context_chars", "")),
                ("review_assist_context_chars", context.get("review_assist_context_chars", "")),
                ("risk_sentinel_count", context.get("risk_sentinel_count", "")),
                ("risk_sentinel_digest", context.get("risk_sentinel_digest", "")),
                ("initial_model_used", initial_result.get("model_used", "")),
                ("retry_model_used", retry_result.get("model_used", "")),
                ("retry_prompt_chars", retry_request.get("prompt_chars", "")),
            ]
        )
    )

    if changed_files:
        lines.extend(
            [
                "",
                "### Changed Files",
                "",
                "| File | Status | Additions | Deletions | Changes |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for item in changed_files:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {filename} | {status} | {additions} | {deletions} | {changes} |".format(
                    filename=cell(item.get("filename", "")),
                    status=cell(item.get("status", "")),
                    additions=cell(item.get("additions", "")),
                    deletions=cell(item.get("deletions", "")),
                    changes=cell(item.get("changes", "")),
                )
            )

    prompt_files = sorted((debug_dir / "prompts").glob("*.txt")) if (debug_dir / "prompts").is_dir() else []
    response_files = sorted((debug_dir / "responses").glob("*.json")) if (debug_dir / "responses").is_dir() else []
    context_files = sorted((debug_dir / "context").glob("*.md")) if (debug_dir / "context").is_dir() else []

    lines.extend(["", "---", "", "### Prompt And Response Readback", ""])
    if not prompt_files and not response_files:
        lines.append("No prompt or response files were captured.")
    for path in prompt_files:
        lines.append(details(f"Prompt: {path.name}", read_text(path), "text"))
        lines.append("")
    for path in response_files:
        lines.append(details(f"Model response: {path.name}", read_text(path), "json"))
        lines.append("")

    lines.extend(["", "---", "", "### Context Payloads", ""])
    if not context_files:
        lines.append("No context markdown files were captured.")
    for path in context_files:
        lines.append(details(f"Context: {path.name}", read_text(path), "markdown"))
        lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-dir", default=os.environ.get("DCOIR_REVIEW_DEBUG_ARTIFACT_DIR", "dcoir-review-debug"))
    parser.add_argument(
        "--output",
        default="chatgpt-workflow-report-section/chatgpt_workflow_report_section.md",
    )
    args = parser.parse_args()

    debug_dir = Path(args.debug_dir)
    if not debug_dir.is_dir():
        raise SystemExit(f"DCOIR Review debug directory not found: {debug_dir}")
    print(write_report(debug_dir, Path(args.output)))


if __name__ == "__main__":
    main()
