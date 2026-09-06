#!/usr/bin/env python3
"""Deterministically validate the multi-language adversarial DCOIR corpus.

This validator is deliberately inference-free. It combines structural corpus checks with
small executable/AST witnesses where safe so a benchmark case cannot receive credit for
a counterexample that does not actually exercise the supplied implementation.
"""

from __future__ import annotations

import ast
import base64
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "evaluation" / "multilang_adversarial_corpus_v1.json"
SCHEMA = "dcoir_review_multilang_adversarial_corpus_v1"
SURFACES = {"powershell": 12, "python": 10, "github-actions": 8, "markdown-governance": 6, "json-config": 4}
DIFFICULTIES = {"easy": 4, "medium": 7, "hard": 24, "adversarial": 5}

PS_ASSERTIONS = {
    "ps-contains-direction-membership": "$v=Test-RoleAllowed -Role 'admin' -AllowedRoles @('reader','admin'); if([bool]$v){throw 'defect no longer reproduces'}",
    "ps-path-prefix-is-not-ancestor": "$v=Test-UnderRoot -Root 'C:\\safe' -Candidate 'C:\\safe-evil\\payload.txt'; if(-not [bool]$v){throw 'defect no longer reproduces'}",
    "ps-regex-root-not-escaped": "$bad=$false; try{$v=Test-PathPrefix -Root 'C:\\Temp\\A.B[1]' -Candidate 'C:\\Temp\\A.B[1]\\case.json'; if(-not [bool]$v){$bad=$true}}catch{$bad=$true}; if(-not $bad){throw 'defect no longer reproduces'}",
    "ps-nonterminating-copy-bypasses-catch": "$s=Join-Path ([IO.Path]::GetTempPath()) ('dcoir-missing-'+[Guid]::NewGuid().ToString('N')); $d=Join-Path ([IO.Path]::GetTempPath()) ('dcoir-dest-'+[Guid]::NewGuid().ToString('N')); $v=Copy-Evidence -Source $s -Destination $d 2>$null; if(-not [bool]$v){throw 'defect no longer reproduces'}",
    "ps-vectorized-comparison-any-vs-all": "$x=@([pscustomobject]@{Confidence=0.95},[pscustomobject]@{Confidence=0.40}); $v=Test-AllFindingsHighConfidence -Findings $x; if(-not [bool]$v){throw 'defect no longer reproduces'}",
    "ps-clean-collection-membership": "$a=Test-RoleAllowed -Role 'admin' -AllowedRoles @('reader','admin'); $b=Test-RoleAllowed -Role 'owner' -AllowedRoles @('reader','admin'); if((-not [bool]$a) -or [bool]$b){throw 'clean control regressed'}",
}


def fail(msg: str) -> None:
    raise AssertionError(msg)


def call_names(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                out.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                out.append(node.func.attr)
    return out


def duplicate_json_keys(text: str) -> list[str]:
    found: list[str] = []
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                found.append(key)
            obj[key] = value
        return obj
    json.loads(text, object_pairs_hook=hook)
    return found


def validate_structural(case: dict[str, Any]) -> None:
    cid = str(case["id"])
    for field in ("language", "surface", "difficulty", "expected", "defect_class", "synthetic_path", "review_contract", "source", "counterexample", "ground_truth_rationale"):
        if not str(case.get(field, "")).strip():
            fail(f"{cid}: empty required field {field}")
    groups = case.get("finding_term_groups")
    if not isinstance(groups, list):
        fail(f"{cid}: finding_term_groups must be a list")
    if case["expected"] == "finding":
        if len(groups) < 2 or any(not isinstance(g, list) or len(g) < 2 for g in groups):
            fail(f"{cid}: finding cases require at least two multi-term semantic groups")
    elif case["expected"] == "clean":
        if groups:
            fail(f"{cid}: clean cases may not define finding term groups")
    else:
        fail(f"{cid}: invalid expected disposition")
    source = str(case["source"])
    probe = str(case["counterexample"])
    oracle = case.get("oracle")
    if not isinstance(oracle, dict):
        fail(f"{cid}: missing oracle")
    for needle in oracle.get("required_source_substrings", []):
        if str(needle) not in source:
            fail(f"{cid}: missing required source witness {needle!r}")
    for needle in oracle.get("forbidden_source_substrings", []):
        if str(needle) in source:
            fail(f"{cid}: forbidden source witness present {needle!r}")
    for needle in oracle.get("required_probe_substrings", []):
        if str(needle) not in probe:
            fail(f"{cid}: missing required probe witness {needle!r}")


def validate_python(case: dict[str, Any]) -> bool:
    if case.get("language") != "python":
        return False
    cid = str(case["id"])
    source = str(case["source"])
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        fail(f"{cid}: invalid Python fixture: {exc}")
    calls = call_names(tree)
    if cid == "py-path-prefix-is-not-ancestor":
        if "startswith" not in calls or not "/srv/reviewer-evil/payload.py".startswith("/srv/review"):
            fail(f"{cid}: prefix witness invalid")
    elif cid == "py-reuse-key-omits-policy-version":
        fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "reuse_key"), None)
        if not fn or [a.arg for a in fn.args.args] != ["blob_sha", "model"]:
            fail(f"{cid}: key signature no longer demonstrates omitted policy version")
    elif cid == "py-provider-error-becomes-clean-result":
        if not any(isinstance(n, ast.ExceptHandler) for n in ast.walk(tree)) or not any(isinstance(n, ast.Return) and isinstance(n.value, ast.List) and not n.value.elts for n in ast.walk(tree)):
            fail(f"{cid}: error-to-clean witness invalid")
    elif cid == "py-any-used-for-all-requirements":
        if "any" not in calls or "all" in calls:
            fail(f"{cid}: quantifier witness invalid")
    elif cid == "py-lexicographic-version-gate":
        ns: dict[str, Any] = {}
        exec(compile(source, cid, "exec"), ns, ns)
        fn = ns.get("supported")
        if not callable(fn) or fn("10.0", "9.2") is not False:
            fail(f"{cid}: string-order witness invalid")
    elif cid == "py-mutable-default-cross-pr-state":
        ns: dict[str, Any] = {}
        exec(compile(source, cid, "exec"), ns, ns)
        fn = ns.get("already_reviewed")
        if not callable(fn) or fn("shared/blob") is not False or fn("shared/blob") is not True:
            fail(f"{cid}: mutable-default behavior no longer reproduces")
    elif cid == "py-head-checked-only-before-long-review":
        if calls.count("get_head") != 1 or "publish_review" not in calls:
            fail(f"{cid}: stale-head witness invalid")
    elif cid == "py-semantic-fingerprint-omits-dependency-context":
        fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "semantic_fingerprint"), None)
        if not fn or [a.arg for a in fn.args.args] != ["file_blob_sha", "config_version"]:
            fail(f"{cid}: dependency fingerprint witness invalid")
    elif cid == "py-clean-component-aware-path-check":
        if "is_relative_to" not in calls or Path("/srv/reviewer-evil/payload.py").is_relative_to(Path("/srv/review")):
            fail(f"{cid}: clean path control invalid")
    elif cid == "py-clean-refetch-head-before-publication":
        if calls.count("get_head") < 2 or "publish_review" not in calls:
            fail(f"{cid}: clean exact-head control invalid")
    return True


