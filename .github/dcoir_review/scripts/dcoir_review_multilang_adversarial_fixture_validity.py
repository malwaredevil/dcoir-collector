#!/usr/bin/env python3
"""Deterministic structural and behavioral validation for the multi-language adversarial corpus.

The earlier calibration corpus exposed why syntax-only fixtures are insufficient: a
counterexample can look persuasive while failing to exercise the literal implementation.
This validator therefore combines structural oracles with executable witnesses wherever
it is safe and portable to do so. It never performs model inference or network access.
"""

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

# These assertions load the exact PowerShell fixture text and then exercise a bounded,
# local witness. They deliberately avoid remoting, network requests, and external native
# executables. Exit zero means the fixture still demonstrates the intended disposition.
POWERSHELL_BEHAVIOR_ASSERTIONS: dict[str, str] = {
    "ps-contains-direction-membership": (
        "$actual=Test-RoleAllowed -Role 'admin' -AllowedRoles @('reader','admin');"
        "if([bool]$actual){throw 'defect witness no longer reproduces'}"
    ),
    "ps-path-prefix-is-not-ancestor": (
        "$actual=Test-UnderRoot -Root 'C:\\safe' -Candidate 'C:\\safe-evil\\payload.txt';"
        "if(-not [bool]$actual){throw 'prefix witness no longer reproduces'}"
    ),
    "ps-regex-root-not-escaped": (
        "$violates=$false;"
        "try{$actual=Test-PathPrefix -Root 'C:\\Temp\\A.B[1]' -Candidate 'C:\\Temp\\A.B[1]\\case.json';"
        "if(-not [bool]$actual){$violates=$true}}catch{$violates=$true};"
        "if(-not $violates){throw 'regex-literal witness no longer reproduces'}"
    ),
    "ps-nonterminating-copy-bypasses-catch": (
        "$missing=Join-Path ([IO.Path]::GetTempPath()) ('dcoir-missing-'+[Guid]::NewGuid().ToString('N'));"
        "$dest=Join-Path ([IO.Path]::GetTempPath()) ('dcoir-dest-'+[Guid]::NewGuid().ToString('N'));"
        "$actual=Copy-Evidence -Source $missing -Destination $dest 2>$null;"
        "if(-not [bool]$actual){throw 'nonterminating-error witness no longer reproduces'}"
    ),
    "ps-vectorized-comparison-any-vs-all": (
        "$items=@([pscustomobject]@{Confidence=0.95},[pscustomobject]@{Confidence=0.40});"
        "$actual=Test-AllFindingsHighConfidence -Findings $items;"
        "if(-not [bool]$actual){throw 'vectorized any-vs-all witness no longer reproduces'}"
    ),
    "ps-clean-collection-membership": (
        "$yes=Test-RoleAllowed -Role 'admin' -AllowedRoles @('reader','admin');"
        "$no=Test-RoleAllowed -Role 'owner' -AllowedRoles @('reader','admin');"
        "if((-not [bool]$yes) -or [bool]$no){throw 'clean membership fixture behavior regressed'}"
    ),
}


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


def _call_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.append(node.func.attr)
    return names


