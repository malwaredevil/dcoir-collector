# chatgpt-exec requests

Create reviewed `chatgpt-exec` request JSON files here:

```text
.github/chatgpt_staging/exec_requests/<request_id>.json
```

A push that creates or restages a request file should trigger `.github/workflows/chatgpt-exec.yml`.

After staging, monitor:

```text
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/progress_history.jsonl
```

Then read output from:

```text
.github/chatgpt_staging/status_reports/chatgpt-exec/<request_id>/artifact_readback/
```

Files written under `DCOIR_DOWNLOADS_DIR` appear under `artifact_readback/downloads/<output_folder>/`.
