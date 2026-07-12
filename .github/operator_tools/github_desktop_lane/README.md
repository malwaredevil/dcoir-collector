# DCOIR GitHub Desktop Lane Tools

Reusable operator-side helper tools for AFRICOM_SOC_IR / DCOIR manual GitHub Desktop workflows.

## Authority model

- GitHub repo is the source of truth for tool code, operator guidance, and governed discovery for this lane.
- `tool_catalog.json` is the repo-side machine-readable discovery catalog for these tools.
- The DCOIR GitHub Desktop Lane Advisor skill selects tools and generates launcher commands from repo-governed sources.
- The operator runs these scripts locally in PowerShell and uploads logs or ZIP outputs when a local lane is required.
- ChatGPT connector apply-in work uses the repo-side single-payload contract under `.github/chatgpt_staging/in/README.md`.

## ChatGPT apply-in single-payload rule

For `chatgpt-apply-in`, use exactly one file:

```text
.github/chatgpt_staging/in/<request_id>/payload.zip.b64
```

Do not use `payload.zip.b64.parts/`, `part-*.b64`, chunk manifests, or any chunk marker. If a payload is too large, reduce the batch size and rebuild one smaller `payload.zip.b64`.

Preferred builder/validator:

```text
.github/scripts/chatgpt_apply_in/build_payload_zip_b64.py
```

That helper builds one ZIP with root `apply_manifest.json` and `files/`, encodes it to `payload.zip.b64`, and validates ZIP open, manifest shape, request id, no truncation marker, no chunk artifacts, and base64 round trip.

## Operator guide

Use [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) as the wiki/operator runbook for this tool lane. It covers tool selection, normal run flow, CAP logging expectations, GitHub Desktop bundle application, safety stop conditions, evidence to preserve, and the maintainer checklist.

Keep this README as the landing page, `tool_catalog.json` as the machine-readable repo catalog, and `modules/README.md` as the module role index and linked discovery surface for this lane.

## Safety defaults

These tools favor read-only diagnostics, fast-forward-only pulls, explicit manifests, local logs, and stop-on-unsafe-state behavior. Do not use destructive git commands such as `git reset --hard`, `git clean`, or `git stash pop` unless a purpose-specific recovery plan calls for them.

GitHub Actions terminology used by this toolset:

- `workflow`: the YAML automation definition under `.github/workflows/`.
- `workflow run`: one execution of a workflow.
- `job`: an execution unit inside a workflow run.

GitHub Actions allows multiple workflow runs by default, but a workflow or job may define a `concurrency` group. In a concurrency group, GitHub allows at most one running and one pending workflow run or job at a time. The orchestrator therefore uses `max_parallel` only as a local dispatch throttle; GitHub runner availability and workflow-level concurrency still decide actual execution order.

## Reusable module architecture

The toolset is split into reusable modules under `modules/`:

| Module | Purpose | Validation status |
|---|---|---|
| `Dcoir.Common` | Paths, Machine/System environment validation, placeholder rejection, JSON, UTF-8 filesystem helpers, safe names, timestamps, and shared logging context. | Shared baseline module. |
| `Dcoir.Git` | Self-contained git-lane helpers: Machine/System env lookup, placeholder rejection, UTF-8 logging, git executable discovery, native argument quoting, logged git process execution, branch checks, clean-tree checks, fetch, fast-forward pull, and ahead/behind analysis. | Validated by git diagnostic, safe pre-pull, snapshot, and repo patch apply tools. |
| `Dcoir.GitHub` | GitHub CLI auth/availability, `gh` text/JSON wrappers, Actions run lookup, run details, and job lookup. | Validated through Actions orchestrator gates. |
| `Dcoir.Packaging` | ChatGPT-friendly ZIP packaging wrapper. | Validated through Actions and snapshot ZIP generation. |
| `Dcoir.Actions` | Manifest parsing, dispatch, monitor, fail-fast gates, parallel workflow execution throttle, capture, cleanup, summaries, and exit codes. | Preferred Actions orchestrator lane. |
| `Dcoir.Snapshot` | Repo-relative path safety, safe names, path normalization, under-root checks, text-file filtering, binary sniffing, targeted staging, and UTF-8 logging. | Validated by text-only and targeted snapshot smoke tests. |
| `Dcoir.RepoPatch` | Repo patch path safety, payload-root resolution, allowed target roots, hashing, and UTF-8 logging. | Validated by WhatIfOnly and real fixture apply smoke tests. |
| `DcoirActionsOrchestrator` | Compatibility facade preserving the stable public entrypoint. | Preserves existing public entrypoint. |

Harnesses and wrappers should only create reviewed JSON configuration and execute the orchestrator or module-owned engine. Shared functions used by two or more tools should move into the reusable module ecosystem. Git-facing scripts should use `Dcoir.Git`; snapshot scripts should use `Dcoir.Snapshot`; repo patch/apply scripts should use `Dcoir.RepoPatch`.

## Environment variables

DCOIR operator tools resolve local configuration from **Machine/System** environment variables:

```powershell
[Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
[Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
```

`DCOIR_REPO_ROOT` should point to the local `dcoir-collector` repository root. `DCOIR_DOWNLOADS_DIR` should point to the folder where logs and ZIP outputs should be written.

Operator tools reject placeholder paths such as `C:\path\to\dcoir-collector` and should not trust process-scoped placeholder values from a polluted terminal session. Generated ChatGPT codeblocks for local tools should use the documented canonical environment variable names, maximize Machine/System environment variables, fail fast on missing variables, and never print secret values.

