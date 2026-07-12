[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RequestId,
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [string]$Repository = $env:GITHUB_REPOSITORY
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$result = if ($env:DCOIR_EXEC_EXIT_CODE -eq '0') { 'success' } else { 'failure' }
$reportDir = Join-Path 'chatgpt_staging/status_reports/chatgpt-exec' $RequestId
$reportPath = Join-Path $reportDir 'workflow_report.md'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

python .github/scripts/write_chatgpt_progress_report.py `
    --workflow chatgpt-exec `
    --request-id $RequestId `
    --request-path $RequestPath `
    --phase final-readback-commit `
    --result $result `
    --exit-code $env:DCOIR_EXEC_EXIT_CODE `
    --artifact-name $env:DCOIR_EXEC_ARTIFACT_NAME `
    --message 'Final exec status is being committed with workflow report, progress history, marker, and any tracked summary files already produced by the request/tool. Full output remains in the uploaded GitHub Actions artifact.'

if (Test-Path -LiteralPath $reportPath -PathType Leaf) {
    @(
        '',
        '## GitHub Actions run',
        '',
        "- github_run_id: $env:GITHUB_RUN_ID",
        "- github_run_attempt: $env:GITHUB_RUN_ATTEMPT",
        "- github_sha: $env:GITHUB_SHA",
        "- github_ref: $env:GITHUB_REF",
        "- workflow_run_url: https://github.com/$Repository/actions/runs/$env:GITHUB_RUN_ID",
        '',
        '## Output readback contract',
        '',
        '- heartbeat_report: committed in this request-scoped status directory',
        '- tracked_summaries: read any concise summary files beside this report when present',
        '- full_output: uploaded GitHub Actions artifact named in this report',
        '- artifact_readback: optional and normally not committed for chatgpt-exec because .gitignore intentionally excludes unzipped artifact_readback trees'
    ) | Out-File -FilePath $reportPath -Encoding utf8 -Append
}

$markerPath = Join-Path $reportDir 'final_readback_marker.json'
[ordered]@{
    schema = 'dcoir.chatgpt_staging.exec_final_readback_marker.v2'
    request_id = $RequestId
    result = $result
    exit_code = $env:DCOIR_EXEC_EXIT_CODE
    artifact_name = $env:DCOIR_EXEC_ARTIFACT_NAME
    artifact_readback_committed = $false
    artifact_readback_policy = 'not_committed_for_chatgpt_exec; .gitignore intentionally excludes artifact_readback to avoid long-path checkout problems'
    tracked_summary_policy = 'requests/tools should write concise sanitized summaries beside workflow_report.md when ChatGPT connector-readable results are needed'
    github_run_id = $env:GITHUB_RUN_ID
    github_run_attempt = $env:GITHUB_RUN_ATTEMPT
    github_sha = $env:GITHUB_SHA
    github_ref = $env:GITHUB_REF
    created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
} | ConvertTo-Json -Depth 6 | Out-File -FilePath $markerPath -Encoding utf8

if ($env:DCOIR_EXEC_CLEANUP_REQUEST_AFTER_RUN -ne 'False' -and $env:DCOIR_EXEC_CLEANUP_REQUEST_AFTER_RUN -ne 'false') {
    Remove-Item -LiteralPath $RequestPath -Force -ErrorAction SilentlyContinue
}
