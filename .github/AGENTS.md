# .github AGENTS.md

## Scope

These instructions apply to files under `.github/`. They supplement the repository root `AGENTS.md` and do not override workflow-boundary rules.

## GitHub Actions and repository automation review guidance

Workflow files are governed surfaces. Do not create, edit, loosen, or remove workflow files unless the operator explicitly approves workflow changes in the current task.

When reviewing `.github/workflows/` changes, prioritize:

- unsafe `pull_request_target` usage
- untrusted PR data interpolated into shell commands
- missing or overbroad `permissions:` blocks
- secret exposure in logs, artifacts, summaries, or uploaded reports
- write-token use where read-only token permissions would be sufficient
- artifact path traversal, untrusted zip extraction, or unsafe generated script execution
- stale repository identity, branch, path, or workflow-name references
- validation claims without workflow run, job, step, or artifact readback

When a Codex Cloud PR task touches GitHub metadata, templates, CODEOWNERS, workflows, or repository governance files, use the task's current PR context plus GitHub source-truth readback to confirm the intended branch/head and report validation gaps explicitly. Do not depend on a legacy `codex-pr-context` environment helper.

## Security and compatibility workflows

The repo-local CodeQL workflow is `codeql-security.yml` and its reusable implementation is `reusable-codeql-security.yml`. It is intended to analyze supported CodeQL languages in this repository, especially Python and GitHub Actions workflow surfaces. Do not treat CodeQL as a replacement for collector runtime validation, dependency review, or manual security review.

The repo-local Windows PowerShell 5.1 workflow is `windows-powershell-51.yml` and its reusable implementation is `reusable-windows-powershell-51.yml`. It is the workflow-level evidence surface for exact Windows PowerShell 5.1 parser compatibility. Linux `pwsh` output is not equivalent.

When reviewing these workflows, also check the workflow modularization registry, workflow inventory, and reporter allowlist surfaces so workflow-governance checks remain aligned.

