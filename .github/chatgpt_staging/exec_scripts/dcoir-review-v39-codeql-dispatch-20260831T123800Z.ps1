$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $env:GITHUB_WORKSPACE

$token = $env:DCOIR_GITHUB_CL_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) {
    $token = $env:DCOIR_GITHUB_FG_TOKEN
}
if ([string]::IsNullOrWhiteSpace($token)) {
    throw 'No authorized GitHub token bridge is available for CodeQL workflow dispatch.'
}

$headers = @{
    Authorization = "Bearer $token"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$body = @{ ref = 'main' } | ConvertTo-Json -Compress
Invoke-RestMethod `
    -Method Post `
    -Uri 'https://api.github.com/repos/malwaredevil/dcoir-collector/actions/workflows/codeql-security.yml/dispatches' `
    -Headers $headers `
    -ContentType 'application/json' `
    -Body $body | Out-Null

Write-Host 'CodeQL Security workflow dispatch submitted for main.'
exit 0
