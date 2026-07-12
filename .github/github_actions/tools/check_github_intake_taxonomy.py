#!/usr/bin/env python3
"""Validate GitHub issue/PR intake surfaces against the approved taxonomy."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_taxonomy(root: Path) -> dict[str, Any]:
    path = root / "project_sources" / "github_actions" / "github_intake_taxonomy.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], path: Path, message: str) -> None:
    errors.append(f"{path.as_posix()}: {message}")


def extract_top_level_labels(text: str) -> list[str]:
    lines = text.splitlines()
    labels: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("labels:"):
            continue
        base_indent = len(line) - len(line.lstrip())
        remainder = stripped.split(":", 1)[1].strip()
        if remainder:
            return [
                value.strip().strip("'\"")
                for value in remainder.strip("[]").split(",")
                if value.strip()
            ]
        for follow in lines[index + 1 :]:
            follow_indent = len(follow) - len(follow.lstrip())
            if follow.strip().startswith("- ") and follow_indent > base_indent:
                labels.append(follow.strip().split("- ", 1)[1].strip().strip("'\""))
                continue
            if follow.strip() == "":
                continue
            if follow_indent <= base_indent:
                break
        if labels:
            return labels
    return labels


def extract_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    if not match:
        return None
    return match.group(1).strip().strip("'\"")


def quoted_label_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"['\"]([^'\"]+)['\"]", text))
    tokens.update(re.findall(r"`([^`]+)`", text))
    tokens.update(re.findall(r"(?m)^\s*-\s+([A-Za-z0-9:_-]+)\s*$", text))
    return tokens


def line_label_tokens(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for line in text.splitlines():
        line_tokens = set(re.findall(r"['\"]([^'\"]+)['\"]", line))
        line_tokens.update(re.findall(r"`([^`]+)`", line))
        list_match = re.match(r"\s*-\s+([A-Za-z0-9:_-]+)\s*$", line)
        if list_match:
            line_tokens.add(list_match.group(1))
        tokens.extend((token, line) for token in line_tokens)
    return tokens


def is_allowed_wildcard_example(token: str, line: str) -> bool:
    if token not in {"area:*", "type:*"}:
        return False
    return (
        "approved `area:*` label and one approved `type:*` label" in line
        or "approved `area:*` and `type:*` taxonomy" in line
        or "Exactly one `area:*` label and exactly one `type:*` label" in line
    )


def markdown_headings(text: str) -> set[str]:
    return set(re.findall(r"(?m)^##\s+(.+?)\s*$", text))


def validate_config(root: Path, errors: list[str]) -> None:
    path = root / ".github" / "ISSUE_TEMPLATE" / "config.yml"
    rel = path.relative_to(root)
    if not path.exists():
        fail(errors, rel, "issue-template config.yml is required")
        return
    text = path.read_text(encoding="utf-8")
    if not re.search(r"(?m)^blank_issues_enabled:\s*false\s*$", text):
        fail(errors, rel, "blank_issues_enabled must be false")


def validate_issue_forms(root: Path, taxonomy: dict[str, Any], errors: list[str]) -> None:
    template_dir = root / ".github" / "ISSUE_TEMPLATE"
    approved_labels = set(taxonomy["approved_labels"])
    expected_forms = {entry["file"]: entry for entry in taxonomy["issue_forms"]}

    for path in sorted(template_dir.glob("*.md")):
        fail(errors, path.relative_to(root), "Markdown issue templates are retired; use YAML issue forms")

    actual_forms = {
        path.name: path
        for path in sorted(template_dir.glob("*.yml")) + sorted(template_dir.glob("*.yaml"))
        if path.name != "config.yml"
    }

    missing = sorted(set(expected_forms) - set(actual_forms))
    extra = sorted(set(actual_forms) - set(expected_forms))
    for name in missing:
        fail(errors, template_dir / name, "expected issue form is missing")
    for name in extra:
        fail(errors, actual_forms[name].relative_to(root), "issue form is not declared in taxonomy manifest")

    for name, path in actual_forms.items():
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        labels = extract_top_level_labels(text)
        if not labels:
            fail(errors, rel, "issue form must declare labels")
            continue
        unknown = [label for label in labels if label not in approved_labels]
        if unknown:
            fail(errors, rel, f"unknown labels: {', '.join(unknown)}")
        area = [label for label in labels if label.startswith("area:")]
        kind = [label for label in labels if label.startswith("type:")]
        if len(area) != 1:
            fail(errors, rel, f"expected exactly one area label, got {len(area)}")
        if len(kind) != 1:
            fail(errors, rel, f"expected exactly one type label, got {len(kind)}")

        expected = expected_forms.get(name)
        if expected:
            if labels != expected["labels"]:
                fail(errors, rel, f"labels must match taxonomy manifest: {expected['labels']}; got {labels}")
            form_name = extract_scalar(text, "name")
            if form_name != expected["name"]:
                fail(errors, rel, f"name must match taxonomy manifest: {expected['name']}; got {form_name}")


def validate_label_references(root: Path, taxonomy: dict[str, Any], errors: list[str]) -> None:
    approved_labels = set(taxonomy["approved_labels"])
    retired_labels = set(taxonomy["retired_labels"])
    paths = [
        root / ".github" / "README.md",
        root / ".github" / "PULL_REQUEST_TEMPLATE.md",
        root / ".github" / "dependabot.yml",
    ]
    paths.extend((root / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
    paths.extend((root / ".github" / "ISSUE_TEMPLATE").glob("*.yaml"))

    for path in paths:
        if not path.exists():
            continue
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        tokens = [
            token
            for token, line in line_label_tokens(text)
            if not is_allowed_wildcard_example(token, line)
        ]
        retired = sorted(token for token in tokens if token in retired_labels)
        if retired:
            fail(errors, rel, f"retired label references: {', '.join(retired)}")
        label_like = sorted(
            token
            for token in tokens
            if token.startswith(("area:", "type:")) and token not in approved_labels
        )
        if label_like:
            fail(errors, rel, f"unapproved taxonomy labels: {', '.join(label_like)}")


def validate_dependabot(root: Path, errors: list[str]) -> None:
    path = root / ".github" / "dependabot.yml"
    if not path.exists():
        return
    labels = extract_top_level_labels(path.read_text(encoding="utf-8"))
    expected = {"area:github-repo", "type:maintenance"}
    if set(labels) != expected:
        fail(
            errors,
            path.relative_to(root),
            f"dependabot labels must be exactly {sorted(expected)}; got {labels}",
        )


def validate_pr_template(root: Path, taxonomy: dict[str, Any], errors: list[str]) -> None:
    path = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    rel = path.relative_to(root)
    text = path.read_text(encoding="utf-8")
    headings = markdown_headings(text)
    for section in taxonomy["required_pr_template_sections"]:
        if section not in headings:
            fail(errors, rel, f"missing required PR template section: {section}")
    for phrase in taxonomy["required_pr_template_phrases"]:
        if phrase not in text:
            fail(errors, rel, f"missing required PR template phrase: {phrase}")


def validate_guidance(root: Path, taxonomy: dict[str, Any], errors: list[str]) -> None:
    readme = root / ".github" / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    for phrase in taxonomy["required_github_readme_phrases"]:
        if phrase not in readme_text:
            fail(errors, readme.relative_to(root), f"missing required API-created issue guidance: {phrase}")

    guidance_paths = [
        root / ".github" / "README.md",
        root / ".github" / "SECURITY.md",
        root / ".github" / "PULL_REQUEST_TEMPLATE.md",
    ]
    guidance_paths.extend((root / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
    guidance_paths.extend((root / ".github" / "ISSUE_TEMPLATE").glob("*.yaml"))
    for path in guidance_paths:
        text = path.read_text(encoding="utf-8")
        stale = sorted(term for term in taxonomy["stale_guidance_terms"] if term in text)
        if stale:
            fail(errors, path.relative_to(root), f"stale guidance terms: {', '.join(stale)}")


def main() -> int:
    root = repo_root()
    taxonomy = load_taxonomy(root)
    errors: list[str] = []
    validate_config(root, errors)
    validate_issue_forms(root, taxonomy, errors)
    validate_label_references(root, taxonomy, errors)
    validate_dependabot(root, errors)
    validate_pr_template(root, taxonomy, errors)
    validate_guidance(root, taxonomy, errors)
    if errors:
        print("GitHub intake taxonomy validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("GitHub intake taxonomy validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
