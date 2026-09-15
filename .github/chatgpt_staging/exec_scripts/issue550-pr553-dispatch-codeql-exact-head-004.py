from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "malwaredevil/dcoir-collector"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
EXPECTED_HEAD = "f4a6236d1ab6a9c13693fd07a4e702a92d523d77"
WORKFLOW = "codeql-security.yml"


def output(*args: str) -> str:
    cp = subprocess.run(args, text=True, capture_output=True)
    print(cp.stderr, end="", file=sys.stderr)
    if cp.returncode:
        raise RuntimeError(f"command failed {cp.returncode}: {args}")
    return cp.stdout.strip()

subprocess.run(["git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}"], check=True)
head = output("git", "rev-parse", f"refs/remotes/origin/{BRANCH}")
if head != EXPECTED_HEAD:
    raise RuntimeError(f"branch head drift before CodeQL dispatch: expected {EXPECTED_HEAD}, observed {head}")

payload = json.dumps({"ref": BRANCH}).encode("utf-8")
url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
errors: list[str] = []
for env_name in ("DCOIR_GITHUB_FG_TOKEN", "DCOIR_GITHUB_CL_TOKEN"):
    token = os.environ.get(env_name, "").strip()
    if not token:
        errors.append(f"{env_name}=missing")
        continue
    request = urllib.request.Request(url, data=payload, method="POST", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dcoir-chatgpt-exec",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
        if status == 204:
            print(f"token_source={env_name}")
            print(f"workflow={WORKFLOW}")
            print(f"ref={BRANCH}")
            print(f"exact_head={EXPECTED_HEAD}")
            print("dispatch_status=204")
            print("ISSUE550_PR553_DISPATCH_CODEQL_EXACT_HEAD_004_PASS")
            raise SystemExit(0)
        errors.append(f"{env_name}=http_{status}")
    except urllib.error.HTTPError as exc:
        errors.append(f"{env_name}=http_{exc.code}")
    except urllib.error.URLError as exc:
        errors.append(f"{env_name}=url_error_{type(exc.reason).__name__}")

raise RuntimeError("CodeQL workflow_dispatch failed: " + ", ".join(errors))
