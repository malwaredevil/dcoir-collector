# Stage-out readback

After staging `chatgpt-stage-out`, monitor the committed heartbeat files:

```text
.github/chatgpt_staging/status_reports/chatgpt-stage-out/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/chatgpt-stage-out/<request_id>/progress_history.jsonl
```

For output inspection, the primary readback path is the committed output directory:

```text
.github/chatgpt_staging/out/<request_id>/
```

Read `manifest.md`, `manifest.json`, `chunks/`, and `files/` directly through the GitHub connector. The ZIP artifact is supplemental.
