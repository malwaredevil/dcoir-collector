# ChatGPT Staging Lane Scenario Matrix

Status: active matrix for `PLAN-20260501-chatgpt-github-staging-lane`.

Action order is ChatGPT first, GitHub second, Supabase ircore state third. ChatGPT initiates and verifies. GitHub performs bounded automation. Supabase ircore preserves durable work-item state, routing, validation, and readback receipts.

## Retention and repo-bloat scenarios

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| Stage-out output has been retrieved | Read needed bundle/files and record evidence, then create cleanup marker with `cleanup_out_bundles=true` and `cleanup_status_reports=true`. | Cleanup removes scoped `out/<request_id>` and consumed reports while preserving scaffolds. | Evidence or Supabase work item note records retrieval before cleanup. |
| Stage-out output has not been retrieved | Do not create cleanup marker for out bundle yet. | Preserve `out/<request_id>` and report. | Supabase work item remains waiting for readback/retrieval. |
| Artifact readback bundle has been retrieved | Read the staged artifact files and manifest, record evidence, then create cleanup marker with `cleanup_out_bundles=true` and `cleanup_status_reports=true`. | Cleanup removes scoped `out/<request_id>` and consumed reports while preserving scaffolds. | Evidence or Supabase work item note records retrieval before cleanup. |
| Apply-in succeeded | Verify target commit/readback and apply report, then clean retained apply/status reports when no longer needed. | Apply-in already deletes inbound payload after success; cleanup can remove reports later. | Supabase work item advances only after readback. |
| Apply-in failed | Read `workflow_report.md` and artifacts if needed; record retry/stop decision before cleanup. | Preserve failure/status evidence until cleanup marker. | Supabase work item stays waiting/blocked until diagnosis is recorded. |
| Cleanup completed | Read cleanup `workflow_report.md`; verify removed and retained paths. Create later cleanup marker if the cleanup report itself is no longer needed. | Cleanup report remains as proof of what was removed. | Evidence records cleanup if material. |
| Validation evidence required | Decide what must be retained and record that reason in Supabase before cleanup. | Preserve intentionally retained files until later explicit cleanup. | Supabase work-item readbacks explain retention. |
| Stale or abandoned artifacts found | Prefer scoped cleanup marker by request id. Avoid broad cleanup unless operator approves. | Cleanup removes only selected surfaces and preserves `.gitkeep`. | Supabase work item note records housekeeping action. |

## Trigger isolation scenarios

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| ChatGPT initiates stage-out by request file | Commit a request under `.github/chatgpt_staging/requests/` with schema `dcoir.chatgpt_staging.stage_out_request.v1`. | Run only on `main` push or manual dispatch; reject missing/wrong schema; write workflow report. | Supabase work item remains active/waiting until output is read. |
| ChatGPT initiates apply-in by payload | Commit `.github/chatgpt_staging/in/<request_id>/payload.zip.b64` with an apply manifest using schema `dcoir.chatgpt_staging.apply_manifest.v1`. | Run only on `main` push or manual dispatch; reject missing/wrong schema; enforce path/hash/workflow mutation rules. | Supabase work item advances only after readback. |
| ChatGPT initiates cleanup by marker | Commit `.github/chatgpt_staging/cleanup_requests/<request_id>.json` with schema `dcoir.chatgpt_staging.cleanup_request.v1`. | Run only on `main` push or manual dispatch; reject missing/wrong schema and malformed booleans. | Cleanup evidence is recorded if material. |
| ChatGPT initiates artifact readback by request file | Commit `.github/chatgpt_staging/requests/github_artifact_readback/<request_id>.json` with schema `dcoir.chatgpt_staging.github_artifact_readback_request.v1`. | Run only on `main` push or manual dispatch; write a request-scoped heartbeat report, download the chosen artifact, extract it into `.github/chatgpt_staging/out/<request_id>/`, and commit a final workflow report plus manifest. | Supabase work item remains active/waiting until extracted output is read and cleanup is recorded. |
| Workflow-generated commit touches trigger path by deletion | No action needed unless report/readback shows a loop. | Commit uses `[skip ci]` so push workflows are skipped. | Supabase work item records loop prevention if validated. |
| Manifest attempts workflow mutation | Only do this on an operator-approved workflow-repair branch or explicitly approved staging-lane workflow repair. | `.github/workflows/` targets require `allow_workflow_changes=true` and non-empty `workflow_change_reason`; otherwise fail closed. | Skill/decision rows should treat workflow mutation as a high-friction branch. |
| Wrong schema or absent schema | Regenerate the request/manifest/marker with the correct schema. | Fail closed and write/retain workflow report where possible. | Supabase work item remains waiting/blocked with trigger/schema failure class. |

