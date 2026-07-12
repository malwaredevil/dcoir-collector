# ChatGPT GitHub Staging Lane Safety Contract

Status: active safety and operations contract for `PLAN-20260501-chatgpt-github-staging-lane`.

This folder supports the ChatGPT GitHub staging lane: a controlled path for large-file readback, stage-out bundles, reviewed apply-in bundles, cleanup markers, workflow status reports, and bounded artifact extraction when normal connector edits or readback are too small, fragile, or cumbersome.

## New-session rule

When a session sees staging-lane, cleanup, failure-report, workflow-report, large-file readback, artifact extraction, or batch-apply work:

1. Read the live GitHub issue or PR, then read the matching Supabase ircore work-item context when governed work is in scope.
2. Consult Supabase ircore routing, workflow catalog, validation rules, and reusable lessons for the staging-lane scenario.
3. Read this file and `.github/chatgpt_staging/SCENARIO_MATRIX.md` from GitHub when repo-source behavior is in scope.
4. Read `.github/operator_tools/github_desktop_lane/docs/CHATGPT_STAGING_LANE_OPERATOR_GUIDE.md` before giving operator-facing CAP or troubleshooting instructions.
5. Check `.github/chatgpt_staging/status_reports/` before asking the operator for screenshots, copied logs, uploaded logs, or a commit SHA.
6. Check `.github/chatgpt_staging/failure_reports/` before retrying an old request id.
7. Check `.github/chatgpt_staging/cleanup_requests/` before assuming cleanup was requested or completed.
8. Never claim cleanup, retry safety, or production readiness without GitHub readback and Supabase work-item evidence.

## Production safety principles

1. Narrow by default. Each request or apply manifest must explicitly list the roots it may read or write.
2. No broad root writes. Manifests must not allow the repository root, empty strings, `.`, or wildcard-style broad coverage.
3. No path traversal. Absolute paths, drive-letter paths, parent segments, and root escapes are prohibited.
4. No secrets. Payloads must not include API keys, tokens, credentials, `.env` files, private config values, or secret-bearing logs.
5. No workflow mutation through apply-in, ever. `.github/workflows/*` targets are always reverted before commit by `reusable-chatgpt-apply-in.yml`, even when a manifest sets `allow_workflow_changes: true`, because GitHub's default `GITHUB_TOKEN` cannot push workflow-file changes regardless of granted permissions. Workflow-file changes must go through a normal branch/PR reviewed by a human or agent with push access, never through this bot.
6. No stale overwrites. Apply-in must use current-source hash checks or blob SHA checks for existing files whenever overwriting tracked content.
7. No repo bloat. Payloads, ZIPs, extracted work folders, generated logs, output bundles, status reports, and failure reports must be cleaned or explicitly retained as validation evidence.
8. Evidence before readiness. The lane cannot be called production-ready until blocked-path, hash-mismatch, cleanup, workflow-report, retention, operator-instruction, and happy-path validation all pass.

## Operator-facing rule

When talking to the operator, keep staging-lane instructions plain:

- explain what the bundle/request/payload is for
- give one suggested commit summary
- after CAP, use GitHub readback and workflow reports before asking for logs or a SHA
- recommend the next step after status updates
- use the operator guide for CAP wording and troubleshooting expectations

## Apply-in hash and stale-write policy

Apply-in must fail closed unless the manifest proves it is acting on the intended source state.

For every file entry:

- Existing tracked files require `expected_blob_sha` or `expected_current_sha256`.
- New files require `create_only: true` and `expected_new_sha256`.
- `create_only: true` fails if the target path already exists.
- Existing untracked files must not be overwritten.
- `expected_new_sha256` must match the incoming file content whenever provided, and it is mandatory for new files.
- A manifest-level `allow_missing_current_hash: true` may bypass the current-hash requirement for existing tracked files only as an explicit exception. If used, the workflow report must make the override visible.

ChatGPT should prefer stage-out manifest data when preparing apply-in payloads, because stage-out records blob SHA and sha256 values for the current repo state.

## Trigger isolation and schema policy

The staging workflows keep narrow `push` triggers so ChatGPT can initiate work by committing a request, payload, or cleanup marker. To reduce accidental or recursive runs:

- push triggers are limited to `main` and only these paths:
  - `.github/chatgpt_staging/requests/*.json` for stage-out
  - `.github/chatgpt_staging/requests/github_artifact_readback/*.json` for artifact readback
  - `.github/chatgpt_staging/in/*/payload.zip.b64` for apply-in
  - `.github/chatgpt_staging/cleanup_requests/*.json` for cleanup
- workflow-generated commits use GitHub-recognized `[skip ci]` so cleanup/output/report commits do not retrigger push workflows unnecessarily
- stage-out request files require `schema: dcoir.chatgpt_staging.stage_out_request.v1`
- artifact-readback request files require `schema: dcoir.chatgpt_staging.github_artifact_readback_request.v1`
- apply manifests require `schema: dcoir.chatgpt_staging.apply_manifest.v1`
- cleanup markers require `schema: dcoir.chatgpt_staging.cleanup_request.v1`
- `.github/workflows/` targets require `allow_workflow_changes: true` and `workflow_change_reason` in the apply manifest to pass manifest validation, but the file is still reverted before commit and never actually lands (see "No workflow mutation" above); the workflow report notes this explicitly when it happens

