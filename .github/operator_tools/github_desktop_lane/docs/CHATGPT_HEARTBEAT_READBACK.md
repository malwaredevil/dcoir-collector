# ChatGPT heartbeat readback guide

Status: active companion guide for the GitHub Desktop lane and GitHub Actions staging workflows.

## Applies to

- `chatgpt-exec`
- `chatgpt-apply-in` / `chatgpt-in`
- `chatgpt-stage-out`
- `chatgpt-github-artifact-readback`

## What ChatGPT should read first

For each staged workflow, ChatGPT should read the committed heartbeat path before asking the operator for screenshots, pasted logs, uploaded files, or manual artifact handling:

```text
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/progress_history.jsonl
```

## Artifact readback

ZIP artifacts are still uploaded by GitHub Actions for short-retention provenance and operator download. They are not the primary ChatGPT readback path.

When sanitized output files are produced, workflows should also commit an unzipped readback path:

```text
.github/chatgpt_staging/status_reports/<workflow>/<request_id>/artifact_readback/
```

For `chatgpt-exec`, files written under `DCOIR_DOWNLOADS_DIR` appear under `artifact_readback/downloads/<output_folder>/`.

For `chatgpt-stage-out`, the primary unzipped readback path is:

```text
.github/chatgpt_staging/out/<request_id>/
```

For `chatgpt-github-artifact-readback`, the primary extracted artifact path is also:

```text
.github/chatgpt_staging/out/<request_id>/
```

Read `artifact_manifest.md` there first, then inspect the staged files it lists.

## Current exec-lane implementation

`.github/operator_tools/github_desktop_lane/scripts/Invoke-DcoirActionsExecHarness.ps1` copies sanitized exec artifact contents into `artifact_readback/` beside the committed exec workflow report. The uploaded ZIP artifact remains available separately.

## Operator note

If a future session says it cannot read an artifact, have it check the committed heartbeat report and readback path first. Artifact ZIP download should be treated as fallback evidence, not the first or only path.
