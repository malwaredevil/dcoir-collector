#!/usr/bin/env python3
"""Read every GitHub validation surface required for governed PR readiness.

This helper deliberately reads both Actions workflow runs and the complete commit
check-run collection. GitHub Advanced Security may publish a separate failing
CodeQL results check even when the CodeQL Actions workflow itself succeeds.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

BLOCKING_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "stale",
    "startup_failure",
    "timed_out",
}
PENDING_STATES = {"expected", "in_progress", "pending", "queued", "requested", "waiting"}


def gh_json(endpoint: str, *, fields: dict[str, str] | None = None) -> Any:
    cmd = ["gh", "api", "-X", "GET", endpoint]
    for key, value in (fields or {}).items():
        cmd.extend(["-f", f"{key}={value}"])
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def review_threads(repo: str, number: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    query = """
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      reviewThreads(first:100){
        nodes{id isResolved}
        pageInfo{hasNextPage}
      }
    }
  }
}
""".strip()
    cmd = [
        "gh", "api", "graphql", "-f", f"query={query}",
        "-F", f"owner={owner}", "-F", f"name={name}", "-F", f"number={number}",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    return payload["data"]["repository"]["pullRequest"]["reviewThreads"]


def failed_annotations(repo: str, check_runs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    annotations: list[dict[str, Any]] = []
    gaps: list[str] = []
    for check in check_runs:
        title = str((check.get("output") or {}).get("title") or "")
        reports_new_alerts = bool(re.search(r"\b[1-9]\d* new alerts?\b", title, re.IGNORECASE))
        if check.get("conclusion") not in BLOCKING_CONCLUSIONS and not reports_new_alerts:
            continue
        check_id = check.get("id")
        try:
            rows = gh_json(f"repos/{repo}/check-runs/{check_id}/annotations", fields={"per_page": "100"})
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            gaps.append(f"could not read annotations for check {check_id}: {exc}")
            continue
        for row in rows:
            annotations.append(
                {
                    "check_id": check_id,
                    "check_name": check.get("name"),
                    "path": row.get("path"),
                    "start_line": row.get("start_line"),
                    "annotation_level": row.get("annotation_level"),
                    "title": row.get("title"),
                    "message": row.get("message"),
                }
            )
    return annotations, gaps


def evaluate_snapshot(snapshot: dict[str, Any], expected_head: str | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    pending: list[str] = []
    gaps: list[str] = list(snapshot.get("gaps", []))
    pr = snapshot["pr"]
    head = str(pr.get("head", {}).get("sha") or "")

    if expected_head and head != expected_head:
        blockers.append(f"PR head mismatch: expected {expected_head}, observed {head}")
    if pr.get("mergeable") is False or pr.get("mergeable_state") == "dirty":
        blockers.append("PR has merge conflicts")
    if pr.get("mergeable") is None:
        pending.append("PR mergeability is not yet computed")

    check_runs = snapshot.get("check_runs", [])
    if not check_runs:
        gaps.append("no commit check runs were returned")
    for check in check_runs:
        name = str(check.get("name") or check.get("id"))
        status = str(check.get("status") or "")
        conclusion = check.get("conclusion")
        title = str((check.get("output") or {}).get("title") or "")
        reports_new_alerts = bool(re.search(r"\b[1-9]\d* new alerts?\b", title, re.IGNORECASE))
        if conclusion in BLOCKING_CONCLUSIONS:
            suffix = f" ({title})" if title else ""
            blockers.append(f"check run failed: {name}{suffix}")
        elif reports_new_alerts:
            blockers.append(f"check run reports new alerts: {name} ({title})")
        elif status != "completed" or conclusion in PENDING_STATES or conclusion is None:
            pending.append(f"check run incomplete: {name} [{status}/{conclusion}]")

    workflow_runs = snapshot.get("workflow_runs", [])
    for run in workflow_runs:
        name = str(run.get("name") or run.get("id"))
        status = str(run.get("status") or "")
        conclusion = run.get("conclusion")
        if conclusion in BLOCKING_CONCLUSIONS:
            blockers.append(f"workflow run failed: {name}")
        elif status != "completed" or conclusion in PENDING_STATES or conclusion is None:
            pending.append(f"workflow run incomplete: {name} [{status}/{conclusion}]")

    combined = snapshot.get("combined_status", {})
    statuses = combined.get("statuses", []) or []
    combined_state = combined.get("state")
    # GitHub reports combined state "pending" when no legacy commit statuses
    # exist. An empty legacy-status surface is not itself a pending validation.
    if statuses or int(combined.get("total_count", 0) or 0) > 0:
        if combined_state in {"failure", "error"}:
            blockers.append(f"commit status failed: {combined_state}")
        elif combined_state == "pending":
            pending.append("commit status is pending")
    for status in statuses:
        state = status.get("state")
        context = status.get("context") or status.get("id")
        if state in {"failure", "error"}:
            blockers.append(f"commit status failed: {context}")
        elif state == "pending":
            pending.append(f"commit status pending: {context}")

    threads = snapshot.get("review_threads", {})
    if threads.get("pageInfo", {}).get("hasNextPage"):
        gaps.append("more than 100 review threads exist; pagination is required")
    unresolved = [item for item in threads.get("nodes", []) or [] if not item.get("isResolved")]
    if unresolved:
        blockers.append(f"unresolved review threads: {len(unresolved)}")

    return {
        "head_sha": head,
        "blockers": blockers,
        "pending": pending,
        "gaps": gaps,
        "ready": not blockers and not pending and not gaps,
    }


def collect(repo: str, pr_number: int) -> dict[str, Any]:
    pr = gh_json(f"repos/{repo}/pulls/{pr_number}")
    head = pr["head"]["sha"]
    check_payload = gh_json(f"repos/{repo}/commits/{head}/check-runs", fields={"per_page": "100"})
    workflow_payload = gh_json(
        f"repos/{repo}/actions/runs",
        fields={"head_sha": head, "per_page": "100"},
    )
    combined_status = gh_json(f"repos/{repo}/commits/{head}/status")
    threads = review_threads(repo, pr_number)
    annotations, gaps = failed_annotations(repo, check_payload.get("check_runs", []))
    return {
        "pr": pr,
        "check_runs": check_payload.get("check_runs", []),
        "workflow_runs": workflow_payload.get("workflow_runs", []),
        "combined_status": combined_status,
        "review_threads": threads,
        "failed_annotations": annotations,
        "gaps": gaps,
    }


def print_text(snapshot: dict[str, Any], evaluation: dict[str, Any]) -> None:
    pr = snapshot["pr"]
    print(f"PR #{pr['number']} head: {evaluation['head_sha']}")
    print(f"state={pr.get('state')} draft={pr.get('draft')} mergeable={pr.get('mergeable')} mergeable_state={pr.get('mergeable_state')}")
    print("\nCHECK RUNS")
    for check in snapshot.get("check_runs", []):
        title = (check.get("output") or {}).get("title") or ""
        print(f"- {check.get('id')} {check.get('name')}: {check.get('status')}/{check.get('conclusion')} {title}".rstrip())
    print("\nWORKFLOW RUNS")
    for run in snapshot.get("workflow_runs", []):
        print(f"- {run.get('id')} {run.get('name')}: {run.get('status')}/{run.get('conclusion')}")
    if snapshot.get("failed_annotations"):
        print("\nFAILED CHECK ANNOTATIONS")
        for item in snapshot["failed_annotations"]:
            print(f"- {item['check_name']} [{item['path']}:{item['start_line']}]: {item['title']}")
            if item.get("message"):
                print(f"  {item['message']}")
    print("\nREADINESS")
    for label in ("blockers", "pending", "gaps"):
        values = evaluation[label]
        print(f"{label}: {len(values)}")
        for value in values:
            print(f"- {value}")
    print(f"ready={evaluation['ready']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="owner/repository")
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--expected-head")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        snapshot = collect(args.repo, args.pr)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as exc:
        print(f"validation readback failed: {exc}", file=sys.stderr)
        return 2
    evaluation = evaluate_snapshot(snapshot, args.expected_head)
    if args.json:
        print(json.dumps({"snapshot": snapshot, "evaluation": evaluation}, indent=2, sort_keys=True))
    else:
        print_text(snapshot, evaluation)
    return 0 if evaluation["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