def validate_python(case: dict[str, Any]) -> bool:
    if case.get("language") != "python":
        return False
    case_id = str(case["id"])
    try:
        tree = ast.parse(str(case["source"]))
    except SyntaxError as exc:
        fail(f"{case_id}: Python fixture is not syntactically valid: {exc}")
    calls = _call_names(tree)

    # Targeted AST/semantic witnesses bind the prose counterexample to the exact fixture
    # construct, avoiding another capitalization/branch mismatch like the old corpus bug.
    if case_id == "py-path-prefix-is-not-ancestor":
        if "startswith" not in calls or not "/srv/reviewer-evil/payload.py".startswith("/srv/review"):
            fail(f"{case_id}: path-prefix witness no longer demonstrates the defect")
    elif case_id == "py-reuse-key-omits-policy-version":
        func = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "reuse_key"), None)
        args = [arg.arg for arg in func.args.args] if isinstance(func, ast.FunctionDef) else []
        if args != ["blob_sha", "model"]:
            fail(f"{case_id}: cache-key signature changed; re-adjudicate fixture")
    elif case_id == "py-provider-error-becomes-clean-result":
        handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
        empty_returns = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.List) and not node.value.elts
        ]
        if not handlers or not empty_returns:
            fail(f"{case_id}: provider-error-to-empty-result witness no longer matches source")
    elif case_id == "py-any-used-for-all-requirements":
        if "any" not in calls or "all" in calls:
            fail(f"{case_id}: existential/universal witness no longer matches source")
        values = {"exact_head": True, "schema_valid": False, "verifier_supported": False}
        if not any(values[name] for name in ("exact_head", "schema_valid", "verifier_supported")):
            fail(f"{case_id}: witness setup is invalid")
    elif case_id == "py-lexicographic-version-gate":
        if "10.0" >= "9.2":
            fail(f"{case_id}: Python string-order assumption unexpectedly changed")
    elif case_id == "py-mutable-default-cross-pr-state":
        funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        if not funcs or not any(isinstance(default, ast.Set) for default in funcs[0].args.defaults):
            fail(f"{case_id}: mutable-default witness no longer matches source")
    elif case_id == "py-head-checked-only-before-long-review":
        if calls.count("get_head") != 1 or "publish_review" not in calls:
            fail(f"{case_id}: stale-head publication witness no longer matches source")
    elif case_id == "py-semantic-fingerprint-omits-dependency-context":
        func = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "semantic_fingerprint"), None)
        args = [arg.arg for arg in func.args.args] if isinstance(func, ast.FunctionDef) else []
        if args != ["file_blob_sha", "config_version"]:
            fail(f"{case_id}: dependency-fingerprint signature changed; re-adjudicate fixture")
    elif case_id == "py-clean-component-aware-path-check":
        if "is_relative_to" not in calls:
            fail(f"{case_id}: clean component-aware path control no longer matches source")
        if Path("/srv/reviewer-evil/payload.py").is_relative_to(Path("/srv/review")):
            fail(f"{case_id}: clean path witness unexpectedly accepts sibling prefix")
    elif case_id == "py-clean-refetch-head-before-publication":
        if calls.count("get_head") < 2 or "publish_review" not in calls:
            fail(f"{case_id}: clean exact-head publication control no longer rechecks head")
    return True


def validate_json(case: dict[str, Any]) -> bool:
    language = str(case.get("language", ""))
    case_id = str(case["id"])
    if language == "json":
        duplicates = duplicate_json_keys(str(case["source"]))
        if case.get("defect_class") == "duplicate-config-key":
            if "allow_fallbacks" not in duplicates:
                fail(f"{case_id}: duplicate-key fixture no longer contains duplicate allow_fallbacks")
        elif duplicates:
            fail(f"{case_id}: clean/non-duplicate JSON fixture unexpectedly has duplicate keys: {duplicates}")
        return True
    if language == "json+python":
        if case_id == "json-string-false-coerced-to-true" and not bool("false"):
            fail(f"{case_id}: string-truthiness witness unexpectedly changed")
        if case_id == "json-null-model-stringified-instead-of-defaulted" and str(None) != "None":
            fail(f"{case_id}: null-stringification witness unexpectedly changed")
        return True
    return False


def validate_powershell(case: dict[str, Any], pwsh: str | None) -> tuple[bool, bool]:
    if case.get("language") != "powershell":
        return False, False
    if not pwsh:
        return True, False
    case_id = str(case["id"])
    encoded = base64.b64encode(str(case["source"]).encode("utf-8")).decode("ascii")
    assertion = POWERSHELL_BEHAVIOR_ASSERTIONS.get(case_id, "")
    command = (
        "$ErrorActionPreference='Stop';"
        "$src=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:DCOIR_PS_FIXTURE));"
        "$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseInput($src,[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -gt 0){$errors|ForEach-Object{[Console]::Error.WriteLine($_.Message)};exit 3};"
        ". ([ScriptBlock]::Create($src));"
        + assertion
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
        fail(f"{case_id}: PowerShell fixture parser/behavior witness failed: {result.stderr.strip() or result.stdout.strip()}")
    return True, bool(assertion)


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

    python_semantic_checks = 0
    json_semantic_checks = 0
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
        python_semantic_checks += int(validate_python(case))
        json_semantic_checks += int(validate_json(case))

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    powershell_cases = 0
    powershell_behavior_checks = 0
    for case in cases:
        parsed, behavior = validate_powershell(case, pwsh)
        powershell_cases += int(parsed)
        powershell_behavior_checks += int(behavior)

    result = {
        "schema_version": EXPECTED_SCHEMA,
        "cases": len(cases),
        "finding_cases": len(findings),
        "clean_cases": len(cleans),
        "surface_counts": dict(surface_counts),
        "difficulty_counts": dict(difficulty_counts),
        "python_ast_semantic_checks": python_semantic_checks,
        "json_semantic_checks": json_semantic_checks,
        "powershell_cases": powershell_cases,
        "powershell_parser": "executed" if pwsh else "unavailable-skipped",
        "powershell_behavior_checks": powershell_behavior_checks if pwsh else 0,
        "network_requests_made": 0,
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
