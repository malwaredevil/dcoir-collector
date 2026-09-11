# Codex Cloud Environment and PR Publish Contract

## Scope

This document records the validated Codex Cloud environment and PR publish mechanics for `malwaredevil/dcoir-collector`.

GitHub remains canonical source truth for repository branches, commits, pull requests, files, checks, and workflow results. A Codex task-side diff or commit is provisional until the intended GitHub branch is published and read back from GitHub.

## Authoritative platform references

Current platform behavior should be checked against:

- OpenAI Codex cloud environments: https://learn.chatgpt.com/docs/environments/cloud-environment
- OpenAI Codex GitHub integration: https://learn.chatgpt.com/docs/third-party/github

If those platform contracts materially change, revalidate this repository's Codex Cloud posture instead of recreating legacy behavior from memory.

## Validated baseline

As validated for issue #466 on 2026-09-11:

- Repository: `malwaredevil/dcoir-collector`
- Container image: `universal`
- Setup script: Automatic
- Container/post-setup caching: On
- Agent internet access: Off
- Custom environment variables: none
- Custom secrets: none
- Custom setup script: none
- Custom maintenance script: none
- Persisted GitHub PAT: none
- Custom Git credential helper: none
- Wrapped or replaced `gh`: none
- Repository-specific global `codex-*` helper commands: none

The universal image supplied the core Git, Python, pytest, ruff, black, mypy, pyright, isort, ripgrep, jq, curl, and GitHub CLI tooling required by the tested repository tasks.

The baseline did not include `shellcheck`, `shfmt`, `yamllint`, `bandit`, `pwsh`, or `powershell`. Their absence did not prevent the repository-native validation used by issue #466 from succeeding. Do not add optional tools merely to silence an optional warning; add dependencies only when a demonstrated repository requirement justifies them.

## Repository-native validation

Use:

`bash .github/dcoir_review/scripts/validate-codex-local.sh`

with explicit changed-file paths for bounded tasks when practical.

Validation output is evidence. A warning for an unavailable optional tool is not by itself a reason to mutate the environment.

For exact Windows PowerShell 5.1 evidence, rely on the repository's `windows-powershell-51.yml` GitHub Actions workflow. Linux PowerShell must not be represented as Windows PowerShell 5.1 validation.

Do not create or modify workflow files without explicit operator approval for workflow changes in the current task.

## PR context and exact-head discipline

A Codex Cloud PR task may use a task-local branch such as `work` and may have no configured Git remote. Do not repair that condition by adding a remote, rewriting Git configuration, adding credentials, or restoring retired environment helpers when the native GitHub integration is available.

Before a bounded PR mutation, confirm the expected PR branch and exact head SHA supplied by the approved task or live PR context. If they differ, stop as stale rather than editing against an unexpected head.

## Native PR publish behavior

Issue #466 / draft PR #545 proved the following behavior:

1. A PR-triggered Codex Cloud task produced the requested bounded diff in task-local state.
2. Task completion by itself did not update the GitHub PR branch.
3. The task UI exposed an `Update branch` action.
4. After the operator selected `Update branch`, GitHub advanced the existing PR branch and persisted the task-produced change.
5. GitHub readback confirmed the published commit and exact one-line diff.

The task-side commit reported before publish was `2c10e783dbfac77ed9216bfa800168c2feb64c33`. The GitHub commit created by `Update branch` was `ae320a00c7e5757e000977a854ce03525f25664e`. Therefore a task-side commit SHA must not be assumed to equal the final GitHub-published SHA.

For a task that belongs to an existing PR:

- use the task UI's `Update branch` action to publish the task result to that PR branch;
- do not select `Create new PR` unless the operator explicitly wants a separate PR;
- treat `Copy git apply` and `Copy patch` as manual fallback/export paths, not proof of native branch write-back;
- after `Update branch`, read back the live PR head, commit parent/diff, changed files, and relevant GitHub validation before claiming persistence or success.

If `Update branch` is unavailable or fails, stop and preserve the failure evidence. Do not work around the failure by restoring a persisted PAT, custom credential helper, wrapped `gh`, raw authenticated push path, or legacy repository-specific `codex-*` helper commands unless a separately governed change demonstrates that such a mechanism is required and the operator explicitly approves it.

## Revalidation triggers

Revalidate this contract when any of these materially changes:

- Codex Cloud environment configuration;
- OpenAI's documented cloud-environment or GitHub-integration behavior;
- repository dependency or validation requirements;
- GitHub integration permissions;
- PR task publish behavior;
- repository security or branch-protection requirements.
