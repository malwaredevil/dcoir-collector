# Ops Apply Patch Requests

Stage exactly one request directory per apply operation:

```text
.github/ops/requests/apply_patch/<request_id>/request.json
.github/ops/requests/apply_patch/<request_id>/change.patch
```

`<request_id>` may contain only letters, numbers, dots, underscores, and hyphens.
The workflow only looks for requests under `.github/ops/requests/apply_patch/<request_id>/`.
This is the **Ops apply-patch** lane. It is not `chatgpt-apply-in`, does not read
`.github/chatgpt_staging/apply_in` payloads, and does not process full-file replacement
ZIPs.

This lane is for connector-staged patch requests, not connector-staged full-file
replacement payloads. To use it through the GitHub connector, create both
`request.json` and the referenced `.patch` or `.diff` file on the default branch
under one request directory. The entry workflow has two paths:

- a push to `main` touching `.github/ops/requests/apply_patch/**`, when GitHub emits a
  usable push event for the writer; or
- a manual `workflow_dispatch` with `request_path` set to the request JSON.

There is no automatic scheduled scanner. If a connector-created commit does not
produce a visible `64 Ops - Apply Patch Request` run, an `ops-apply-patch-*`
artifact, or a target-branch commit within the normal Actions startup window,
do not assume the request will be picked up later. Manually dispatch this
workflow with the exact `request_path`, or use an approved `chatgpt-exec` request
to run `python .github/ops/tools/apply_patch_request.py apply --repo . --request <path>`.
That exec fallback still uses the same apply-patch validation script; it is not
`chatgpt-apply-in`.

When staging through a tool that cannot atomically create both files, prefer one
of these patterns:

1. Stage the patch and request together by a single git commit from a real
   checkout, then let the push trigger run.
2. Stage both files through the connector, then manually dispatch with
   `request_path` after confirming both files exist on `main`.
3. Stage both files through the connector, then run the approved exec fallback
   above if manual dispatch is unavailable.

Avoid relying on a patch-only push as the apply signal. A `.patch`/`.diff` file
without the same-directory `request.json` is an incomplete request and may fail
or be skipped depending on how the push event is resolved.

The workflow does not scan arbitrary staging folders and does not ingest
replacement files. `.patch` and `.diff` describe the patch file format only; the
request schema decides whether the patch is a v1 single-file patch or a v2
multi-file patch set.

## Implementation Surfaces

The apply-patch lane follows the repo workflow/module/script pattern:

- Entry workflow: `.github/workflows/ops-apply-patch.yml`
- Reusable workflow: `.github/workflows/reusable-ops-apply-patch.yml`
- Patch validation/apply script: `.github/ops/tools/apply_patch_request.py`
- Request lookup folder: `.github/ops/requests/apply_patch/<request_id>/`

The workflow and reusable workflow are tracked in the GitHub workflow inventory
and modularization contract under the `ops-apply-patch` family.

## Request Schema: v1 Single File

```json
{
  "schema": "dcoir.ops.apply_patch_request.v1",
  "request_id": "example-request",
  "mode": "apply",
  "target_branch": "feature/example-branch",
  "target_path": "project_sources/example/large-file.txt",
  "allowed_roots": ["project_sources/example"],
  "patch_path": ".github/ops/requests/apply_patch/example-request/change.patch",
  "expected_patch_sha256": "<sha256 of change.patch>",
  "expected_target_blob_sha": "<current git blob sha on target branch>",
  "expected_current_sha256": "<current file sha256 on target branch>",
  "expected_new_sha256": "<optional expected file sha256 after patch>",
  "commit_message": "Apply reviewed ops patch example-request"
}
```

Use `mode: "dry-run"` to validate and run `git apply --check` without committing.
The v1 lane accepts only one text patch for one existing tracked file. It rejects
multi-file patches, binary patches, renames, copies, deletes, mode changes,
unsafe paths, missing stale-base hashes, and unexpected changed paths.

## Request Schema: v2 Patch Set

```json
{
  "schema": "dcoir.ops.apply_patch_request.v2",
  "request_id": "example-patch-set",
  "mode": "patch-set",
  "operation": "apply",
  "target_branch": "feature/example-branch",
  "patch_path": ".github/ops/requests/apply_patch/example-patch-set/change.diff",
  "expected_patch_sha256": "<sha256 of change.diff>",
  "targets": [
    {
      "path": "project_sources/example/first.txt",
      "allowed_roots": ["project_sources/example"],
      "expected_target_blob_sha": "<current git blob sha on target branch>",
      "expected_current_sha256": "<current file sha256 on target branch>",
      "expected_new_sha256": "<optional expected file sha256 after patch>"
    },
    {
      "path": "project_sources/example/second.txt",
      "allowed_roots": ["project_sources/example"],
      "expected_target_blob_sha": "<current git blob sha on target branch>",
      "expected_current_sha256": "<current file sha256 on target branch>",
      "expected_new_sha256": "<optional expected file sha256 after patch>"
    }
  ],
  "commit_message": "Apply reviewed ops patch set example-patch-set"
}
```

Use `operation: "dry-run"` to validate and run `git apply --check` without
committing. The v2 lane initially supports multi-file text-only unified diffs for
existing tracked files. It still rejects creates, deletes, renames, copies, mode
changes, binary patches, unsafe paths, missing stale-base hashes, and unexpected
changed paths. All validated file changes are committed together.

For v2, every target carries its own `path`, stale-base hash, optional expected
new hash, and `allowed_roots`. The patch paths must exactly match the `targets[]`
paths. The report artifact includes an apply plan with files touched, operation
type, root policy result, workflow policy result, and stale-base result.

Compute `expected_patch_sha256` from the patch file bytes as they exist in the
Git checkout that will run `.github/ops/tools/apply_patch_request.py`. If the request is
staged through an API or connector, read the staged `.patch` or `.diff` file back
from GitHub first and hash that content; local pre-staging hashes can differ when
Git normalizes line endings.

The patch file must be a valid unified diff. Context lines, including
blank context lines inside a hunk must still begin with a single space;
added lines begin with `+` and removed lines begin with `-`. A patch can
pass checksum validation but still fail `git apply --check` as corrupt
when a staged hunk contains bare empty lines instead of space-prefixed
blank context lines.

Default-branch writes are blocked unless the request sets `allow_default_branch: true`
and includes a non-empty `default_branch_reason`.

Workflow-file targets are blocked unless the request sets
`allow_workflow_changes: true` and includes a non-empty
`workflow_change_reason`.

Creates, deletes, renames, copies, and mode changes should be added later only
behind explicit per-operation approval flags and focused tests.

## Cleanup Lifecycle

Request files are staging inputs, not durable repo records.

- Successful v1 `mode: "apply"` and v2 `operation: "apply"` runs upload the
  report artifact first, then remove `.github/ops/requests/apply_patch/<request_id>/`
  from the branch that staged the request using a `[skip ci]` cleanup commit.
- Before deletion, cleanup hashes the current staged request directory and
  compares it with the triggering request input. If the directory changed, such
  as from a reused request id, cleanup refuses deletion and leaves the current
  request files for review.
- Failed apply runs leave the request directory in place so the operator can
  inspect and fix the request.
- Successful dry-run requests leave the request directory in place because no
  target-branch change was implemented.
- Report files are uploaded as GitHub Actions artifacts, not committed under the
  repo tree. The workflow uses 14-day artifact retention for the apply report.
- If a cleanup-only deletion push is evaluated by the workflow trigger, the
  reusable workflow treats it as a no-op cleanup run instead of failing because
  the deleted `request.json` is no longer present.
