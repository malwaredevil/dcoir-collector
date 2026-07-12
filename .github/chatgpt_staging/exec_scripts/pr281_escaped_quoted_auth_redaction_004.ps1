$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repo = $env:DCOIR_REPO_ROOT
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo) -or -not (Test-Path -LiteralPath $repo -PathType Container)) {
    throw 'Unable to resolve repository root.'
}

$branch = 'implement-pr-review-command-workflow'
$expectedHead = '90360eaf947711fe8af840ae0785e0ea2cd73b53'
$requestId = 'exec-20260619-pr281-escaped-quoted-auth-redaction-004'
$payloadB64 = Join-Path $repo '.github/chatgpt_staging/exec_payloads/pr281_escaped_quoted_auth_redaction_patch_002.py.b64'
$payload = Join-Path $env:RUNNER_TEMP "$requestId-payload.py"
$expectedPaths = @(
    '.github/dcoir_review/scripts/openrouter_pr_review.py',
    'scripts/openrouter_pr_review_selftest.py'
)
$expectedBlobs = @{
    '.github/dcoir_review/scripts/openrouter_pr_review.py' = '0c7cdf54e833597ab3572d3e1ff854c6c380ad37'
    'scripts/openrouter_pr_review_selftest.py' = 'a0e7cf08b387c42c1d35558b542b9cf895421ecb'
}

