# DCOIR GitHub Desktop Lane Operator Guide

This guide is the operator-facing wiki page for the GitHub Desktop lane tools and modules. It explains which tool to use, how to run it safely, what evidence to keep, and how to CAP a repo-update bundle after review.

## Authority model

- GitHub `.github/operator_tools/github_desktop_lane/` is the source of truth for reusable operator-side tool code and documentation.
- `tool_catalog.json` is the repo-side machine-readable catalog for this tool lane.
- `README.md` is the landing page. This guide is the operator runbook. `modules/README.md` documents reusable module roles.
- The DCOIR GitHub Desktop Lane Advisor skill should select tools from repo-governed docs and catalog surfaces instead of inventing one-off scripts.

## Environment readiness

Set these as Machine/System environment variables before running tools:

```powershell
[Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
[Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
```

Expected values:

- `DCOIR_REPO_ROOT`: local path to the `dcoir-collector` repository root.
- `DCOIR_DOWNLOADS_DIR`: local folder where logs, snapshots, and upload ZIPs should be written.

Stop if either variable is missing, points at a placeholder such as `C:\path\to\dcoir-collector`, or points at the wrong repo/download folder.

## Tool selector

| Operator need | Use this tool | Main output |
|---|---|---|
| Diagnose GitHub Desktop, local branch, pull, conflict, stash, or ahead/behind confusion. | `scripts/Get-DcoirGitConflictDiagnostic.ps1` | `dcoir_git_conflict_diagnostic_*.txt` |
| Safely fast-forward a local repo before applying a repo update. | `scripts/Invoke-DcoirSafePrePullApply.ps1` | `dcoir_safe_prepull_apply_*.txt` |
| Share selected repo paths for ChatGPT review. | `scripts/New-DcoirTargetedSnapshot.ps1` | `*_snapshot_*.zip` and `*_snapshot_*.log.txt` |
| Share a broad text-only repo snapshot. | `scripts/New-DcoirTextOnlyRepoSnapshot.ps1` | `dcoir_text_only_repo_snapshot_*.zip`, log, and manifest |
| Apply a reviewed repo-relative update bundle. | `scripts/Invoke-DcoirRepoPatchApply.ps1` | `dcoir_repo_patch_apply_*.log.txt` and result JSON |
| Package local diagnostic folders for ChatGPT upload. | `scripts/New-DcoirChatGPTFriendlyZip.ps1` | caller-defined `.chatgpt.zip` |
| Watch, capture, or dispatch GitHub Actions workflows. | `scripts/Invoke-DcoirActionsWorkflowOrchestrator.ps1` | orchestrator output folder, summary files, and `.chatgpt.zip` |
| Run guarded Actions smoke validation. | `scripts/Invoke-DcoirActionsValidationSmoke.ps1` | smoke output ZIPs |
| Run a fail-fast Actions mode/suite ladder. | `scripts/Invoke-DcoirActionsModeLadder.ps1` | ladder output ZIPs and result JSON |

## Normal operator run pattern

1. Confirm GitHub Desktop is on the expected branch and the working tree state is understood.
2. Confirm `DCOIR_REPO_ROOT` and `DCOIR_DOWNLOADS_DIR` are set at Machine/System scope.
3. Choose the smallest tool that matches the current need.
4. Run the tool from PowerShell.
5. Keep the timestamped log/result JSON/ZIP in `DCOIR_DOWNLOADS_DIR`.
6. Upload the log/ZIP back to ChatGPT when readback or validation is needed.
7. Do not mark a tools-lane task complete until repo readback, validation evidence, and intended closeout targets have been reviewed.

## CAP logging pattern

For future local apply/CAP scripts, terminal output should be teed to a timestamped log in `DCOIR_DOWNLOADS_DIR` and the script should print clear success markers. Use this pattern when wrapping a local CAP sequence:

```powershell
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is not set at Machine/System scope.' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$capLog = Join-Path $downloads "dcoir_cap_$stamp.log.txt"

& {
  Write-Host '[DCOIR-CAP] START'
  git status --short
  git branch --show-current
  git log -1 --oneline
  Write-Host '[DCOIR-CAP] READY-FOR-OPERATOR-REVIEW'
} 2>&1 | Tee-Object -FilePath $capLog

Write-Host "[DCOIR-CAP] LOG: $capLog"
```

