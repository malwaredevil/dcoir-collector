# Repository validation scripts

This folder contains operator-friendly validation wrappers used by Codex, GitHub Desktop, and manual review lanes.

## Scripts

- `validate-codex-local.sh` runs a local best-effort review pass using available tools such as `rg`, `shellcheck`, `shfmt`, `yamllint`, `ruff`, `bandit`, `semgrep`, and PowerShell parser checks. Invoke it with `bash .github/dcoir_review/scripts/validate-codex-local.sh` so it works even when the executable bit is not preserved by local checkout tooling. With explicit path arguments, it validates only those files. With no arguments, it validates changed files relative to `CODEX_BASE_REF` or `origin/main`, plus staged and unstaged local changes; it does not scan every tracked file by default.
- `validate-windows-powershell-51.ps1` validates PowerShell parser compatibility. In the Windows PowerShell 5.1 workflow it requires Windows PowerShell 5.1; local Linux/macOS syntax checks may pass `-AllowPowerShell7`.
- `validate-codeql-security-workflow.py` validates that the repo-local CodeQL workflow and reusable workflow retain the expected security configuration shape. Invoke it with `python3 .github/dcoir_review/scripts/validate-codeql-security-workflow.py`.
- `read-pr-validation-state.py` is the canonical post-publication PR readback helper. It reads the PR head/mergeability, the **complete commit check-run collection** (including separate GitHub Advanced Security result checks such as `CodeQL`), Actions workflow runs, legacy commit statuses, unresolved review threads, and annotations for failed checks when available. Use `python3 .github/dcoir_review/scripts/read-pr-validation-state.py --repo <owner/repo> --pr <number> --expected-head <sha>`. A green Actions workflow alone is not sufficient evidence.
- `dcoir_review_pr_validation_readback_selftest.py` protects the readback contract, including the failure mode where CodeQL Actions jobs succeed but the separate GHAS `CodeQL` results check fails.

These scripts do not replace GitHub Actions readback. Use workflow run, job, step, and artifact evidence for governed readiness claims.

## Historical compatibility boundary

Production DCOIR Review uses responsibility-named owners only. Numbered historical runtime module names are compatibility wrappers for legacy imports/tests and must not become implementation dependencies of stable production modules. The runtime-module-loader selftest enforces both zero numbered production roots and zero stable-to-numbered imports.
