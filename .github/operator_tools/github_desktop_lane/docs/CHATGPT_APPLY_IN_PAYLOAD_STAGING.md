# ChatGPT Apply-In Payload Staging

## Purpose

`New-DcoirApplyInPayload.ps1` prepares a local ChatGPT apply-in ZIP payload for the `chatgpt-apply-in` GitHub Actions workflow.

This helper remains the preferred local validation path when the operator is using GitHub Desktop or local git. Connector staging of `.github/chatgpt_staging/in/<request_id>/payload.zip.b64` is also allowed when the operator explicitly authorizes it and ChatGPT can validate the ZIP/base64 round trip before writing.

## Background

A live test on 2026-05-03 staged `.github/chatgpt_staging/in/airtable-export-policy-20260503/payload.zip.b64` through a long inline write. The `chatgpt-apply-in` workflow run `25280175341` failed in the `Decode ZIP payload and apply bundle` step with:

```text
base64: invalid input
```

Readback showed the staged payload contained a literal truncation marker:

```text
ERROR TRUNCATED
```

That failure means the payload file was corrupted before the workflow executed. It is a historical caution, not a standing ban on connector staging. Current practice is: validate locally/in-session, stage through the safest available lane, and verify workflow/readback after push.

## Tool

```text
.github/operator_tools/github_desktop_lane/scripts/New-DcoirApplyInPayload.ps1
```

## Logging requirement

This tool imports `.github/operator_tools/github_desktop_lane/modules/Dcoir.Logging/Dcoir.Logging.psm1` and writes a single uploadable log file on success or failure.

The log path is returned in JSON output as `log_path`. Upload that file instead of relying on screenshots.

## Input contract

The input ZIP must contain `apply_manifest.json` at archive root.

The helper:

- resolves `DCOIR_REPO_ROOT` from Machine/System environment when `-RepoRoot` is omitted;
- writes the payload to `.github/chatgpt_staging/in/<request_id>/payload.zip.b64`;
- writes `payload_staging_report.json` next to it;
- rejects unsafe request IDs;
- rejects payload text containing `ERROR TRUNCATED`;
- decodes the written base64 back to a temporary ZIP;
- verifies SHA256 round-trip equality;
- verifies the decoded ZIP still contains `apply_manifest.json`;
- logs resolved paths, phases, hashes, error type, stack trace, and next action.

## Launcher

```powershell
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
$script = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\New-DcoirApplyInPayload.ps1'
$payload = Join-Path ([Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')) 'payload.zip'
& $script -PayloadZip $payload -RequestId 'my-request-id'
```

Then review and commit the two staged files:

```text
.github/chatgpt_staging/in/<request_id>/payload.zip.b64
.github/chatgpt_staging/in/<request_id>/payload_staging_report.json
```

Pushing `payload.zip.b64` under `.github/chatgpt_staging/in/<request_id>/` triggers the `chatgpt-apply-in` workflow. You may also use workflow dispatch with the same repo-relative payload path.

## Connector staging rule

When the operator authorizes connector staging, ChatGPT may create or update `.github/chatgpt_staging/in/<request_id>/payload.zip.b64` directly through the connector after validating: ZIP opens; `apply_manifest.json` exists at archive root; base64 round trip matches the source ZIP SHA256; request id is safe; and staged content does not contain truncation markers. If the full payload is too large or fails, retry with smaller bounded payloads such as half the skill set or a one-skill test payload.

## Failure triage

If local staging fails, upload the returned `log_path` file.

If `chatgpt-apply-in` fails after push, inspect:

```text
.github/chatgpt_staging/status_reports/chatgpt-apply-in/<request_id>/workflow_report.md
```

Then inspect the GitHub Actions job log and failure artifact named like:

```text
chatgpt-apply-in-failure-<run_id>
```

The committed report gives the run id, artifact name, payload path, request id, and next action. The job log usually contains the exact failed command.
