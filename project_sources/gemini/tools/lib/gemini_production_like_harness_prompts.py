"""Prompt construction and leak checks for production-like Gemini harness scenarios."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.gemini_production_like_harness_common import (
    BANNED_PROMPT_TERMS,
    add_message,
    repo_relative,
    sha_file,
    sha_text,
)


def build_prompt(
    index: dict[str, Any],
    scenario: dict[str, Any],
    scenario_dir: Path,
    root: Path,
    messages: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]]]:
    template = index.get("prompt_template", {})
    visible = scenario.get("visible", {})
    lines = [
        template.get("header", "Governed DCOIR Gemini blind replay. Return operator-facing text only."),
        template.get("evidence_boundary", "Use only listed evidence; name gaps and the smallest safe next move."),
        "",
        "Operator turn:",
        str(visible.get("turn", "")).strip(),
        "",
        "Evidence attachments:",
    ]
    attachments: list[dict[str, Any]] = []

    for number, text in enumerate(visible.get("evidence_inline", []), 1):
        label = f"inline_evidence_{number}.txt"
        text_value = str(text)
        lines += [
            "",
            f"--- BEGIN ATTACHMENT: {label} ---",
            text_value.rstrip(),
            f"--- END ATTACHMENT: {label} ---",
        ]
        attachments.append(
            {
                "path": label,
                "size_bytes": len(text_value.encode("utf-8")),
                "sha256": sha_text(text_value),
            }
        )

    for item in visible.get("evidence_files", []):
        path = (scenario_dir / item).resolve()
        text = ""
        if not path.is_file():
            add_message(messages, "error", f"{scenario.get('id')} attachment missing", repo_relative(path, root))
        else:
            text = path.read_text(encoding="utf-8-sig")
            attachments.append(
                {
                    "path": repo_relative(path, root),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha_file(path),
                }
            )
        lines += [
            "",
            f"--- BEGIN ATTACHMENT: {item} ---",
            text.rstrip(),
            f"--- END ATTACHMENT: {item} ---",
        ]

    disallowed = list(template.get("no", [])) + list(visible.get("disallowed", []))
    if disallowed:
        lines += ["", "Disallowed behavior:"] + [f"- {item}" for item in disallowed]
    return "\n".join(lines).rstrip() + "\n", attachments


def check_prompt(
    index: dict[str, Any],
    scenario: dict[str, Any],
    scenario_path: Path,
    prompt: str,
    messages: list[dict[str, str]],
    root: Path,
) -> None:
    lowered_prompt = prompt.lower()
    for term in BANNED_PROMPT_TERMS:
        if term in lowered_prompt:
            add_message(
                messages,
                "error",
                f"{scenario.get('id')} prompt leaks grading vocabulary: {term}",
                repo_relative(scenario_path, root),
            )

    hidden = scenario.get("hidden", {})
    for field in ("expected_behavior", "forbidden_behavior"):
        for item in hidden.get(field, []):
            hidden_text = str(item).strip().lower()
            if len(hidden_text) >= 80 and hidden_text in lowered_prompt:
                add_message(
                    messages,
                    "error",
                    f"{scenario.get('id')} prompt leaks long hidden {field} text",
                    repo_relative(scenario_path, root),
                )

    for term in index.get("redaction_prohibited_terms", []):
        if str(term).lower() in lowered_prompt:
            add_message(
                messages,
                "error",
                f"{scenario.get('id')} prompt leaks prohibited redaction term",
                repo_relative(scenario_path, root),
            )
    for pattern in index.get("redaction_prohibited_patterns", []):
        if str(pattern).lower() in lowered_prompt:
            add_message(
                messages,
                "error",
                f"{scenario.get('id')} prompt leaks prohibited redaction pattern",
                repo_relative(scenario_path, root),
            )


def check_signals(
    scenario: dict[str, Any],
    scenario_path: Path,
    prompt: str,
    messages: list[dict[str, str]],
    root: Path,
) -> dict[str, list[str]]:
    expectations = scenario.get("artifact_expectations", {})
    missing = [item for item in expectations.get("must_find", []) if item not in prompt]
    unexpected = [item for item in expectations.get("must_not_find", []) if item in prompt]
    for item in missing:
        add_message(
            messages,
            "error",
            f"{scenario.get('id')} missing expected fixture signal: {item}",
            repo_relative(scenario_path, root),
        )
    for item in unexpected:
        add_message(
            messages,
            "error",
            f"{scenario.get('id')} contains prohibited fixture signal: {item}",
            repo_relative(scenario_path, root),
        )
    return {"missing_required_signals": missing, "unexpected_prohibited_signals": unexpected}
