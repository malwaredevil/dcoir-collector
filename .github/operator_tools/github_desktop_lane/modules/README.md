# DCOIR GitHub Desktop Lane PowerShell Modules

This folder contains reusable PowerShell module building blocks for DCOIR operator-side tools.

## Default logging contract

`Dcoir.Logging` is the default logging module for DCOIR operator-run PowerShell tools and generated local-execution codeblocks.

Any tool that performs local execution, repo update staging, diagnostics, validation, capture, export, packaging, or workflow orchestration must produce one uploadable log or diagnostic file by default unless an explicit exception is documented.

Default pattern:

```powershell
$module = Join-Path $toolRoot 'modules\Dcoir.Logging\Dcoir.Logging.psm1'
Import-Module $module -Force
Initialize-DcoirToolLog -ToolName 'my_tool' -ToolVersion 'YYYY-MM-DD.N' -LogPath $LogPath
```

During execution, tools should use:

```powershell
Set-DcoirLogPhase -Phase 'phase-name'
Write-DcoirLogLine -Message 'operator-visible status'
Write-DcoirLogObject -Label 'context' -Object $safeContext
```

Catch blocks should use:

```powershell
$result = Write-DcoirCaughtError -ErrorRecord $_ -NextAction 'Upload the log_path file to ChatGPT.'
```

The returned tool output should include `log_path` on success and failure. Operators should upload that single file instead of relying on screenshots.

Logs must not print secret environment values. Log variable presence, source, safe paths, phases, hashes, error type, stack trace, and next action.

## Module roles

| Module | Role |
|---|---|
| `Dcoir.Logging` | Default operator-tool logging contract: one uploadable log file, phase tracking, terminal-relevant status, safe object logging, error type, stack trace, and next action. |
| `Dcoir.Common` | Environment/path resolution, placeholder rejection, JSON conversion, UTF-8 file writes, timestamped console/log output, safe names, and shared run context. |
| `Dcoir.Git` | Git executable discovery, native argument quoting, logged git execution, branch/status checks, clean-tree checks, fetch, fast-forward pull, stash-safe support, and ahead/behind analysis. |
| `Dcoir.Snapshot` | Repo-relative path safety, safe names, path normalization, under-root checks, text-file filtering, binary sniffing, targeted staging, and UTF-8 snapshot logging. |
| `Dcoir.RepoPatch` | Repo patch path safety, payload-root resolution, wrapper-root stripping, allowed target roots, copy/delete planning, hashing, UTF-8 verification, and apply logging. |
| `Dcoir.GitHub` | GitHub CLI availability, `gh api` JSON/text wrappers, Actions workflow run lookup, run lookup, and job lookup. |
| `Dcoir.Packaging` | ChatGPT-friendly ZIP invocation and reusable packaging entrypoints. |
| `Dcoir.Actions` | Manifest parsing, dispatch guardrails, workflow dispatch, monitoring, fail-fast gates, evidence capture, summaries, cleanup, and exit codes. |
| `DcoirActionsOrchestrator` | Compatibility facade preserving the existing public orchestrator entrypoint. |

## Harness boundary

Harness scripts should only create reviewed JSON configuration and execute the orchestrator or module-owned engine. Shared patterns used by multiple tools belong in these modules rather than inside wrappers.

Logging is a shared pattern. Do not create new ad hoc logging helpers when `Dcoir.Logging` can be imported.

## Compatibility

The modules target Windows PowerShell 5.1 and PowerShell 7. Avoid syntax that requires newer runtimes unless the wrapper explicitly gates for it.

## Documentation surfaces

- Parent README: `.github/operator_tools/github_desktop_lane/README.md`
- Operator guide: `.github/operator_tools/github_desktop_lane/docs/OPERATOR_GUIDE.md`
- Logging standard: `.github/operator_tools/github_desktop_lane/docs/OPERATOR_TOOL_LOGGING_STANDARD.md`
- Machine-readable catalog: `.github/operator_tools/github_desktop_lane/tool_catalog.json`
- Logging policy: `.github/operator_tools/github_desktop_lane/tool_catalog_operator_logging_policy.json`