## Hash and stale-write scenarios

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| Existing tracked file update | Use stage-out data or direct GitHub readback to include `expected_blob_sha` or `expected_current_sha256` in the apply manifest. | Apply-in verifies the expected current state before copying content. | Supabase work item can advance only after readback confirms the expected file changed. |
| Existing tracked file missing current hash | Regenerate payload with current hash data unless an explicit operator-approved override is intended. | Fail closed and write `workflow_report.md`; commit no unsafe target changes. | Validation case `VAL-20260502-STAGING-HASH-REQUIRED-FOR-EXISTING` should pass. |
| Current hash mismatch | Treat as stale payload; regenerate from current repo state or stop. | Fail closed and report expected vs actual hash where available. | Evidence feeds T3 stale-write validation. |
| New file create-only success | Use `create_only: true` and `expected_new_sha256` for the new path. | Succeeds only if target does not exist and incoming content hash matches. | Evidence confirms new-file creation did not overwrite anything. |
| New file missing create-only or new hash | Regenerate manifest with `create_only: true` and `expected_new_sha256`. | Fail closed and report the missing requirement. | Validation case `VAL-20260502-STAGING-HASH-CREATE-ONLY-NEW` should cover this. |
| Create-only target already exists | Read report and decide whether to convert to tracked update with current hash or choose a new path. | Fail closed; do not overwrite existing file. | Supabase work item remains waiting until retry decision. |
| Existing untracked target | Stop and choose a safer path or manually resolve untracked state. | Fail closed; do not overwrite untracked content. | Supabase readback notes unresolved repo state if material. |
| Explicit missing-current-hash override | Use only with a visible reason and operator-approved risk tradeoff. | May apply, but workflow report lists the override warning. | Validation case `VAL-20260502-STAGING-HASH-OVERRIDE-VISIBLE` proves override is visible. |

## Workflow report scenarios

Scope: ChatGPT-readable workflow success/failure reports and cleanup after ChatGPT reads them.

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| Workflow starts normally | Wait for expected status report, or use GitHub readback if the report does not appear. | Initialize a report target using workflow name plus request id or run id. | Active Supabase work item remains active or waiting. |
| Workflow succeeds | Read `workflow_report.md`; verify result, changed paths, run id, commit/readback clues, and cleanup hint. Create cleanup marker when no longer needed. | Commit one compact Markdown report under `status_reports/<workflow>/<id>/workflow_report.md`. | Supabase readback evidence can record success based on report plus GitHub readback. |
| Workflow fails due to validation or hash mismatch | Decide whether to regenerate request/payload from current source or stop. | Fail closed, write mismatch details in the report, commit no unsafe target changes. | Supabase readback evidence records the failure class and retry or stop decision. |
| Cleanup marker for status report is created | Create cleanup marker only after reading/recording report evidence. | Cleanup removes scoped status report and marker; preserves `.gitkeep` scaffolds. | Evidence records cleanup if material. |

## Stage-out scenarios

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| Stage-out needed | Create `.github/chatgpt_staging/requests/<request_id>.json` with explicit allowed roots and exact paths or bounded search terms. | Detect request, create `out/<request_id>`, write status report, and delete consumed request JSON after success. | Supabase work item remains active/waiting until ChatGPT retrieves output and records evidence. |
| Stage-out succeeds and bundle is needed | Retrieve `manifest.json`, `manifest.md`, `staged_files.zip`, chunks, or copied files as needed. After retrieval, create cleanup marker when safe. | Preserve `out/<request_id>` and status report until cleanup marker appears. | Record readback/evidence before cleanup. |
| Stage-out fails before output | Inspect `status_reports/chatgpt-stage-out/<request_id>/workflow_report.md` and run logs if needed. | Commit small failure report if possible; do not perform unsafe cleanup. | Mark Supabase work item blocked or waiting with failure class. |
| Artifact readback succeeds | Check Gmail `label:GitHub` as an early liveness signal; in connector metadata and returned labels the same mailbox label may appear as `Label_125`, then poll the request-scoped heartbeat report until `result: success` or `failure`, then read `artifact_manifest.md` and the staged files under `.github/chatgpt_staging/out/<request_id>/`, and clean them when safe. | Preserve `out/<request_id>` and `status_reports/chatgpt-github-artifact-readback/<request_id>/` until cleanup marker appears. | Record extracted-artifact readback before cleanup. |

## Apply-in scenarios

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| Apply-in needed | Create `.github/chatgpt_staging/in/<request_id>/payload.zip.b64` with `apply_manifest.json`, allowed roots, hashes, and explicit targets. | Detect payload, decode ZIP, validate manifest, apply changes, write report, commit target changes, and delete inbound payload only after success. | Supabase work item remains active until commit/readback succeeds. |
| Apply-in succeeds | Read success report, verify target file commit/readback, then create cleanup marker if retained reports should be removed. | Commit target file changes, apply report, status report, and payload deletion. | Close or advance Supabase work item only after readback. |
| Apply-in fails | Read failure report and optional artifact pointer; decide retry or repair. | Commit one failure `workflow_report.md`; upload bulky diagnostics as artifact when useful; commit no target changes. | Preserve evidence and failure class before retry. |

## Cleanup scenarios

| Scenario | ChatGPT action | GitHub action | Supabase ircore state |
|---|---|---|---|
| Cleanup marker needed | Create `.github/chatgpt_staging/cleanup_requests/<request_id>.json` only after retrieval/readback. | Detect marker, delete only scoped artifacts, write cleanup report, delete marker after success, preserve scaffolds. | Record cleanup verification if material. |
| Cleanup succeeds | Read cleanup workflow report; verify scoped deletion and retained scaffolds. | Commit cleanup changes and one cleanup `workflow_report.md`. | Validation case can pass after readback confirms no collateral deletion. |
| Cleanup marker malformed | Fix/recreate marker. | Fail closed, delete nothing, write failure report if possible. | Mark cleanup blocked if it affects active plan. |

## Cleanup marker schema

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
