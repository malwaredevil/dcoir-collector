#!/usr/bin/env python3
"""Issue #618, no-publication paired first-pass prompt evaluator.

Default is plan-only: no network requests, API key, GitHub writes, or changes
to tracked source. Live OpenRouter calls require separately approved operator
action; the --operator-approved flag is an acknowledgement, NOT that approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import dcoir_review_first_pass_candidate_eval as base
import dcoir_review_pr_mutation_eval as mutation
import openrouter_pr_review_pareto_context as review


DCOIR_ROOT = Path(__file__).resolve().parents[1]
CORPUS = DCOIR_ROOT / "evaluation" / "cross_file_recall_corpus_v1.json"
SCHEMA = "dcoir_cross_file_review_cases_v1"
REPORT_SCHEMA = "dcoir_cross_file_recall_comparison_v1"
MODES = ("baseline", "enhanced")


def modes_for(case: dict[str, Any]) -> tuple[str, ...]:
    """Single-file controls have identical prompts; do not pay twice."""
    return MODES if case.get("related_path") else ("enhanced",)


def load_cases() -> list[dict[str, Any]]:
    corpus = base.load_json(CORPUS)
    if corpus.get("schema_version") != SCHEMA:
        raise ValueError("Unexpected Issue618 recall corpus version")
    raw = corpus.get("cases")
    if not isinstance(raw, list) or len(raw) != 6:
        raise ValueError("Issue618 evaluation must have exactly 6 fixed cases")
    ids: set[str] = set()
    checked: list[dict[str, Any]] = []
    for case in raw:
        if not isinstance(case, dict):
            raise ValueError("Issue618 case is not an object")
        cid = str(case.get("id", "")).strip()
        expected = str(case.get("expected", ""))
        path = str(case.get("focus_path", "")).strip()
        source = str(case.get("focus_source", ""))
        if not cid or cid in ids or expected not in {"finding", "clean"}:
            raise ValueError(f"Invalid/duplicated label: {cid}")
        if not path or not source or not case.get("changed_diff", "").startswith("diff --git "):
            raise ValueError(f"Missing model-visible source/diff: {cid}")
        groups = case.get("match_groups")
        if expected == "finding" and (not isinstance(groups, list) or len(groups) < 2):
            raise ValueError(f"Missing hidden scoring requirements: {cid}")
        if expected == "clean" and groups is not None:
            raise ValueError(f"Clean case must not have finding match groups: {cid}")
        if expected == "finding":
            if not all(isinstance(g, list) and g and all(isinstance(t, str) and t for t in g) for g in groups):
                raise ValueError(f"Malformed hidden matching groups: {cid}")
        ids.add(cid)
        checked.append(case)
    if sum(case["expected"] == "finding" for case in checked) != 3:
        raise ValueError("Issue618 must contain 3 defect and 3 clean cases")
    return checked


def focus_patch(case: dict[str, Any]) -> str:
    prefix = f"diff --git a/{case['focus_path']} b/{case['focus_path']}"
    matches = [
        part for part in re.split(r"(?=^diff --git a/)", case["changed_diff"], flags=re.MULTILINE)
        if part.startswith(prefix + "\n")
    ]
    if len(matches) != 1:
        raise ValueError(f"{case['id']}: missing/ambiguous focus patch")
    patch = matches[0].rstrip() + "\n"
    added = mutation.added_lines(patch)
    if not added:
        raise ValueError(f"{case['id']}: focus lacks changed-right lines")
    if case["expected"] == "finding":
        if not any(str(case["expected_anchor"]) in text for _, text in added):
            raise ValueError(f"{case['id']}: expected anchor is not in changed RIGHT lines")
    return patch


def prompts(case: dict[str, Any], config: Any) -> dict[str, str]:
    """Use the actual maintained per-file first-pass prompt function twice."""
    patch = focus_patch(case)
    additions, deletions = mutation.file_stats(patch)
    item = {
        "filename": case["focus_path"],
        "status": "modified",
        "patch": patch,
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
    }
    pr = {"number": 9000, "title": "Synthetic cross-file validation change"}
    args = (pr, item, case["focus_source"], case["changed_diff"], config, [], "first-pass-deep")
    original = review.build_cross_file_contract_context
    try:
        review.build_cross_file_contract_context = lambda *_a, **_kw: ""
        baseline = review.build_per_file_review_prompt(*args)
    finally:
        review.build_cross_file_contract_context = original
    enhanced = review.build_per_file_review_prompt(*args)
    if not baseline or not enhanced or "Cross-file contract review cues" in baseline:
        raise ValueError(f"{case['id']}: baseline prompt was not baseline")
    if case["related_path"] and "Cross-file contract review cues" not in enhanced:
        raise ValueError(f"{case['id']}: enhanced prompt lacks cross-file cues")
    if case["related_path"] and baseline == enhanced:
        raise ValueError(f"{case['id']}: cross-file comparator input prompts are identical")
    if not case["related_path"] and baseline != enhanced:
        raise ValueError(f"{case['id']}: single-file control unexpectedly changed")
    for output in (baseline, enhanced):
        if str(case["supporting_contract"]) in output or str(case["counterexample"]) in output:
            raise ValueError(f"{case['id']}: hidden evaluation answer leaked into model prompt")
    return {"baseline": baseline, "enhanced": enhanced}


def _finding_matches(case: dict[str, Any], finding: Any, valid_lines: set[int]) -> bool:
    if not isinstance(finding, dict) or finding.get("path") != case["focus_path"]:
        return False
    try:
        line = int(finding.get("line", 0))
    except (TypeError, ValueError):
        return False
    if line not in valid_lines:
        return False
    severity = str(finding.get("severity", "") or "").lower()
    if case.get("severity") == "P1" and severity not in {"high", "critical"}:
        return False
    prose = " ".join(str(finding.get(key, "") or "") for key in ("title", "body", "validation")).lower()
    return all(any(term.lower() in prose for term in group) for group in case.get("match_groups", []))


def score(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if not response.get("ok"):
        return {"correct": False, "disposition": "request-error", "matched": 0, "extra": 0}
    value = response.get("result", {})
    findings = value.get("findings") if isinstance(value, dict) else None
    if not isinstance(findings, list):
        return {"correct": False, "disposition": "schema-error", "matched": 0, "extra": 0}
    if case["expected"] == "clean":
        return {"correct": not findings, "disposition": "clean" if not findings else "false-positive", "matched": 0, "extra": len(findings)}
    valid_lines = {line for line, _ in mutation.added_lines(focus_patch(case))}
    matches = [idx for idx, finding in enumerate(findings) if _finding_matches(case, finding, valid_lines)]
    # One root cause per positive fixture. Duplicate matching comments do
    # not improve recall; they are extra review noise for this benchmark.
    extras = len(findings) - int(bool(matches))
    return {
        "correct": bool(matches) and extras == 0,
        "disposition": ("found" if extras == 0 else "found-with-extras") if matches else "false-negative",
        "matched": len(matches),
        "extra": extras,
    }


def payload_for(candidate: dict[str, Any], prompt: str, args: argparse.Namespace) -> dict[str, Any]:
    matrix = base.load_matrix()
    system = base.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    schema = base.load_json(base.REVIEW_SCHEMA_PATH)
    contract = matrix.get("request_contract", {})
    synthetic = {"id": "issue618", "source": "", "counterexample": "", "review_contract": ""}
    payload = base.build_payload(candidate, synthetic, system, schema, contract)
    payload["messages"][1]["content"] = prompt
    payload["max_tokens"] = args.max_tokens
    if payload.get("model") != candidate["model"] or len(payload.get("messages", [])) != 2:
        raise ValueError("Unsafe evaluation payload")
    return payload


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="sonnet5.5-high")
    parser.add_argument("--case", action="append", default=[], help="case id; repeat for paired controls")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-requests", type=int, default=12)
    parser.add_argument("--max-cost-usd", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--execute-live", action="store_true", help="requires separate operator-approved exact command")
    parser.add_argument("--operator-approved", action="store_true", help="manual acknowledgement, not authorization")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    if not (1 <= args.max_tokens <= 8192 and 1 <= args.max_requests <= 12 and 1 <= args.timeout_seconds <= 180):
        raise SystemExit("Invalid bounded evaluation limits")
    matrix = base.load_matrix()
    candidate_list = base.selected_candidates(matrix, args.candidate)
    if len(candidate_list) != 1 or candidate_list[0]["model"].startswith(("openrouter/", "~")):
        raise SystemExit("Select exactly one pinned non-router model for paired comparison")
    candidate = candidate_list[0]
    cases = load_cases()
    if args.case:
        requested = set(args.case)
        cases = [case for case in cases if case["id"] in requested]
        unknown = requested - {case["id"] for case in cases}
        if unknown:
            raise SystemExit(f"Unknown Issue618 case ids: {sorted(unknown)}")
    requests = sum(len(modes_for(case)) for case in cases)
    if requests > args.max_requests:
        raise SystemExit(f"Plan has {requests} requests, beyond --max-requests={args.max_requests}")
    config = review.load_pareto_context_config(str(DCOIR_ROOT / "openrouter-pr-review-pareto.yml"))
    case_prompts = [(case, prompts(case, config)) for case in cases]
    metadata = [
        {
            "case_id": case["id"],
            "expected": case["expected"],
            "scheduled_variants": list(modes_for(case)),
            "prompts": {
                mode: {"chars": len(prompt), "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
                for mode, prompt in variants.items()
            },
        }
        for case, variants in case_prompts
    ]
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "mode": "live" if args.execute_live else "plan",
        "model": candidate["model"],
        "candidate_id": candidate["id"],
        "cases": metadata,
        "planned_requests": requests,
        "network_requests_made": 0,
        "max_tokens_per_request": args.max_tokens,
        "max_requests": args.max_requests,
        "max_cost_usd": args.max_cost_usd if args.execute_live else None,
        "reported_spend_usd": 0.0,
        "cost_limit_semantics": "reactive reported-cost stop; one billed request can exceed limit",
        "results": [],
        "partial": False,
        "stop_reason": "",
        "authorization": "operator separately approves exact live command; CLI acknowledgement is not approval",
    }
    if args.execute_live:
        if not args.operator_approved or not args.case:
            raise SystemExit("Live requires --operator-approved plus explicit --case selection and separate real approval")
        if not (0 < args.max_cost_usd <= 2.0):
            raise SystemExit("Live requires a positive --max-cost-usd at most 2")
        if not args.output:
            raise SystemExit("Live requires --output for audit; no data goes to GitHub")
        if Path(args.output).exists():
            raise SystemExit("Refusing to overwrite an existing paid-evaluation report")
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        if not secret:
            raise SystemExit("OPENROUTER_API_KEY missing (not needed in plan mode)")
        spent = 0.0
        for case, variants in case_prompts:
            for variant in modes_for(case):
                if spent >= args.max_cost_usd:
                    report["partial"] = True
                    report["stop_reason"] = "reported cost threshold reached"
                    break
                prompt = variants[variant]
                try:
                    request = base.call_openrouter(payload_for(candidate, prompt, args), secret, timeout_seconds=args.timeout_seconds)
                except Exception as exc:
                    # Network uncertainty can still incur provider billing. Stop
                    # without a retry and preserve the partial evidence report.
                    report["network_requests_made"] += 1
                    report["partial"] = True
                    report["stop_reason"] = f"request-exception:{type(exc).__name__}"
                    break
                report["network_requests_made"] += 1
                charge = request.get("usage", {}).get("cost_usd") if isinstance(request.get("usage"), dict) else None
                if not isinstance(charge, (float, int)) or not (0 < charge < 100):
                    report["partial"] = True
                    report["stop_reason"] = "provider cost missing, zero, or malformed"
                    break
                spent += float(charge)
                row = {
                    "case_id": case["id"],
                    "variant": variant,
                    "score": score(case, request),
                    "model": str(request.get("requested_model", "")),
                    "provider": request.get("selected_provider"),
                    "usage": request.get("usage"),
                    "latency_seconds": request.get("latency_seconds"),
                    "result": request.get("result") if request.get("ok") else None,
                    "error": request.get("error") if not request.get("ok") else None,
                }
                report["results"].append(row)
                report["reported_spend_usd"] = spent
                if not request.get("ok"):
                    report["partial"] = True
                    report["stop_reason"] = "provider returned an error"
                    break
                if spent > args.max_cost_usd:
                    report["partial"] = True
                    report["stop_reason"] = "single request exceeded reported cost threshold"
                    break
            if report["partial"]:
                break
        # Soft cap: one individually capped request may carry charge beyond
        # the provider-reported budget. This cannot limit server billing.
    if args.output:
        target = Path(args.output)
        if target.exists():
            raise SystemExit("Refusing to overwrite existing report")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["partial"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
