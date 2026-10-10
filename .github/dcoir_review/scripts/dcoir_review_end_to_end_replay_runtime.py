"""Fake GitHub/OpenRouter network runtime for the end-to-end replay selftest."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from dcoir_review_end_to_end_replay_support import (
    BASE_SHA, CLEAN, HEAD, HTTP, NEW_HEAD, PR, PY_LINES, REPO, Raw, TimeoutErr,
    VERIFIED, files_default,
)


def run_one(repo_root: str, name: str, spec: dict[str, Any]) -> None:
    os.chdir(repo_root)
    sys.path.insert(0, os.path.join(repo_root, ".github", "dcoir_review", "scripts"))
    from dcoir_review import adversarial_prompt_policy as app

    challenger_marker = app.INDEPENDENT_CONFIRMATION_INTRO[:80]
    files = spec.get("files") or files_default(6)
    gh_opts = spec.get("gh", {})
    incremental = bool(spec.get("incremental")) and os.environ.get("E2E_PHASE") == "second"
    head = NEW_HEAD if incremental else HEAD
    state = {"count": 0, "kinds": [], "gh_calls": 0, "review_posts": 0, "unknown": [], "file_in_prompt": "", "posted": None, "status": []}
    seq_pos: dict[str, int] = {}

    def patch_for(entry):
        lines = entry.get("lines", PY_LINES)
        body = "\n".join("+" + line for line in lines)
        return f"@@ -0,0 +1,{len(lines)} @@\n{body}"

    def gh_files():
        out = []
        for e in files:
            status = e.get("status", "added")
            item = {"filename": e["path"], "status": status, "sha": "3" * 40,
                    "additions": 0 if status == "removed" else len(e.get("lines", PY_LINES)),
                    "deletions": len(PY_LINES) if status == "removed" else 0}
            item["changes"] = item["additions"] + item["deletions"]
            if e.get("previous_filename"):
                item["previous_filename"] = e["previous_filename"]
            if status == "removed":
                item["patch"] = "@@ -1,%d +0,0 @@\n" % len(PY_LINES) + "\n".join("-" + l for l in PY_LINES)
            elif not e.get("binary") and not e.get("nopatch"):
                item["patch"] = patch_for(e)
            out.append(item)
        return out

    def diff_text():
        chunks = []
        for e in files:
            p = e["path"]
            status = e.get("status", "added")
            if e.get("nopatch"):
                continue
            if e.get("binary"):
                chunks.append(f"diff --git a/{p} b/{p}\nnew file mode 100644\nindex 0000000..1111111\nBinary files /dev/null and b/{p} differ\n")
            elif status == "removed":
                chunks.append(f"diff --git a/{p} b/{p}\ndeleted file mode 100644\nindex 1111111..0000000\n--- a/{p}\n+++ /dev/null\n@@ -1,{len(PY_LINES)} +0,0 @@\n" + "\n".join("-" + l for l in PY_LINES) + "\n")
            elif status == "renamed":
                chunks.append(f"diff --git a/{e['previous_filename']} b/{p}\nsimilarity index 50%\nrename from {e['previous_filename']}\nrename to {p}\n--- a/{e['previous_filename']}\n+++ b/{p}\n{patch_for(e)}\n")
            else:
                chunks.append(f"diff --git a/{p} b/{p}\nnew file mode 100644\nindex 0000000..1111111\n--- /dev/null\n+++ b/{p}\n{patch_for(e)}\n")
        return "".join(chunks)

    prior_body = ""
    if incremental:
        with open(os.environ["E2E_PRIOR_REVIEW"], encoding="utf-8") as handle:
            prior_body = handle.read()

    def gh_handler(method, path, body):
        state["gh_calls"] += 1
        cur_head = head
        if gh_opts.get("head_moves_after") and state["gh_calls"] > gh_opts["head_moves_after"] + 30:
            cur_head = "9" * 40
        if method == "GET" and re.fullmatch(rf"/repos/{REPO}/pulls/{PR}", path):
            return {"number": PR, "state": gh_opts.get("state", "open"), "title": "replay", "body": "", "draft": False,
                    "head": {"sha": cur_head, "ref": "feature", "repo": {"full_name": REPO}},
                    "base": {"sha": BASE_SHA, "ref": "main", "repo": {"full_name": REPO}}, "user": {"login": "malwaredevil"}}
        if method == "GET" and path.startswith(f"/repos/{REPO}/pulls/{PR}/files"):
            mpage = re.search(r"[?&]page=(\d+)", path)
            page = int(mpage.group(1)) if mpage else 1
            allf = gh_files()
            return allf[(page - 1) * 100: page * 100]
        if method == "GET" and path.startswith(f"/repos/{REPO}/pulls/{PR}/reviews"):
            if incremental and not re.search(r"[?&]page=([2-9]|\d\d)", path):
                return [{"id": 700, "body": prior_body, "commit_id": HEAD, "state": "COMMENTED", "user": {"login": "github-actions[bot]"}}]
            return []
        if method == "GET" and (path.startswith(f"/repos/{REPO}/issues/{PR}/comments") or path.startswith(f"/repos/{REPO}/pulls/{PR}/comments")):
            return []
        if method == "GET" and "/contents/" in path:
            fname = path.split("/contents/", 1)[1].split("?", 1)[0]
            entry = next((e for e in files if e["path"] == fname), None)
            if entry is None or entry.get("status") == "removed":
                raise HTTP(404, '{"message":"Not Found"}')
            if entry.get("binary"):
                content = b"\x89PNG\r\n\x1a\n\x00\x00"
            else:
                content = ("\n".join(entry.get("lines", PY_LINES)) + "\n").encode()
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(content).decode(), "sha": "3" * 40, "size": len(content)}
        if method == "GET" and "/compare/" in path:
            return {"status": "ahead", "ahead_by": 1, "behind_by": 0, "files": gh_files(), "commits": [{"sha": NEW_HEAD}],
                    "merge_base_commit": {"sha": HEAD}, "base_commit": {"sha": HEAD}}
        if method == "GET" and "/actions/runs/" in path:
            run_id = path.rsplit("/", 1)[1]
            return {"id": int(run_id), "path": ".github/workflows/openrouter-pr-review.yml", "event": "issue_comment",
                    "status": "completed", "conclusion": "success", "head_branch": "main", "actor": {"login": "malwaredevil"},
                    "name": f"28 Review - DCOIR Review | PR #{PR} | malwaredevil"}
        if method == "POST" and path.endswith("/reactions"):
            if gh_opts.get("reaction_fail"):
                raise HTTP(403, '{"message":"Resource not accessible by integration"}')
            return {"id": 99}
        if method == "DELETE":
            return {}
        if method == "POST" and path == f"/repos/{REPO}/issues/{PR}/comments":
            state["status"].append(body.get("body", ""))
            return {"id": 555}
        if method == "PATCH" and "/issues/comments/" in path:
            state["status"].append(body.get("body", ""))
            return {"id": 555}
        if method == "POST" and path == f"/repos/{REPO}/pulls/{PR}/reviews":
            state["review_posts"] += 1
            if gh_opts.get("review_422_always"):
                raise HTTP(422, '{"message":"Validation Failed","errors":[{"resource":"PullRequestReview","code":"invalid","field":"event"}]}')
            if gh_opts.get("review_422_once") and state["review_posts"] == 1 and body.get("comments"):
                if gh_opts.get("review_422_shape") == "structured":
                    raise HTTP(422, '{"message":"Validation Failed","errors":[{"resource":"PullRequestReviewComment","code":"unprocessable","field":"line"}]}')
                # GitHub's actual create-review response for an unresolvable inline anchor.
                raise HTTP(422, '{"message":"Unprocessable Entity","errors":["Line could not be resolved"],"status":"422"}')
            state["posted"] = body
            return {"id": 777, "commit_id": body.get("commit_id"), "html_url": "https://example.invalid/review/777"}
        state["unknown"].append(f"{method} {path}")
        return []

    def classify(payload):
        schema = payload.get("response_format", {}).get("json_schema", {}).get("schema", {})
        title = str(schema.get("title", ""))
        prompt = payload["messages"][-1]["content"]
        hits = [(prompt.find(e["path"]), e["path"]) for e in files if e["path"] in prompt]
        state["file_in_prompt"] = min(hits)[1] if hits else "tools/replay_0.py"
        if "Verifier" in title:
            return "verifier"
        if "Critic" in title:
            return "repair-critic"
        if "Repair" in title or "Fix Synthesis" in title:
            return "repair-author"
        if "Candidate hypotheses from the bounded primary/challenger evidence" in prompt:
            return "v44-adjudication-retry" if "Review quality retry:" in prompt else "v44-adjudicator"
        if "Candidate hypotheses from the earlier detector/challenger stages" in prompt:
            return "v35-adjudication-retry" if "Review quality retry:" in prompt else "v35-adjudicator"
        if "Review quality retry:" in prompt:
            return "quality-retry"
        if challenger_marker in prompt:
            return "challenger"
        return "first-pass"

    model = spec.get("model", {})

    def respond(kind, payload):
        state["count"] += 1
        handler = model.get(kind)
        if handler is None:
            if kind == "verifier":
                return VERIFIED
            if kind in ("repair-author", "repair-critic"):
                return {}
            if kind == "challenger":
                return CLEAN
            if kind.endswith("adjudication-retry"):
                return CLEAN
            if kind.endswith("adjudicator"):
                return CLEAN
            if kind == "quality-retry":
                return CLEAN
            return CLEAN
        if callable(handler):
            out = handler(state, payload)
        else:
            i = seq_pos.get(kind, 0)
            out = handler[min(i, len(handler) - 1)]
            seq_pos[kind] = i + 1
        if isinstance(out, BaseException):
            raise out
        return out

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def http_error(url, exc):
        return urllib.error.HTTPError(url, exc.code, "err", {}, io.BytesIO(str(exc.body).encode()))

    def fake_urlopen(req, timeout=None, **_kw):
        url = req.full_url
        method = req.get_method()
        data = json.loads(req.data.decode()) if req.data else None
        parts = urllib.parse.urlsplit(url)
        if parts.hostname == "openrouter.ai":
            kind = classify(data)
            state["kinds"].append(kind)
            try:
                parsed = respond(kind, data)
            except HTTP as exc:
                raise http_error(url, exc)
            except TimeoutErr:
                import socket
                raise socket.timeout("timed out")
            except Raw as raw:
                out = {"model": data.get("model"), "choices": [{"finish_reason": raw.finish, "message": {"content": raw.content}}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
                return Resp(json.dumps(out).encode())
            out = {"id": "gen", "model": data.get("model"), "provider": "Fake", "service_tier": "default",
                   "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(parsed)}}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
            return Resp(json.dumps(out).encode())
        if parts.hostname == "api.github.com":
            path = parts.path + (f"?{parts.query}" if parts.query else "")
            accept = req.headers.get("Accept", "")
            if method == "GET" and ".diff" in accept:
                return Resp(diff_text().encode())
            try:
                return Resp(json.dumps(gh_handler(method, path, data)).encode())
            except HTTP as exc:
                raise http_error(url, exc)
        raise RuntimeError(f"unexpected network: {url}")

    urllib.request.urlopen = fake_urlopen
    import time as _time
    _time.sleep = lambda *_a, **_k: None
    debug_dir = tempfile.mkdtemp(prefix="dcoir-e2e-")
    body = ("/dcoir-review " + spec.get("suffix", "")).strip()
    os.environ.update({
        "GITHUB_TOKEN": "x", "OPENROUTER_API_KEY": "x", "GITHUB_REPOSITORY": REPO, "PR_NUMBER": str(PR),
        "TRIGGER_COMMENT_ID": "4242", "TRIGGER_COMMENT_BODY": body, "TRIGGER_AUTHOR": "malwaredevil",
        "OPENROUTER_REVIEW_CONFIG": ".github/dcoir_review/openrouter-pr-review-pareto.yml",
        "DCOIR_REVIEW_DEBUG_ARTIFACT_DIR": debug_dir, "REVIEW_ASSIST_CONTEXT_PATH": "",
        "GITHUB_RUN_ID": "38000000001" if not incremental else "38000000002", "GITHUB_WORKFLOW": "28 Review - DCOIR Review",
        "GITHUB_RUN_ATTEMPT": "1",
    })
    outcome = "ok"
    try:
        from dcoir_review.entrypoint import DcoirReviewEntrypoint
        DcoirReviewEntrypoint().run()
    except SystemExit as exc:
        outcome = f"SystemExit {exc.code}"
    except Exception as exc:  # noqa: BLE001 - every run failure is a scenario outcome
        outcome = f"{type(exc).__name__}: {str(exc)[:500]}"
        if os.environ.get("E2E_TB"):
            traceback.print_exc()
    posted = state["posted"]
    result = {
        "name": name, "outcome": outcome, "kinds": state["kinds"],
        "review_posted": posted is not None,
        "review_attempts": state["review_posts"],
        "comments": len(posted.get("comments", [])) if posted else None,
        "event": posted.get("event") if posted else None,
        "body_head": (posted.get("body", "") if posted else "")[:300],
        "body_full": posted.get("body", "") if posted else "",
        "unknown_gh": sorted(set(state["unknown"]))[:10],
        "status_tail": (state["status"][-1] if state["status"] else "")[-400:],
    }
    if spec.get("incremental") and os.environ.get("E2E_PHASE") != "second" and posted:
        with open(os.environ["E2E_PRIOR_REVIEW"], "w", encoding="utf-8") as fh:
            fh.write(posted.get("body", ""))
    shutil.rmtree(debug_dir, ignore_errors=True)
    print("E2E_RESULT " + json.dumps(result))