Expected success markers:

- `[DCOIR-CAP] START`
- `[DCOIR-CAP] READY-FOR-OPERATOR-REVIEW`
- `[DCOIR-CAP] LOG: <path>`

A committed and pushed state is CAP. A local commit that has not been pushed is not CAP.

## GitHub Desktop repo-update workflow

Use this workflow for documentation, tool, module, or skill-source parity bundles unless a direct commit is explicitly approved.

1. Download the repo-relative bundle from ChatGPT.
2. Extract it into the local repo root named by `DCOIR_REPO_ROOT`.
3. Confirm the ZIP has no wrapper root and paths land under the intended repo-relative folders.
4. Open GitHub Desktop and inspect every changed file.
5. Confirm no generated junk, secrets, logs, `.git`, or local-only files were added.
6. Commit with the suggested summary from ChatGPT.
7. Push to the remote branch.
8. Give ChatGPT the commit SHA or ask for GitHub readback.

## Module boundary

Harnesses and wrappers stay thin. Durable behavior belongs in modules:

- `Dcoir.Common`: shared environment, paths, logging, JSON, UTF-8, safe names, timestamps, and run context.
- `Dcoir.Git`: git executable discovery, clean-tree checks, branch checks, fetch, fast-forward pull, ahead/behind analysis, and logged git execution.
- `Dcoir.Snapshot`: repo-relative path safety, path normalization, text filtering, binary sniffing, targeted staging, and snapshot logging.
- `Dcoir.RepoPatch`: payload-root detection, wrapper-root stripping, allowed target roots, copy/delete planning, hashing, and repo patch logging.
- `Dcoir.GitHub`: GitHub CLI checks, `gh api` wrappers, Actions run lookup, run details, and job lookup.
- `Dcoir.Packaging`: ChatGPT-friendly ZIP creation and staging helpers.
- `Dcoir.Actions`: manifest parsing, dispatch guardrails, workflow monitoring, fail-fast gates, evidence capture, cleanup, summaries, and exit codes.
- `DcoirActionsOrchestrator`: compatibility facade that preserves the stable public orchestrator entrypoint.

When a wrapper needs logic shared by two or more tools, move that logic into the relevant module before promotion.

## Safety stop conditions

Stop and ask for guidance when any of these occur:

- `DCOIR_REPO_ROOT` or `DCOIR_DOWNLOADS_DIR` is missing, placeholder, or wrong.
- The repo is not the expected `dcoir-collector` working tree.
- GitHub Desktop shows unexpected changes outside the intended bundle.
- A tool proposes destructive git operations such as `git reset --hard`, `git clean`, or `git stash pop` without an approved recovery plan.
- A repo patch bundle includes files outside allowed target roots or includes wrapper-root junk.
- A live GitHub Actions dispatch would run more workflows than the reviewed manifest allows.
- Any log or bundle appears to contain secrets, tokens, or credentials.

## Evidence to preserve

For a successful tools-lane change, keep or upload:

- The applied repo-update bundle.
- GitHub Desktop changed-file review notes when useful.
- Tool smoke-test logs or result JSON when scripts/modules changed.
- `tool_catalog.json` diff when tools/modules changed.
- GitHub remote readback evidence after CAP.
- Related issue or PR traceability when governance-facing guidance changed.

Documentation-only updates normally require Markdown review and repo readback after CAP. Tool/module behavior changes require script-level regression evidence before closeout.

## Maintainer checklist

When adding or materially changing a tool/module:

1. Update the durable module or script source under `.github/operator_tools/github_desktop_lane/`.
2. Keep harnesses/wrappers thin.
3. Update `tool_catalog.json`.
4. Update `README.md`, this operator guide, and `modules/README.md` if the operator-facing behavior or module ecosystem changed.
5. Refresh any repo-governed documentation or issue/PR traceability tied to the affected tool.
6. Run the smallest meaningful smoke/regression test.
7. Package only affected repo-relative files in a GitHub Desktop bundle unless direct commit is approved.
8. After CAP, verify remote GitHub readback and then update validation/closeout records.