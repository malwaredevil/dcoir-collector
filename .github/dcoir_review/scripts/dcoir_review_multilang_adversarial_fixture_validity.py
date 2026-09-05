#!/usr/bin/env python3
"""Deterministic structural/oracle validation for the multi-language adversarial corpus."""

from __future__ import annotations

import ast
import base64
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


DCOIR_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = DCOIR_ROOT / "evaluation" / "multilang_adversarial_corpus_v1.json"
EXPECTED_SCHEMA = "dcoir_review_multilang_adversarial_corpus_v1"
EXPECTED_SURFACES = {
    "powershell": 12,
    "python": 10,
    "github-actions": 8,
    "markdown-governance": 6,
    "json-config": 4,
}
EXPECTED_DIFFICULTIES = {"easy": 4, "medium": 7, "hard": 24, "adversarial": 5}


def fail(message: str) -> None:
    raise AssertionError(message)


def duplicate_json_keys(text: str) -> list[str]:
    duplicates: list[str] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                duplicates.append(key)
            result[key] = value
        return result

    json.loads(text, object_pairs_hook=hook)
    return duplicates


def validate_oracle(case: dict[str, Any]) -> None:
    case_id = str(case["id"])
    source = str(case.get("source", ""))
    probe = str(case.get("counterexample", ""))
    oracle = case.get("oracle")
    if not isinstance(oracle, dict):
        fail(f"{case_id}: missing oracle object")
    for needle in oracle.get("required_source_substrings", []):
        if str(needle) not in source:
            fail(f"{case_id}: required source witness missing: {needle!r}")
    for needle in oracle.get("forbidden_source_substrings", []):
        if str(needle) in source:
            fail(f"{case_id}: forbidden source witness present: {needle!r}")
    for needle in oracle.get("required_probe_substrings", []):
        if str(needle) not in probe:
            fail(f"{case_id}: required probe witness missing: {needle!r}")


def validate_python(case: dict[str, Any]) -> None:
    if case.get("language") != "python":
        return
    try:
        ast.parse(str(case["source"]))
    except SyntaxError as exc:
        fail(f"{case['id']}: Python fixture is not syntactically valid: {exc}")


def validate_json(case: dict[str, Any]) -> None:
    if case.get("language") != "json":
        return
    duplicates = duplicate_json_keys(str(case["source"]))
    if case.get("defect_class") == "duplicate-config-key":
        if "allow_fallbacks" not in duplicates:
            fail(f"{case['id']}: duplicate-key fixture no longer contains duplicate allow_fallbacks")
    elif duplicates:
        fail(f"{case['id']}: clean/non-duplicate JSON fixture unexpectedly has duplicate keys: {duplicates}")


def validate_powershell(case: dict[str, Any], pwsh: str | None) -> None:
    if case.get("language") != "powershell" or not pwsh:
        return
    encoded = base64.b64encode(str(case["source"]).encode("utf-8")).decode("ascii")
    command = (
        "$src=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:DCOIR_PS_FIXTURE));"
        "$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseInput($src,[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -gt 0){$errors|ForEach-Object{[Console]::Error.WriteLine($_.Message)};exit 3}"
    )
    env = dict(__import__("os").environ)
    env["DCOIR_PS_FIXTURE"] = encoded
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        fail(f"{case['id']}: PowerShell parser rejected fixture: {result.stderr.strip() or result.stdout.strip()}")


def main() -> int:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        fail(f"Unexpected schema: {payload.get('schema_version')!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        fail("cases must be a list")
    ids = [str(case.get("id", "")) for case in cases if isinstance(case, dict)]
    if len(ids) != 40 or len(set(ids)) != 40 or any(not case_id for case_id in ids):
        fail(f"Expected 40 unique non-empty ids, got {len(ids)} ids / {len(set(ids))} unique")
    findings = [case for case in cases if case.get("expected") == "finding"]
    cleans = [case for case in cases if case.get("expected") == "clean"]
    if (len(findings), len(cleans)) != (30, 10):
        fail(f"Expected 30 finding + 10 clean cases, got {len(findings)} + {len(cleans)}")
    surface_counts = Counter(str(case.get("surface", "")) for case in cases)
    if dict(surface_counts) != EXPECTED_SURFACES:
        fail(f"Unexpected surface distribution: {dict(surface_counts)}")
    difficulty_counts = Counter(str(case.get("difficulty", "")) for case in cases)
    if dict(difficulty_counts) != EXPECTED_DIFFICULTIES:
        fail(f"Unexpected difficulty distribution: {dict(difficulty_counts)}")
    if difficulty_counts["hard"] + difficulty_counts["adversarial"] < 29:
        fail("Hard/adversarial cases must remain the majority of the corpus")
    for case in cases:
        if not isinstance(case, dict):
            fail("Every case must be an object")
        case_id = str(case["id"])
        for field in ("language", "surface", "difficulty", "expected", "defect_class", "synthetic_path", "review_contract", "source", "counterexample", "ground_truth_rationale"):
            if not str(case.get(field, "")).strip():
                fail(f"{case_id}: required field {field!r} is empty")
        groups = case.get("finding_term_groups")
        if not isinstance(groups, list):
            fail(f"{case_id}: finding_term_groups must be a list")
        if case["expected"] == "finding":
            if len(groups) < 2:
                fail(f"{case_id}: finding fixture must require at least two semantic term groups")
            for group in groups:
                if not isinstance(group, list) or len(group) < 2 or any(not str(term).strip() for term in group):
                    fail(f"{case_id}: each semantic term group must contain at least two non-empty terms")
        elif groups:
            fail(f"{case_id}: clean fixture must not contain finding term groups")
        validate_oracle(case)
        validate_python(case)
        validate_json(case)
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    for case in cases:
        validate_powershell(case, pwsh)
    result = {
        "schema_version": EXPECTED_SCHEMA,
        "cases": len(cases),
        "finding_cases": len(findings),
        "clean_cases": len(cleans),
        "surface_counts": dict(surface_counts),
        "difficulty_counts": dict(difficulty_counts),
        "powershell_parser": "executed" if pwsh else "unavailable-skipped",
        "status": "pass",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
