# DCOIR Collector Pester tests

This directory contains Pester tests intended for the Codex review helper and optional local operator runs.

These tests require **Pester 5 or newer**. Windows PowerShell 5.1 commonly loads an older inbox Pester module first, so prefer the wrapper script below instead of calling `Invoke-Pester -CI` directly.

## First-time local setup

From the repository root:

```powershell
.github/pester/Install-DcoirPesterPrereqs.ps1
```

Or manually:

```powershell
Install-Module Pester -Scope CurrentUser -MinimumVersion 5.0.0 -Force -SkipPublisherCheck
Remove-Module Pester -ErrorAction SilentlyContinue
Import-Module Pester -MinimumVersion 5.0.0 -Force
```

## Run locally

Recommended:

```powershell
.github/pester/Invoke-DcoirPester.ps1
```

To return the Pester result object:

```powershell
.github/pester/Invoke-DcoirPester.ps1 -PassThru
```

To prove that passing, known-failing, and empty-discovery runs produce the
required exit behavior:

```powershell
.github/pester/Test-DcoirPesterRunner.ps1
```

For CI-style test-result output through the wrapper:

```powershell
.github/pester/Invoke-DcoirPester.ps1 -CI
```

The workflow pins both the approved module version and the current discovery
floor. The equivalent local command is:

```powershell
.github/pester/Invoke-DcoirPester.ps1 -RequiredPesterVersion 5.7.1 -MinimumTestCount 45 -CI
```

Direct Pester invocation also works after Pester 5+ is imported:

```powershell
Invoke-Pester -Path .github/pester -Output Detailed
```

Avoid using `Invoke-Pester -CI` until you have confirmed Pester 5+ is loaded. The wrapper script version-checks this for you and imports the newest installed Pester 5+ module.

## Scope

These tests are deliberately supporting checks. They do not replace the repository's existing collector validation lanes, Windows PowerShell 5.1 parser workflow, PSScriptAnalyzer/custom-check reports, fixture reports, assembly parity checks, or harness regression workflows.

The tests focus on:

- collector wrapper, source-part, and manifest alignment;
- parser compatibility for the wrapper and maintained collector parts;
- public parameter ValidateSet and alias contracts;
- static safety guardrails that are cheap to verify in PR review;
- low-risk runtime smoke checks for `-ShowVersion`, `-ShowHelp`, path-leaf validators, and JSON truncation handling;
- deterministic function behavior for cleanup containment, event windows and filters, UTF-8 chunking/reconstruction, and quick aliases;
- harness presence and the repository Pester-boundary policy;
- high-risk behavior contracts for cleanup/purge, quick shortcuts, event windows, and upload-safe chunking.

## Codex behavior

The Codex setup helper should run Pester only when changed PowerShell files exist and `*.Tests.ps1` files are present. The preferred path is this directory: `.github/pester`.

Linux `pwsh` Pester results are useful for syntax, AST, cross-platform static checks, and low-risk smoke behavior. They do not prove exact Windows PowerShell 5.1 behavior. Use the existing `windows-powershell-51.yml` workflow for Windows PowerShell 5.1 validation.
