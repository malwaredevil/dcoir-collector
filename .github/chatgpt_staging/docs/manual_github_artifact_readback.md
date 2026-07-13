# ChatGPT GitHub Artifact Readback

Use this workflow when ChatGPT needs connector-readable access to a GitHub Actions artifact without asking the operator to download and re-upload the ZIP manually.

## Workflow

- workflow name: `chatgpt-github-artifact-readback`
- workflow file: `.github/workflows/manual-github-artifact-readback.yml`

## Trigger options

Preferred automatic trigger:

- commit a bounded request JSON under `.github/chatgpt_staging/requests/github_artifact_readback/`
- schema: `dcoir.chatgpt_staging.github_artifact_readback_request.v1`

Fallback manual trigger:

- use `workflow_dispatch` with either `request_path` or the direct bounded inputs

## Request JSON shape

```json
{
  "schema": "dcoir.chatgpt_staging.github_artifact_readback_request.v1",
  "request_id": "artifact-readback-26581484030-validate-gemini-behavioral-replay",
  "source_run_id": "26581484030",
  "artifact_name": "validate-gemini-behavioral-replay-results",
  "artifact_subpath": ""
}
```

Use `artifact_id` instead of `artifact_name` when the artifact id is the safer selector.

## Readback paths

Live polling during execution:

```text
.github/chatgpt_staging/status_reports/chatgpt-github-artifact-readback/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/chatgpt-github-artifact-readback/<request_id>/progress_history.jsonl
.github/chatgpt_staging/status_reports/chatgpt-github-artifact-readback/<request_id>/latest_progress_marker.json
```

Successful runs also write:

```text
.github/chatgpt_staging/out/<request_id>/artifact_manifest.json
.github/chatgpt_staging/out/<request_id>/artifact_manifest.md
.github/chatgpt_staging/out/<request_id>/...
```

The staged output under `.github/chatgpt_staging/out/<request_id>/` is the primary ChatGPT-readable surface after the heartbeat report reaches `result: success`.

## Use pattern

1. Check Gmail `label:GitHub` with the GitHub subject prefix `[DCOIR-Collector/dcoir-collector]` as an early liveness signal only. In connector metadata and returned labels, the same mailbox label may appear as `Label_125`.
2. Poll `.github/chatgpt_staging/status_reports/chatgpt-github-artifact-readback/<request_id>/workflow_report.md` until `result` becomes `success` or `failure`.
3. Do not use `repo-workflows/.../workflow_report.md` completed-run summaries for live polling.
4. Read the source workflow report first.
5. Confirm the source run id and artifact name or id.
6. Prefer a request JSON under `.github/chatgpt_staging/requests/github_artifact_readback/`.
7. After success, read `artifact_manifest.md` and the staged files under `.github/chatgpt_staging/out/<request_id>/`.
8. Prefer a scoped `chatgpt-staging-cleanup` marker when the readback is complete and you want immediate bounded cleanup.
9. If scoped cleanup is not requested first, `chatgpt-report-retention-cleanup` is the automatic fallback that prunes stale request JSON files, staged output bundles, and status reports by policy.

## Safety notes

- Do not use absolute paths or parent traversal in `artifact_subpath`.
- Do not use this workflow as a substitute for heartbeat-first readback when the source workflow already commits the answer directly.
- Keep the staged bundle only as long as needed for readback and validation evidence.
