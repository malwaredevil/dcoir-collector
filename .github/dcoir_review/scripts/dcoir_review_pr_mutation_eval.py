#!/usr/bin/env python3
"""Production-shaped, no-publication PR mutation evaluator for DCOIR first-pass candidates.

Unlike the isolated semantic corpus, this lane gives the model a PR-shaped prompt with
PR title/body, changed-file summary, repository guidance, and unified patches. Hidden
benchmark labels, expected findings, anchors, difficulty, and ground truth never enter
the model-visible prompt. Default execution is plan-only and makes zero network calls.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

import dcoir_review_first_pass_candidate_eval as base
import dcoir_review_multilang_adversarial_eval as adv

DCOIR_ROOT = Path(__file__).resolve().parents[1]
SHARD_GLOB = "pr_mutation_cases_*_v1.json"
SHARD_SCHEMA = "dcoir_review_pr_mutation_cases_v1"
REPORT_SCHEMA = "dcoir_review_pr_mutation_eval_report_v1"
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
VALIDATION_COMMANDS = [
    "bash .github/dcoir_review/scripts/validate-codex-local.sh",
    "pwsh -NoProfile -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1 -AllowPowerShell7 -AllowEmpty",
    "python3 .github/dcoir_review/scripts/validate-codeql-security-workflow.py",
]


def added_lines(patch: str) -> list[tuple[int, str]]:
    output: list[tuple[int, str]] = []
    right: int | None = None
    for line in patch.splitlines():
        match = HUNK_RE.match(line)
        if match:
            right = int(match.group(1))
            continue
        if right is None or line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            output.append((right, line[1:]))
            right += 1
        elif line.startswith("-"):
            continue
        else:
            right += 1
    return output


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    ids: set[str] = set()
    shards = sorted((DCOIR_ROOT / "evaluation").glob(SHARD_GLOB))
    if not shards:
        raise ValueError("No PR mutation corpus shards found")
    for path in shards:
        data = base.load_json(path)
        if data.get("schema_version") != SHARD_SCHEMA:
            raise ValueError(f"Unexpected PR mutation shard schema in {path.name}")
        raw_cases = data.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError(f"PR mutation shard {path.name} has no cases")
        for raw in raw_cases:
            if not isinstance(raw, dict):
                raise ValueError(f"Non-object PR mutation case in {path.name}")
            case = dict(raw)
            case_id = str(case.get("id", "")).strip()
            if not case_id or case_id in ids:
                raise ValueError(f"Missing or duplicate PR mutation id: {case_id!r}")
            ids.add(case_id)
            files = case.get("files")
            if not isinstance(files, list) or not files:
                raise ValueError(f"{case_id}: files must be a non-empty list")
            expected = case.get("expected_findings")
            if not isinstance(expected, list):
                raise ValueError(f"{case_id}: expected_findings must be a list")
            file_map = {str(item.get("filename", "")): item for item in files if isinstance(item, dict)}
            if len(file_map) != len(files) or any(not key for key in file_map):
                raise ValueError(f"{case_id}: changed file names must be present and unique")
            for finding in expected:
                if not isinstance(finding, dict):
                    raise ValueError(f"{case_id}: expected finding must be an object")
                target = str(finding.get("path", ""))
                if target not in file_map:
                    raise ValueError(f"{case_id}: expected finding path {target!r} is not changed")
                groups = finding.get("term_groups")
                if not isinstance(groups, list) or len(groups) < 2 or any(not isinstance(group, list) or not group for group in groups):
                    raise ValueError(f"{case_id}: expected finding term groups must contain at least two non-empty groups")
                anchors = finding.get("anchor_substrings")
                if not isinstance(anchors, list) or not anchors:
                    raise ValueError(f"{case_id}: expected finding requires anchor_substrings")
                added = added_lines(str(file_map[target].get("patch", "")))
                if not any(any(str(anchor) in text for _, text in added) for anchor in anchors):
                    raise ValueError(f"{case_id}: no hidden anchor occurs on an added line for {target}")
            cases.append(case)
    if len(cases) != 12:
        raise ValueError(f"Expected 12 PR mutation cases, found {len(cases)}")
    if sum(1 for case in cases if not case["expected_findings"]) != 4:
        raise ValueError("Expected exactly 4 clean PR mutation controls")
    if sum(len(case["expected_findings"]) for case in cases) != 10:
        raise ValueError("Expected exactly 10 seeded findings across the PR mutation corpus")
    return cases


def guidance_text() -> str:
    chunks: list[str] = []
    repo_root = DCOIR_ROOT.parent.parent
    for name in ("AGENTS.md", "README.md"):
        path = repo_root / name
        if path.exists():
            chunks.append(f"# {name}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def file_stats(patch: str) -> tuple[int, int]:
    additions = deletions = 0
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


def build_pr_prompt(case: dict[str, Any]) -> str:
    changed_files: list[dict[str, Any]] = []
    patches: list[str] = []
    for item in case["files"]:
        patch = str(item.get("patch", ""))
        additions, deletions = file_stats(patch)
        changed_files.append({
            "filename": str(item["filename"]),
            "status": str(item.get("status", "modified")),
            "additions": additions,
            "deletions": deletions,
            "changes": additions + deletions,
            "patch": patch,
        })
        patches.append(patch)
    unified = "\n".join(patches)
    return f"""Repository: DCOIR-Collector/dcoir-collector
