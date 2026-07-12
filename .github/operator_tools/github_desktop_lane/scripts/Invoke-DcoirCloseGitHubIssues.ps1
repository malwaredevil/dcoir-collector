<#
.SYNOPSIS
  Safely close GitHub issues in a repository using a local token environment variable.

.DESCRIPTION
  Defaults to dry-run. Requires -Apply and -ConfirmCloseAll to actually close issues.
  Uses DCOIR_GITHUB_FG_TOKEN first, then DCOIR_GITHUB_CL_TOKEN unless -TokenEnvName is specified.
  Writes timestamped logs and JSON reports to DCOIR_DOWNLOADS_DIR.
#>
[CmdletBinding()]
param(
    [string]$Owner = "DCOIR-Collector",
    [string]$Repo = "dcoir-collector",
    [string]$TokenEnvName = "",
    [switch]$Apply,
    [switch]$ConfirmCloseAll,
    [string]$StateReason = "not_planned",
    [string]$CloseComment = "Closed by DCOIR operator bulk issue close tool after operator-approved repository cleanup.",
    [int]$MaxIssues = 0
)

$ErrorActionPreference = "Stop"

function Get-MachineOrProcessEnvValue {
    param([Parameter(Mandatory=$true)][string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name, "Machine")
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, "User")
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    }
    return $value
}

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $script:LogPath -Value $line -Encoding UTF8
}

function Invoke-GitHubApi {
    param(
        [Parameter(Mandatory=$true)][string]$Method,
        [Parameter(Mandatory=$true)][string]$Uri,
        [object]$Body = $null
    )
    $headers = @{
        Authorization = "Bearer $script:Token"
        Accept = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent" = "DCOIR-Issue-Close-Tool"
    }
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers
    }
    $json = $Body | ConvertTo-Json -Depth 20
    return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -Body $json -ContentType "application/json"
}

function Get-OpenIssues {
    $issues = New-Object System.Collections.Generic.List[object]
    $page = 1
    while ($true) {
        $uri = "https://api.github.com/repos/$Owner/$Repo/issues?state=open&per_page=100&page=$page"
        $pageItems = Invoke-GitHubApi -Method GET -Uri $uri
        if ($null -eq $pageItems -or $pageItems.Count -eq 0) { break }
        foreach ($item in $pageItems) {
            if ($null -eq $item.pull_request) {
                $issues.Add($item)
                if ($MaxIssues -gt 0 -and $issues.Count -ge $MaxIssues) { return $issues }
            }
        }
        $page += 1
    }
    return $issues
}

$downloads = Get-MachineOrProcessEnvValue -Name "DCOIR_DOWNLOADS_DIR"
if ([string]::IsNullOrWhiteSpace($downloads)) {
    $downloads = [Environment]::GetFolderPath("UserProfile") + "\Downloads"
}
if (-not (Test-Path -LiteralPath $downloads)) {
    New-Item -ItemType Directory -Path $downloads -Force | Out-Null
}

$stamp = Get-Date -Format "yyyyMMddTHHmmss"
$script:LogPath = Join-Path $downloads "dcoir_close_github_issues_$stamp.log.txt"
$ReportPath = Join-Path $downloads "dcoir_close_github_issues_$stamp.json"

Write-Host "DCOIR GitHub issue close tool"
Write-Host "Repository: $Owner/$Repo"
Write-Host "Mode: $(@('dry-run','apply')[[bool]$Apply])"
Write-Host "Log: $script:LogPath"
Write-Host "Report: $ReportPath"
Write-Host "Expected success marker: DCOIR_CLOSE_GITHUB_ISSUES_DONE"

$tokenNames = @()
if (-not [string]::IsNullOrWhiteSpace($TokenEnvName)) {
    $tokenNames += $TokenEnvName
} else {
    $tokenNames += "DCOIR_GITHUB_FG_TOKEN"
    $tokenNames += "DCOIR_GITHUB_CL_TOKEN"
}

$script:Token = $null
$usedTokenName = $null
foreach ($name in $tokenNames) {
    $candidate = Get-MachineOrProcessEnvValue -Name $name
    if (-not [string]::IsNullOrWhiteSpace($candidate)) {
        $script:Token = $candidate
        $usedTokenName = $name
        break
    }
}

if ([string]::IsNullOrWhiteSpace($script:Token)) {
    throw "No GitHub token found. Set DCOIR_GITHUB_FG_TOKEN or DCOIR_GITHUB_CL_TOKEN as a Machine/User environment variable."
}

Write-Log "Token source: $usedTokenName (value not printed)"
Write-Log "Fetching open issues from $Owner/$Repo"
$issues = Get-OpenIssues
Write-Log "Open issues found, excluding PRs: $($issues.Count)"

$result = [ordered]@{
    repository = "$Owner/$Repo"
    mode = if ($Apply) { "apply" } else { "dry-run" }
    token_source = $usedTokenName
    issue_count = $issues.Count
    closed = @()
    would_close = @()
    errors = @()
    generated_at = (Get-Date).ToString("o")
}

if (-not $Apply) {
    foreach ($issue in $issues) {
        $result.would_close += [ordered]@{ number = $issue.number; title = $issue.title; url = $issue.html_url }
        Write-Log ("DRY RUN would close #{0}: {1}" -f $issue.number, $issue.title)
    }
} else {
    if (-not $ConfirmCloseAll) {
        throw "Apply mode requires -ConfirmCloseAll. Rerun only after reviewing dry-run output."
    }
    foreach ($issue in $issues) {
        try {
            Write-Log ("Closing #{0}: {1}" -f $issue.number, $issue.title)
            if (-not [string]::IsNullOrWhiteSpace($CloseComment)) {
                $commentUri = "https://api.github.com/repos/$Owner/$Repo/issues/$($issue.number)/comments"
                Invoke-GitHubApi -Method POST -Uri $commentUri -Body @{ body = $CloseComment } | Out-Null
            }
            $issueUri = "https://api.github.com/repos/$Owner/$Repo/issues/$($issue.number)"
            $body = @{ state = "closed"; state_reason = $StateReason }
            Invoke-GitHubApi -Method PATCH -Uri $issueUri -Body $body | Out-Null
            $result.closed += [ordered]@{ number = $issue.number; title = $issue.title; url = $issue.html_url }
        } catch {
            $msg = "Failed to close #$($issue.number): $($_.Exception.Message)"
            Write-Log $msg
            $result.errors += [ordered]@{ number = $issue.number; title = $issue.title; error = $_.Exception.Message }
        }
    }
}

$result | ConvertTo-Json -Depth 20 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Log "Report written: $ReportPath"
if ($result.errors.Count -gt 0) {
    Write-Log "Completed with errors: $($result.errors.Count)"
    exit 2
}
Write-Log "DCOIR_CLOSE_GITHUB_ISSUES_DONE"
