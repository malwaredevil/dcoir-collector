# Exec request readback

After staging a `chatgpt-exec` request, monitor the committed heartbeat files:

```text
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/progress_history.jsonl
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/latest_progress_marker.json
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/final_readback_marker.json
```

For result inspection, read any tracked summary files beside the heartbeat report first. Examples:

```text
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/probe_summary.json
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/probe_report.md
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/validation_summary.json
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/validation_report.md
```

Use the uploaded GitHub Actions artifact for full output, large logs, raw exports, or provenance.

## Important artifact_readback rule

Do not assume this path exists in Git for `chatgpt-exec`:

```text
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/artifact_readback/
```

It is intentionally ignored because unzipped exec artifacts can contain long generated paths that break Windows checkout. Older docs and historical reports may still mention committed `artifact_readback/`; treat that as stale wording unless files are actually present in Git.

## Current interpretation

```text
heartbeat/report files = committed status source
tracked summary files = ChatGPT-readable result source when needed
uploaded GitHub Actions artifact = full output/provenance source
artifact_readback/ = optional and normally not committed for chatgpt-exec
```
