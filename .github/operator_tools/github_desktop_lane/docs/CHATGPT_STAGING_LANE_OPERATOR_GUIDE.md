# ChatGPT Staging Lane Operator Guide

Use this guide when ChatGPT says the normal GitHub connector is too small, fragile, or awkward and it gives you a staging-lane bundle, request, payload, or cleanup marker.

## What this lane is for

The staging lane is a safer transfer area inside the repository. ChatGPT prepares a bounded request or payload, GitHub Actions processes it, and ChatGPT verifies the result from GitHub readback.

Use it for:

- large or awkward repo readback
- multi-file apply-in bundles
- workflow troubleshooting where ChatGPT needs a readable report
- cleanup of temporary staging artifacts

Do not use it for normal small edits when the GitHub connector or a simple GitHub Desktop bundle is enough.

## The simple operator workflow

1. ChatGPT gives you a ZIP bundle and a suggested commit summary.
2. You apply the ZIP to the local repo, review the changed files, commit, and push.
3. You say only:

```text
cap
```

4. ChatGPT verifies GitHub readback.
5. If a workflow ran, ChatGPT checks the workflow report before asking you for logs.
6. If temporary staging files are no longer needed, ChatGPT creates or recommends a cleanup marker.

## What ChatGPT should do

ChatGPT should:

- tell you what the bundle is for before CAP
- keep affected files narrow
- give a suggested commit summary
- verify the commit by GitHub readback after you say `cap`
- check `workflow_report.md` before asking for screenshots, pasted logs, uploaded logs, or a commit SHA
- record Supabase work-item readback after governed GitHub evidence changes
- recommend the next step after status updates
- clean consumed staging artifacts when safe

## What you usually do

Most of the time, your job is only:

```text
Apply the ZIP, review the changed files, commit, push, then say cap.
```

You should not normally need to:

- find a commit SHA manually
- upload GitHub Actions logs
- paste terminal output
- screenshot failures
- decide which staging folders to delete

If ChatGPT truly needs a SHA or local diagnostic output, it should give you a copy/paste command or tool.

## Where ChatGPT looks first after a workflow run

```text
.github/chatgpt_staging/status_reports/<workflow-name>/<request-id-or-run-id>/workflow_report.md
```

Each workflow result should create one Markdown report. Do not expect paired JSON and Markdown reports.

The report should tell ChatGPT:

- whether the workflow succeeded or failed
- which workflow ran
- which request or payload was involved
- which files changed, were removed, or were retained
- why a failure happened, when known
- where a larger artifact/log is, when one is needed
- what ChatGPT should do next
- how to clean the report after reading it

## If something fails

Say:

```text
cap
```

or ask:

```text
Check the latest workflow report.
```

ChatGPT should inspect the committed report under `.github/chatgpt_staging/status_reports/` first. If the report points to a GitHub Actions artifact or run log, ChatGPT should use that pointer before asking you for manual logs.

## Cleanup expectations

Staging files are temporary unless Supabase work-item evidence or the active governed issue says to keep them.

ChatGPT should clean staging artifacts after it has consumed them:

- output bundles after ChatGPT retrieves needed files
- inbound payloads after successful apply or failed-payload diagnosis
- status reports after ChatGPT reads them and records evidence
- failure reports after the retry/stop decision is recorded
- apply reports after commit/readback evidence is recorded

Cleanup is done with a scoped marker under:

```text
.github/chatgpt_staging/cleanup_requests/<request_id>.json
```

The cleanup workflow may leave one final cleanup `workflow_report.md` as proof of what it removed. ChatGPT can remove that report later after reading it.

## Safety rules in plain English

- Stage-out requests must stay narrow.
- Apply-in bundles must include current-file proof before overwriting tracked files.
- New files must be marked create-only and include a new-content hash.
- Workflow files are blocked by default unless the repair is explicit and approved.
- Cleanup must stay inside `.github/chatgpt_staging/`.
- `.gitkeep` scaffold files should never be deleted.
- ChatGPT should not claim production readiness until validation evidence exists.

## Useful phrases to say

| Situation | Say this |
|---|---|
| You applied and pushed the bundle | `cap` |
| You want ChatGPT to inspect workflow output | `Check the latest workflow report.` |
| You want ChatGPT to continue the plan | `Proceed.` |
| You want a status and recommendation | `Where are we and what do you recommend next?` |
| You do not know how to get a SHA/log | `Give me the command or tool for that.` |

## Quick glossary

| Term | Meaning |
|---|---|
| CAP | Your signal that you committed and pushed the bundle. |
| stage-out | GitHub packages repo files for ChatGPT to read. |
| apply-in | GitHub applies a ChatGPT-prepared payload to the repo. |
| cleanup marker | A small JSON file ChatGPT creates to ask GitHub to clean staging artifacts. |
| workflow report | A ChatGPT-readable Markdown report written by a staging workflow. |
| retention policy | The rule for what staging artifacts stay temporarily and what gets cleaned. |
