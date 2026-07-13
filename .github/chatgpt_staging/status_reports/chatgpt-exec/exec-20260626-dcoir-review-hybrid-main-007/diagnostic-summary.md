# DCOIR Review hybrid exec 007 diagnostic summary

- result: failure
- failure: git diff --check failed

## Git status before cleanup
```text
 M .github/dcoir_review/openrouter-pr-review-pareto.yml
 M .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/latest_progress_marker.json
 M .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/progress_history.jsonl
 M .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/workflow_report.md
 M .github/ops/requests/apply_patch/README.md
 M .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py
 M .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
```

## Git status after cleanup
```text
 M .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/latest_progress_marker.json
 M .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/progress_history.jsonl
 M .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/workflow_report.md
?? .github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-007/diagnostic-summary.md
```
