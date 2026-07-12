# DCOIR Operator Tool Logging Standard

## Purpose

DCOIR operator-run tools must leave behind enough evidence for ChatGPT to troubleshoot without screenshots.

Every local PowerShell tool or generated local-execution codeblock that performs execution, repo update staging, diagnostics, validation, capture, export, packaging, or workflow orchestration should produce one uploadable log or diagnostic file by default.

## Default module

Use:

```text
operator_tools/github_desktop_lane/modules/Dcoir.Logging/Dcoir.Logging.psm1
```

Do not create one-off script-local logging helpers when this module can be imported.

## Required behavior

A compliant tool should:

- import `Dcoir.Logging` at startup;
- call `Initialize-DcoirToolLog` before meaningful work begins;
- record phases with `Set-DcoirLogPhase`;
- write terminal-relevant status with `Write-DcoirLogLine`;
- write safe structured context with `Write-DcoirLogObject` when useful;
- use `Write-DcoirCaughtError` in catch blocks;
- return or print `log_path` on both success and failure;
- direct the operator to upload the single log file when troubleshooting is needed.

## Required log contents

The log should capture:

- tool name and version;
- logging module version;
- current directory;
- log path;
- resolved repo and output paths;
- relevant Machine/System environment variable presence, not secret values;
- phase transitions;
- key validation checks;
- hashes and counts when useful;
- error message and error type;
- script stack trace when available;
- next action.

## Secret handling

Logs must not print secret environment values. For secret-like configuration, log only presence, source, and non-sensitive names.

DCOIR work-item record contents are governed as scrubbed operational state by operator policy, but environment tokens and local secret values still must not be printed.

## Minimal pattern

```powershell
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$toolRoot = Split-Path -Parent $scriptRoot
$loggingModule = Join-Path $toolRoot 'modules\Dcoir.Logging\Dcoir.Logging.psm1'
Import-Module $loggingModule -Force
Initialize-DcoirToolLog -ToolName 'my_tool' -ToolVersion 'YYYY-MM-DD.N' -LogPath $LogPath | Out-Null

try {
  Set-DcoirLogPhase -Phase 'start'
  Write-DcoirLogLine -Message 'Starting work.'

  # tool work here

  Set-DcoirLogPhase -Phase 'complete'
  Write-DcoirLogLine -Message 'Completed successfully.'
  [ordered]@{
    success = $true
    log_path = Get-DcoirToolLogPath
  } | ConvertTo-Json -Depth 8
}
catch {
  $result = Write-DcoirCaughtError -ErrorRecord $_ -NextAction 'Upload the log_path file to ChatGPT.'
  $result | ConvertTo-Json -Depth 8
  exit 1
}
```

## Exceptions

Exceptions must be explicit and documented in the tool, registry row, or work item. A tool should not silently omit log output merely because it was written quickly or as a one-off diagnostic.

## First validated consumer

`operator_tools/github_desktop_lane/scripts/New-DcoirApplyInPayload.ps1` is the first tool wired to this module. It stages ChatGPT apply-in payloads and returns `log_path` for local failure or success triage.