Example stage-out request:

```json
{
  "schema": "dcoir.chatgpt_staging.stage_out_request.v1",
  "request_id": "example-request",
  "allowed_roots": ["chatgpt_staging"],
  "exact_paths": [".github/chatgpt_staging/README.md"]
}
```

Example artifact-readback request:

```json
{
  "schema": "dcoir.chatgpt_staging.github_artifact_readback_request.v1",
  "request_id": "example-artifact-readback",
  "source_run_id": "1234567890",
  "artifact_name": "artifact-name"
}
```

Example apply manifest fields:

```json
{
  "schema": "dcoir.chatgpt_staging.apply_manifest.v1",
  "request_id": "example-apply",
  "allowed_roots": ["chatgpt_staging"],
  "files": []
}
```

## Retention and repo-bloat policy

Default posture:

- keep stage-out bundles only until ChatGPT retrieves the needed files or records evidence
- keep extracted artifact readback bundles only until ChatGPT retrieves the needed files or records evidence
- delete inbound apply payloads after successful apply/commit/push unless explicit validation evidence requires temporary retention
- keep status reports only until ChatGPT reads them and records any needed Supabase work-item evidence
- keep failure evidence until the failure is diagnosed and retry/stop decision is recorded
- keep GitHub Actions artifacts for short-lived diagnostics only; current workflow retention is 7 days where configured
- never delete `.gitkeep` scaffolds
- use cleanup markers for scoped cleanup when ChatGPT has already consumed a specific request id and wants bounded immediate removal
- scheduled `chatgpt-report-retention-cleanup` is the automatic fallback cleanup owner for stale status reports, stale staged request JSON files, and aged staged output bundles
- cleanup requests may target top-level stage-out requests and nested request families such as `.github/chatgpt_staging/requests/github_artifact_readback/`

A cleanup run may leave its own final `chatgpt-staging-cleanup/.../workflow_report.md` as proof of what was removed. That report should be cleaned by a later cleanup marker after ChatGPT reads and records it.

## Folder roles

```text
.github/chatgpt_staging/
  requests/          # ChatGPT-created stage-out requests and artifact-readback requests
  exec_requests/     # ChatGPT-created execution requests for chatgpt-exec live heartbeat runs
  exec_payloads/     # request-scoped execution payloads retained only while needed for diagnosis or evidence
  in/                # ChatGPT-created apply-in payloads
  out/               # GitHub-created stage-out bundles and artifact readback bundles retained until scoped or retention cleanup
  work/              # transient workflow work area; never intentionally committed
  apply_reports/     # apply-in reports when retained
  failure_reports/   # legacy/special failure locators; use status_reports for new workflow result reports
  status_reports/    # one committed workflow_report.md per workflow result
  cleanup_requests/  # ChatGPT-created cleanup markers
```

## Workflow status report contract

Staging workflows should write exactly one committed Markdown report per workflow result:

```text
.github/chatgpt_staging/status_reports/<workflow-name>/<request-id-or-run-id>/workflow_report.md
```

Do not create paired JSON and Markdown reports for the same result. If additional evidence is required, use a GitHub Actions artifact and include the artifact name/run id inside `workflow_report.md`.

A useful report includes:

- workflow name, result, phase, run id, ref, triggering SHA, and request id when available
- request path, payload path, output path, or cleanup marker path when relevant
- changed, applied, removed, retained, or skipped paths
- failure phase and bounded troubleshooting context
- hash mismatch, unsafe path, malformed marker, stale-write, create_only, or validation details when relevant
- artifact pointer only when large raw diagnostics are needed
- cleanup guidance and next ChatGPT action

ChatGPT should read this report before asking the operator for screenshots, pasted logs, uploaded logs, or a commit SHA.

## Cleanup marker schema

Create cleanup markers only after ChatGPT has read or recorded needed output and reports.

```json
{
  "schema": "dcoir.chatgpt_staging.cleanup_request.v1",
  "request_id": "request-id",
  "cleanup_requests": true,
  "cleanup_in_payloads": true,
  "cleanup_out_bundles": true,
  "cleanup_apply_reports": false,
  "cleanup_failure_reports": false,
  "cleanup_status_reports": true,
  "delete_marker_after_success": true,
  "reason": "ChatGPT consumed the needed report/output and recorded evidence."
}
```

All cleanup booleans must be explicit when ChatGPT creates a marker. GitHub must fail closed if a marker is malformed.

## Stop conditions

Stop and ask for operator guidance if:

- a request or manifest needs a broad repo root
- a workflow file needs to be changed at all (apply-in never lands `.github/workflows/*` changes; use a normal branch/PR instead)
- a payload contains secrets or suspected secrets
- source hash checks fail
- cleanup would delete scaffold or unrelated files
- workflow report creation fails repeatedly and no readable evidence is available
- GitHub Actions behavior differs from this contract
