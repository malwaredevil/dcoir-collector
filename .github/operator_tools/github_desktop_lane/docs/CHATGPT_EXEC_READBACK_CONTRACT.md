# ChatGPT exec readback contract

Use this note when a session is working with `chatgpt-exec`, `chatgpt-apply-in`, or `chatgpt-stage-out`.

## Required read order

1. Read the workflow report for the exact request id.
2. Read the progress history for the exact request id.
3. Read tracked summary files beside the workflow report when the request produced ChatGPT-readable summaries.
4. Use the uploaded GitHub Actions artifact for full output or provenance.
5. Treat `artifact_readback/` as optional and normally unavailable for `chatgpt-exec` Git readback.

## Canonical paths

```text
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/progress_history.jsonl
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/<tracked-summary>.json
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/<tracked-summary>.md
.github/chatgpt_staging/out/<request_id>/
```

## Exec output contract

For `chatgpt-exec`, full command output is uploaded as a short-retention GitHub Actions artifact. Do not expect full unzipped artifact contents to be committed into Git.

When ChatGPT needs connector-readable results, the approved command or reusable tool should write a concise sanitized summary beside the heartbeat report, for example:

```text
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/probe_summary.json
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/probe_report.md
```

These tracked summaries should contain the answer needed for follow-on reasoning, not full raw exports, large logs, secrets, or long generated paths.

## Artifact readback history and current policy

`artifact_readback/` was originally introduced as a committed unzipped copy of the GitHub Actions artifact contents. It is now intentionally ignored for `chatgpt-exec` because unzipped exec artifacts can contain long generated paths that break Windows checkout.

Current policy:

```text
heartbeat/report files = committed status source
tracked summary files = ChatGPT-readable result source when needed
uploaded GitHub Actions artifact = full output and provenance source
artifact_readback/ = optional local runner/readback tree; normally not committed for chatgpt-exec
```

Do not remove the `.gitignore` rule for `.github/chatgpt_staging/status_reports/chatgpt-exec/*/artifact_readback/` without a separate validation plan for Windows checkout safety.

## Canonical policy pointer

```text
.github/chatgpt_staging/HEARTBEAT_AND_ARTIFACT_READBACK.md
```

That file is a historical pointer. Current routing guidance lives in Supabase `ircore`; workflow-specific behavior lives in the workflow YAML header and body.