PR number: 9000
PR title: {case['pr_title']}
PR body:
{case['pr_body']}

Trusted repository guidance:
{guidance_text()}

Preferred validation commands:
{json.dumps(VALIDATION_COMMANDS, indent=2)}

Changed file summary:
{json.dumps(changed_files, indent=2)}

Unified diff:
{unified}

Review task:
Find only high-signal issues in the PR diff. For each finding, give the exact changed file path and right-side line number. Provide a suggested_replacement only when a small GitHub suggestion block would be safe and likely to apply cleanly. Include validation commands that should pass after the fix.""".strip()


def build_payload(candidate: dict[str, Any], case: dict[str, Any], system_prompt: str, review_schema: dict[str, Any], request_contract: dict[str, Any], max_tokens: int | None) -> dict[str, Any]:
    payload = adv.build_payload(candidate, {"id": "prompt-shell", "source": "", "counterexample": "", "review_contract": ""}, system_prompt, review_schema, request_contract, max_tokens_override=max_tokens)
    payload["messages"][1]["content"] = build_pr_prompt(case)
    return payload


def finding_text(finding: dict[str, Any]) -> str:
    return " ".join(str(finding.get(key, "")) for key in ("title", "body", "validation")).lower()


def allowed_changed_lines(case: dict[str, Any], path: str) -> set[int]:
    for item in case["files"]:
        if str(item["filename"]) == path:
            return {line for line, _ in added_lines(str(item.get("patch", "")))}
    return set()


def finding_matches(case: dict[str, Any], expected: dict[str, Any], finding: dict[str, Any]) -> bool:
    if str(finding.get("path", "")) != str(expected["path"]):
        return False
    try:
        line = int(finding.get("line", 0))
    except (TypeError, ValueError):
        return False
    if line not in allowed_changed_lines(case, str(expected["path"])):
        return False
    text = finding_text(finding)
    for group in expected["term_groups"]:
        terms = [str(term).lower() for term in group if str(term).strip()]
        if not any(term in text for term in terms):
            return False
    return True


def score_case(case: dict[str, Any], request_result: dict[str, Any]) -> dict[str, Any]:
    expected = list(case["expected_findings"])
    if not request_result.get("ok"):
        return {"correct": False, "disposition": "request-error", "expected_findings": len(expected), "detected_findings": 0, "extra_findings": 0}
    result = request_result.get("result") if isinstance(request_result.get("result"), dict) else {}
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    unmatched = set(range(len(findings)))
    matched_expected: list[dict[str, Any]] = []
    missed_expected: list[dict[str, Any]] = []
    for target in expected:
        match_index = next((idx for idx in sorted(unmatched) if isinstance(findings[idx], dict) and finding_matches(case, target, findings[idx])), None)
        if match_index is None:
            missed_expected.append({"path": target["path"], "defect_class": target.get("defect_class", "")})
        else:
            unmatched.remove(match_index)
            matched_expected.append({"path": target["path"], "defect_class": target.get("defect_class", "")})
    extras = [findings[idx] for idx in sorted(unmatched)]
    correct = not missed_expected and not extras
    if correct:
        disposition = "clean" if not expected else "all-findings-detected"
    elif missed_expected and extras:
        disposition = "misses-and-extra-findings"
    elif missed_expected:
        disposition = "false-negative"
    else:
        disposition = "false-positive-or-extra"
    return {
        "correct": correct,
        "disposition": disposition,
        "expected_findings": len(expected),
        "detected_findings": len(matched_expected),
        "extra_findings": len(extras),
        "matched_expected": matched_expected,
        "missed_expected": missed_expected,
    }


def aggregate(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    usage = {key: 0 for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_prompt_tokens", "cache_write_tokens", "total_tokens")}
    cost = seconds = 0.0
    providers: dict[str, int] = {}
    for row in rows:
        request = row.get("request") if isinstance(row.get("request"), dict) else {}
        seconds += float(request.get("latency_seconds", 0.0) or 0.0)
        u = request.get("usage") if isinstance(request.get("usage"), dict) else {}
        for key in usage:
            usage[key] += int(u.get(key, 0) or 0)
        cost += float(u.get("cost_usd", 0.0) or 0.0)
        provider = str(request.get("selected_provider", "") or "")
        if provider:
            providers[provider] = providers.get(provider, 0) + 1
    return {
        "candidate_id": str(candidate["id"]),
        "model": str(candidate["model"]),
        "reasoning_effort": str(candidate.get("reasoning_effort", "") or ""),
        "pr_cases": len(rows),
        "correct_pr_cases": sum(1 for row in rows if row["score"]["correct"]),
        "seeded_findings_total": sum(int(row["score"]["expected_findings"]) for row in rows),
        "seeded_findings_detected": sum(int(row["score"]["detected_findings"]) for row in rows),
        "extra_findings": sum(int(row["score"]["extra_findings"]) for row in rows),
        "clean_prs_total": sum(1 for row in rows if row["expected_findings"] == 0),
        "clean_prs_correct": sum(1 for row in rows if row["expected_findings"] == 0 and row["score"]["correct"]),
        "request_errors": sum(1 for row in rows if row["score"]["disposition"] == "request-error"),
        "usage": usage,
        "exact_cost_usd": cost,
        "serial_request_seconds": seconds,
        "providers": providers,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", default="sonnet5-high")
    p.add_argument("--case", action="append", default=[])
    p.add_argument("--max-tokens", type=int, default=32768)
    p.add_argument("--execute-live", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=300)
    p.add_argument("--output", default="")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    matrix = base.load_matrix()
    candidates = base.selected_candidates(matrix, args.candidate)
    cases = load_cases()
    if args.case:
        wanted = set(args.case)
        cases = [case for case in cases if case["id"] in wanted]
        missing = sorted(wanted - {case["id"] for case in cases})
        if missing:
            raise SystemExit(f"Unknown PR mutation cases: {missing}")
    system_prompt = base.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    review_schema = base.load_json(base.REVIEW_SCHEMA_PATH)
    contract = matrix.get("request_contract") if isinstance(matrix.get("request_contract"), dict) else {}
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "mode": "live" if args.execute_live else "plan",
        "selected_candidate_ids": [str(item["id"]) for item in candidates],
        "selected_case_ids": [str(case["id"]) for case in cases],
        "planned_requests": len(candidates) * len(cases),
        "network_requests_made": 0,
        "prompt_shape": "production-pr-mutation-hidden-ground-truth",
        "results": [],
        "candidate_summaries": [],
    }
    if args.execute_live:
        api_key = base.os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY is required only with --execute-live")
        by_candidate: dict[str, list[dict[str, Any]]] = {str(item["id"]): [] for item in candidates}
        for candidate in candidates:
            cid = str(candidate["id"])
            for case in cases:
                payload = build_payload(candidate, case, system_prompt, review_schema, contract, args.max_tokens)
                request_result = base.call_openrouter(payload, api_key, timeout_seconds=args.timeout_seconds)
                report["network_requests_made"] += 1
                score = score_case(case, request_result)
                row = {
                    "candidate_id": cid,
                    "case_id": str(case["id"]),
                    "difficulty": str(case.get("difficulty", "")),
                    "expected_findings": len(case["expected_findings"]),
                    "request": request_result,
                    "score": score,
                }
                report["results"].append(row)
                by_candidate[cid].append(row)
        report["candidate_summaries"] = [aggregate(candidate, by_candidate[str(candidate["id"])]) for candidate in candidates]
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