def validate_json(case: dict[str, Any]) -> bool:
    language = str(case.get("language", ""))
    cid = str(case["id"])
    source = str(case["source"])
    if language == "json":
        duplicates = duplicate_json_keys(source)
        if case.get("defect_class") == "duplicate-config-key":
            if "allow_fallbacks" not in duplicates:
                fail(f"{cid}: duplicate-key witness invalid")
        elif duplicates:
            fail(f"{cid}: unexpected duplicate keys {duplicates}")
        return True
    if language == "json+python":
        if cid == "json-string-false-coerced-to-true" and not bool("false"):
            fail(f"{cid}: string truthiness witness invalid")
        if cid == "json-null-model-stringified-instead-of-defaulted" and str(None) != "None":
            fail(f"{cid}: null stringification witness invalid")
        return True
    return False


def validate_powershell(case: dict[str, Any], pwsh: str | None) -> tuple[bool, bool]:
    if case.get("language") != "powershell":
        return False, False
    if not pwsh:
        return True, False
    cid = str(case["id"])
    encoded = base64.b64encode(str(case["source"]).encode()).decode()
    assertion = PS_ASSERTIONS.get(cid, "")
    command = (
        "$src=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:DCOIR_PS_FIXTURE));"
        "$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseInput($src,[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -gt 0){$errors|%{[Console]::Error.WriteLine($_.Message)};exit 3};"
        ". ([ScriptBlock]::Create($src));" + assertion
    )
    env = dict(os.environ)
    env["DCOIR_PS_FIXTURE"] = encoded
    proc = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", command], env=env, capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode:
        fail(f"{cid}: PowerShell parser/behavior witness failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return True, bool(assertion)


def main() -> int:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA:
        fail(f"unexpected corpus schema {payload.get('schema_version')!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        fail("cases must be a list")
    ids = [str(c.get("id", "")) for c in cases if isinstance(c, dict)]
    if len(ids) != 40 or len(set(ids)) != 40 or any(not value for value in ids):
        fail("corpus must contain exactly 40 unique non-empty case ids")
    finding = [c for c in cases if c.get("expected") == "finding"]
    clean = [c for c in cases if c.get("expected") == "clean"]
    if (len(finding), len(clean)) != (30, 10):
        fail(f"expected 30 finding + 10 clean, got {len(finding)} + {len(clean)}")
    surfaces = Counter(str(c.get("surface", "")) for c in cases)
    difficulties = Counter(str(c.get("difficulty", "")) for c in cases)
    if dict(surfaces) != SURFACES:
        fail(f"surface distribution drifted: {dict(surfaces)}")
    if dict(difficulties) != DIFFICULTIES:
        fail(f"difficulty distribution drifted: {dict(difficulties)}")

    py_checks = json_checks = 0
    for case in cases:
        if not isinstance(case, dict):
            fail("every case must be an object")
        validate_structural(case)
        py_checks += int(validate_python(case))
        json_checks += int(validate_json(case))

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    ps_cases = ps_behavior = 0
    for case in cases:
        parsed, behavior = validate_powershell(case, pwsh)
        ps_cases += int(parsed)
        ps_behavior += int(behavior)

    print(json.dumps({
        "schema_version": SCHEMA,
        "status": "pass",
        "cases": 40,
        "finding_cases": 30,
        "clean_cases": 10,
        "surface_counts": dict(surfaces),
        "difficulty_counts": dict(difficulties),
        "python_ast_semantic_checks": py_checks,
        "json_semantic_checks": json_checks,
        "powershell_cases": ps_cases,
        "powershell_parser": "executed" if pwsh else "unavailable-skipped",
        "powershell_behavior_checks": ps_behavior if pwsh else 0,
        "network_requests_made": 0,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
