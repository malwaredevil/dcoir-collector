[CmdletBinding()]
param(
    [string]$CallerEventName = 'workflow_call',
    [string]$InputRequestPath = 'chatgpt_staging/exec_requests/request.json',
    [string]$GithubSha = $env:GITHUB_SHA,
    [string]$GithubOutput = $env:GITHUB_OUTPUT
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-ChatGptExecOutput {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][AllowEmptyString()][string]$Value
    )
    if ([string]::IsNullOrWhiteSpace($GithubOutput)) {
        throw 'GITHUB_OUTPUT path is not available.'
    }
    "$Name=$Value" | Out-File -FilePath $GithubOutput -Encoding utf8 -Append
}

if ($CallerEventName -eq 'workflow_dispatch') {
    $requestPath = $InputRequestPath
} else {
    $changed = git diff-tree --no-commit-id --name-only -r $GithubSha
    $requestPath = ($changed | Where-Object { $_ -like 'chatgpt_staging/exec_requests/*.json' } | Select-Object -First 1)
}

if ([string]::IsNullOrWhiteSpace($requestPath)) {
    Write-ChatGptExecOutput -Name 'skip' -Value 'true'
    exit 0
}

if ($requestPath -notmatch '^chatgpt_staging/exec_requests/[A-Za-z0-9._-]+\.json$') {
    throw "Exec request path must match chatgpt_staging/exec_requests/<request_id>.json. Got: $requestPath"
}

if (-not (Test-Path -LiteralPath $requestPath -PathType Leaf)) {
    throw "Exec request file not found: $requestPath"
}

$requestId = [IO.Path]::GetFileNameWithoutExtension($requestPath)
Write-ChatGptExecOutput -Name 'skip' -Value 'false'
Write-ChatGptExecOutput -Name 'request_path' -Value $requestPath
Write-ChatGptExecOutput -Name 'request_id' -Value $requestId