## Tools

| Tool | Purpose | Backing modules |
|---|---|---|
| `.github/scripts/chatgpt_apply_in/build_payload_zip_b64.py` | Build and validate one single-file `chatgpt-apply-in` `payload.zip.b64`; no chunks/parts supported. | Python stdlib |
| `scripts/Get-DcoirGitConflictDiagnostic.ps1` | Capture local git/GitHub Desktop conflict state to a timestamped log. | `Dcoir.Git` |
| `scripts/Invoke-DcoirSafePrePullApply.ps1` | Stash current local work, fast-forward pull, reapply only a newly-created captured stash, and log the result. | `Dcoir.Git` |
| `scripts/New-DcoirTargetedSnapshot.ps1` | Build a targeted snapshot ZIP from a JSON manifest after safe repo freshness checks. | `Dcoir.Git`, `Dcoir.Snapshot`, ZIP helper |
| `scripts/New-DcoirTextOnlyRepoSnapshot.ps1` | Build a read-only full-repo text snapshot ZIP for ChatGPT review while excluding binaries, generated/dependency folders, and oversized files. | `Dcoir.Git`, `Dcoir.Snapshot`, ZIP helper |
| `scripts/Invoke-DcoirRepoPatchApply.ps1` | Apply an explicit repo-relative payload manifest with wrapper-root detection, target-root allow-listing, optional pre/post hashes, delete support, and UTF-8 verification logs. | `Dcoir.Git`, `Dcoir.RepoPatch` |
| `scripts/New-DcoirChatGPTFriendlyZip.ps1` | Build rootless, metadata-clean, UTF-8-friendly ZIPs for ChatGPT upload and parsing, including diagnostic indexes and file manifests. | ZIP helper |
| `scripts/Invoke-DcoirActionsWorkflowOrchestrator.ps1` | Watch, capture, or dispatch GitHub Actions workflow runs from a manifest, monitor them, collect evidence, and produce a ChatGPT-friendly ZIP. | `Dcoir.Actions`, `Dcoir.GitHub`, `Dcoir.Packaging`, `Dcoir.Common` |
| `scripts/Invoke-DcoirActionsValidationSmoke.ps1` | Harness that creates guarded smoke manifests and executes the orchestrator. | `Dcoir.Common`, Actions orchestrator |
| `scripts/Invoke-DcoirActionsModeLadder.ps1` | Harness that creates a fail-fast sequential ladder manifest and executes the orchestrator. | `Dcoir.Common`, Actions orchestrator |

## ChatGPT-friendly ZIP launcher

Use this shared helper when a diagnostic or snapshot tool needs to create an upload ZIP that is fast for ChatGPT to unzip, triage, and parse.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:DCOIR_REPO_ROOT\operator_tools\github_desktop_lane\scripts\New-DcoirChatGPTFriendlyZip.ps1" -SourceFolder "$env:DCOIR_DOWNLOADS_DIR\some_diagnostic_folder" -OutputZip "$env:DCOIR_DOWNLOADS_DIR\some_diagnostic_folder.chatgpt.zip" -NormalizeTextEncoding
```

The helper skips hidden/system metadata, avoids wrapper-root junk, writes archive entries with forward slashes, places `diagnostic_index.md`, `captured_files.json`, and `zip_manifest.json` first for fast triage, and can normalize staged text copies to UTF-8 without modifying original files.

## Actions workflow orchestrator launchers

Dry-run dispatch using the bundled sample manifest:

```powershell
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
$script = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\Invoke-DcoirActionsWorkflowOrchestrator.ps1'
$manifest = Join-Path $repo 'operator_tools\github_desktop_lane\manifests\actions_workflow_orchestrator.dispatch.sample.json'
& $script -ManifestJson $manifest
```

Watch latest runs without dispatching:

```powershell
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
$script = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\Invoke-DcoirActionsWorkflowOrchestrator.ps1'
$manifest = Join-Path $repo 'operator_tools\github_desktop_lane\manifests\actions_workflow_orchestrator.watch.sample.json'
& $script -ManifestJson $manifest
```

Live dispatch must use a copied manifest in `DCOIR_DOWNLOADS_DIR`, not the repo sample. Live dispatch defaults to one workflow run only and preserves dispatched run state after GitHub returns a run ID:

```powershell
$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
$script = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\Invoke-DcoirActionsWorkflowOrchestrator.ps1'
$manifest = Join-Path $downloads 'dcoir_actions_live_dispatch_test.json'
& $script -ManifestJson $manifest -ConfirmDispatch
```

Live-dispatch manifest safety fields:

```json
{
  "dry_run": false,
  "require_dispatch_confirmation": true,
  "allow_multiple_live_dispatches": false,
  "max_dispatch_count": 1,
  "max_parallel": 1
}
```

Set `allow_multiple_live_dispatches=true` only after reviewing the plan and intentionally approving a batch of multiple workflow runs.

## Manifest examples

- Repo patch/apply: `manifests/repo_patch_apply.sample.json`
- Actions orchestrator dispatch: `manifests/actions_workflow_orchestrator.dispatch.sample.json`
- Actions orchestrator watch: `manifests/actions_workflow_orchestrator.watch.sample.json`

### Set-and-forget live validation note

For unattended live validation, use a manifest with `require_dispatch_confirmation=false`, `allow_multiple_live_dispatches=false`, and `max_dispatch_count=1` only after the manifest has been reviewed. The safer default remains `require_dispatch_confirmation=true` for first-run live testing.