function Invoke-GitChecked {
    param(
        [Parameter(Mandatory=$true)][string]$Cwd,
        [Parameter(Mandatory=$true)][string[]]$GitArgs
    )
    $oldPreference = $ErrorActionPreference
    $out = @()
    $code = $null
    try {
        $ErrorActionPreference = 'Continue'
        $out = & git -C $Cwd @GitArgs 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($code -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $code`n$out"
    }
    return $out
}

function Get-GitText {
    param(
        [Parameter(Mandatory=$true)][string]$Cwd,
        [Parameter(Mandatory=$true)][string[]]$GitArgs
    )
    return ((Invoke-GitChecked -Cwd $Cwd -GitArgs $GitArgs | Out-String).Trim())
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter(Mandatory=$true)][string[]]$NativeArgs,
        [Parameter(Mandatory=$true)][string]$Label
    )
    $oldPreference = $ErrorActionPreference
    $out = @()
    $code = $null
    try {
        $ErrorActionPreference = 'Continue'
        $out = & $Exe @NativeArgs 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($code -ne 0) {
        throw "$Label failed with exit code $code`n$out"
    }
    return $out
}

if (-not (Test-Path -LiteralPath $payloadB64 -PathType Leaf)) {
    throw "Patch payload not found: $payloadB64"
}

[IO.File]::WriteAllBytes($payload, [Convert]::FromBase64String((Get-Content -LiteralPath $payloadB64 -Raw).Trim()))
Invoke-GitChecked -Cwd $repo -GitArgs @('fetch','origin',"+refs/heads/${branch}:refs/remotes/origin/${branch}") | Out-Null
$remoteHead = Get-GitText -Cwd $repo -GitArgs @('rev-parse',"origin/$branch")
if ($remoteHead -ne $expectedHead) {
    throw "PR branch head mismatch. Expected $expectedHead but got $remoteHead."
}

$tempRoot = $env:RUNNER_TEMP
if ([string]::IsNullOrWhiteSpace($tempRoot)) { $tempRoot = [IO.Path]::GetTempPath() }
$worktree = Join-Path $tempRoot $requestId
if (Test-Path -LiteralPath $worktree) {
    Remove-Item -LiteralPath $worktree -Recurse -Force
}

Invoke-GitChecked -Cwd $repo -GitArgs @('worktree','prune') | Out-Null
Invoke-GitChecked -Cwd $repo -GitArgs @('worktree','add','--detach',$worktree,"origin/$branch") | Out-Null
try {
    foreach ($path in $expectedPaths) {
        $line = Get-GitText -Cwd $worktree -GitArgs @('ls-files','-s','--',$path)
        $blob = (($line -split '\s+')[1])
        if ($blob -ne $expectedBlobs[$path]) {
            throw "Blob mismatch for $path. Expected $($expectedBlobs[$path]) but got $blob."
        }
    }

    Invoke-NativeChecked -Exe 'python' -NativeArgs @($payload, $worktree) -Label 'Patch payload' | Out-Null
    $selftestPath = Join-Path $worktree 'scripts/openrouter_pr_review_selftest.py'
    $selftestText = Get-Content -LiteralPath $selftestPath -Raw -Encoding UTF8
    if ($selftestText.Contains('hdeader_quoted_secret')) {
        $selftestText.Replace('hdeader_quoted_secret', 'header_quoted_secret') | Out-File -FilePath $selftestPath -Encoding utf8
    }
    Invoke-NativeChecked -Exe 'python' -NativeArgs @(
        '-m',
        'py_compile',
        (Join-Path $worktree '.github/dcoir_review/scripts/openrouter_pr_review.py'),
        (Join-Path $worktree 'scripts/openrouter_pr_review_selftest.py')
    ) -Label 'py_compile' | Out-Null
    Invoke-NativeChecked -Exe 'python' -NativeArgs @((Join-Path $worktree 'scripts/openrouter_pr_review_selftest.py')) -Label 'offline selftest' | Out-Null
    Invoke-GitChecked -Cwd $worktree -GitArgs @('diff','--check','--') | Out-Null
    Invoke-GitChecked -Cwd $worktree -GitArgs @('config','user.name','github-actions[bot]') | Out-Null
    Invoke-GitChecked -Cwd $worktree -GitArgs @('config','user.email','41898282+github-actions[bot]@users.noreply.github.com') | Out-Null
    Invoke-GitChecked -Cwd $worktree -GitArgs (@('add','--') + $expectedPaths) | Out-Null
    Invoke-GitChecked -Cwd $worktree -GitArgs @('diff','--cached','--check') | Out-Null

    $changedText = Get-GitText -Cwd $worktree -GitArgs @('diff','--cached','--name-only')
    $changedPaths = @($changedText -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $unexpected = @($changedPaths | Where-Object { $expectedPaths -notcontains $_ })
    $missing = @($expectedPaths | Where-Object { $changedPaths -notcontains $_ })
    if ($unexpected.Count -gt 0) { throw "Unexpected changed paths: $($unexpected -join ', ')" }
    if ($missing.Count -gt 0) { throw "Expected changed paths missing: $($missing -join ', ')" }

    Invoke-GitChecked -Cwd $worktree -GitArgs @('commit','-m','Redact escaped quoted auth credentials') | Out-Null
    $newHead = Get-GitText -Cwd $worktree -GitArgs @('rev-parse','HEAD')
    $token = $env:DCOIR_GITHUB_FG_TOKEN
    if ([string]::IsNullOrWhiteSpace($token)) { $token = $env:DCOIR_GITHUB_CL_TOKEN }
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw 'No bridged GitHub token secret is available for PR branch push.'
    }

    Write-Host "::add-mask::$token"
    $repoFull = $env:GITHUB_REPOSITORY
    if ([string]::IsNullOrWhiteSpace($repoFull)) { $repoFull = 'DCOIR-Collector/dcoir-collector' }
    $pushUrl = "https://x-access-token:${token}@github.com/${repoFull}.git"
    Invoke-GitChecked -Cwd $worktree -GitArgs @('-c','http.https://github.com/.extraheader=','push',$pushUrl,"HEAD:refs/heads/$branch") | Out-Null

    $summaryDir = Join-Path $repo ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
    New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
    [ordered]@{
        schema = 'dcoir.chatgpt_exec.pr281_escaped_quoted_auth_redaction.v1'
        request_id = $requestId
        result = 'success'
        branch = $branch
        starting_head = $expectedHead
        new_head = $newHead
        changed_paths = $changedPaths
        validations = @(
            'branch_head_guard',
            'blob_guards',
            'payload_decode',
            'patch_payload',
            'py_compile',
            'offline_selftest',
            'diff_check',
            'changed_path_guard',
            'push'
        )
        targeted_thread = 'PRRT_kwDOR0OHZ86K4Ddo'
        created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    } | ConvertTo-Json -Depth 6 | Out-File -FilePath (Join-Path $summaryDir 'pr281_escaped_quoted_auth_redaction_summary.json') -Encoding utf8

    @(
        '# PR #281 escaped quoted auth redaction summary',
        '',
        '- result: success',
        "- branch: $branch",
        "- starting_head: $expectedHead",
        "- new_head: $newHead",
        "- changed_paths: $($changedPaths -join ', ')",
        '- targeted_thread: PRRT_kwDOR0OHZ86K4Ddo',
        '- validation: branch head guard; blob guards; payload decode; patch payload; py_compile; offline selftest; diff checks; changed-path guard; push',
        '',
        'Summary: hardened Authorization and Proxy-Authorization auth-scheme redaction so escaped quoted tokens after Bearer, Basic, and token are consumed as part of the credential while exact escaped safe references remain preserved.'
    ) | Out-File -FilePath (Join-Path $summaryDir 'pr281_escaped_quoted_auth_redaction_summary.md') -Encoding utf8

    Write-Host "new_head=$newHead"
}
finally {
    if (Test-Path -LiteralPath $worktree) {
        try {
            Invoke-GitChecked -Cwd $repo -GitArgs @('worktree','remove','--force',$worktree) | Out-Null
        }
        catch {
            Write-Warning "Unable to remove worktree ${worktree}: $($_.Exception.Message)"
        }
    }
}
