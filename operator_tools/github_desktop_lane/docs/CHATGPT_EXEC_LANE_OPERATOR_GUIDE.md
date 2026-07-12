# ChatGPT Exec Lane Operator Guide

## What this is

The ChatGPT exec lane is a GitHub Actions lane that runs a command after the operator has reviewed and approved the exact command text in chat. It is designed to act like a virtual operator runner while preserving the source tools unchanged.

## What it does not do

- It does not store secret values in the repository.
- It does not require a maintained command allowlist.
- It does not modify source tools for GitHub Actions.
- It does not keep request files after the run when cleanup is enabled.

## One-time GitHub setup

Add repository secrets for the DCOIR variables that the runner should be able to use.

1. Open the GitHub repository.
2. Click **Settings**.
3. In the left menu, click **Secrets and variables**.
4. Click **Actions**.
5. Click **New repository secret**.
6. Add the needed names exactly, for example:
   - `DCOIR_GITHUB_FG_TOKEN`
   - `DCOIR_GITHUB_CL_TOKEN`
   - `DCOIR_GEMINI_API`
   - `DCOIR_OPENAI_API_KEY`
   - `DCOIR_OPENAI_PROJECT_ID`
   - `OPENAI_API_KEY`
7. Paste each value only into GitHub's secret value field. Do not commit values into files.

Optional GitHub Environment protection means putting secrets in a named environment and requiring a reviewer before jobs using that environment can start. This lane does not require that protection by default because the operator approval happens before the request is staged.

## Normal execution flow

1. ChatGPT drafts the exact command.
2. Operator reviews and approves the command in chat.
3. ChatGPT stages a request JSON under `chatgpt_staging/exec_requests/`.
4. GitHub Actions runs the command on a Windows runner.
5. The workflow writes a status report under `chatgpt_staging/status_reports/chatgpt-exec/`.
6. The workflow uploads a short-retention artifact containing logs and outputs.
7. ChatGPT reads the status report and downloads the artifact if needed.
8. ChatGPT records repo, issue, PR, and workflow evidence and cleans the status report when safe.

## Apply-in to exec handoff

Use this when direct exec request staging is blocked or when the request should be staged as a governed apply-in bundle.

Validated procedure:

1. Build a ChatGPT apply-in ZIP with an `apply_manifest.json` that creates exactly one reviewed request file under `chatgpt_staging/exec_requests/<request_id>.json`.
2. Stage the payload as `chatgpt_staging/in/<apply_request_id>/payload.zip.b64`.
3. Let `chatgpt-apply-in` run and verify its report under `chatgpt_staging/status_reports/chatgpt-apply-in/<apply_request_id>/workflow_report.md`.
4. Read back the new exec request file.
5. Watch for `[skip ci]`: apply-in report commits use `[skip ci]`, so the newly created exec request may not trigger `chatgpt-exec` from that commit.
6. If no exec report appears after the normal wait window, use the GitHub connector `update_file` action on the already-created exec request JSON. Make a tiny metadata-only change such as adding or refreshing `restaged_at_utc`, preserve the exact already-approved command fields, and use a commit message without `[skip ci]`.
7. This GitHub connector `update_file` restage is the validated step that kicked off `chatgpt-exec`; do not assume apply-in alone was enough unless the exec report appears without restage.
8. Verify the exec report under `chatgpt_staging/status_reports/chatgpt-exec/<request_id>/workflow_report.md`.
9. Record evidence and clean status reports only after readback.

Known historical validation example (the command payload used by that run has since been retired):

- apply-in request id: `apply-20260503-exec-hashfix-validation-001`
- exec request id: `exec-20260503-airtable-schema-hashfix-002`
- GitHub connector action that triggered exec: `update_file` on `chatgpt_staging/exec_requests/exec-20260503-airtable-schema-hashfix-002.json`
- metadata-only field used: `restaged_at_utc`
- restage commit: `5fdfe97b6f4296de2048a6330a9f8fb76d2b4a5e`
- exec run id: `25287957928`

## Request sample

Use `operator_tools/github_desktop_lane/manifests/chatgpt_exec_request.sample.json` as the starting shape.

## Environment bridge

The workflow receives secrets as process environment variables. The reusable harness writes them into Machine-scope environment variables in the Windows runner before invoking the command. That lets existing tools keep using the same Machine-scope environment lookup that they use locally.

Only secret names that are explicitly bridged by the workflow body and harness are available to exec requests. Adding a repository secret alone does not automatically expose it to the runner command environment.

The workflow generates runner-local values for `DCOIR_REPO_ROOT`, `DCOIR_DOWNLOADS_DIR`, and `DCOIR_CONFIG_DIR`. Do not use local workstation path values for those inside GitHub Actions.

## Output expectations

Commands should write upload-worthy files under:

```powershell
[Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
```

The harness automatically includes those files in the GitHub Actions artifact.

## Verification wait rule

After ChatGPT stages an exec request, an immediate missing workflow report means "not visible yet," not failure.

Default behavior:

1. Confirm the request commit and file exist.
2. Wait roughly 60-90 seconds before the first no-report conclusion when the runtime allows it.
3. Poll for the workflow report and workflow-generated commit for a bounded window, normally up to about 3-5 minutes.
4. If no report appears, tell the operator the request has not produced a report yet and ask whether to continue checking or inspect Actions manually.
5. Do not call the request failed unless a failure report, failed workflow run, or job log supports that conclusion.

## Failure handling

If the workflow starts and reaches the harness or reporting path, command failures should still produce a status report and sanitized artifact. ChatGPT should inspect:

- `chatgpt_staging/status_reports/chatgpt-exec/<request_id>/workflow_report.md`
- GitHub Actions artifact `chatgpt-exec-<request_id>`
- the Actions run log only if the report or artifact are insufficient

A status report might not appear if the workflow never starts, the push trigger does not fire, Actions are disabled, the workflow YAML is invalid before the job starts, checkout fails before the harness runs, commit permissions fail, or GitHub is delayed. In those cases, use the Actions tab or manually dispatch `chatgpt-exec` with the same `request_path`.

## Run metadata

Workflow reports include run metadata after the report is committed:

- `github_run_id`
- `github_run_attempt`
- `github_sha`
- `github_ref`
- `workflow_run_url`

Use this metadata to retrieve artifacts and job logs when the committed report is not enough.
