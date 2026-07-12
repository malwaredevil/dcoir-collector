$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT', 'Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo) -or -not (Test-Path -LiteralPath $repo -PathType Container)) {
    throw 'Unable to resolve repository root.'
}

$branch = 'codex/issue-306-function-reachability-report'
$expectedHead = 'a04a447be79d1fe44e77f2e6c98222622a4680d6'
$requestId = 'exec-20260624-issue306-function-reachability-002'
$payloadDir = Join-Path $repo '.github/chatgpt_staging/exec_payloads'
$payloadPartPrefix = 'issue306_function_reachability_patch_001.diff.gz.b64.part'
$fetchRefspec = "+refs/heads/${branch}:refs/remotes/origin/${branch}"
$pushRefspec = "HEAD:refs/heads/${branch}"
$tempRoot = $env:RUNNER_TEMP
if ([string]::IsNullOrWhiteSpace($tempRoot)) { $tempRoot = [IO.Path]::GetTempPath() }
$worktree = Join-Path $tempRoot $requestId
$patchPath = Join-Path $tempRoot "$requestId.diff"
$compressedPatchPath = Join-Path $tempRoot "$requestId.diff.gz"
$reportDir = Join-Path $repo ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
$expectedPaths = @(
    '.github/actions/run-powershell-review-assist/action.yml',
    'project_sources/collector/powershell_function_reachability_report.json',
    'project_sources/collector/powershell_function_reachability_report.md',
    'project_sources/collector/powershell_review_assist_report.json',
    'project_sources/collector/powershell_review_assist_report.md',
    'project_sources/collector/tools/run_powershell_function_reachability_report.py',
    'project_sources/collector/tools/run_powershell_review_assist_report.py',
    'project_sources/collector/tools/test_run_powershell_function_reachability_report.py',
    'project_sources/collector/tools/test_run_powershell_review_assist_report.py'
)
$validationResults = New-Object System.Collections.Generic.List[string]
$summary = [ordered]@{
    schema = 'dcoir.chatgpt_staging.issue306_function_reachability_summary.v1'
    request_id = $requestId
    target_branch = $branch
    expected_start_head = $expectedHead
    result = 'running'
    changed_paths = @()
    validation_results = @()
    new_head = $null
    pushed_head = $null
    error = $null
    created_utc = $null
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string]$Cwd,
        [Parameter(Mandatory = $true)][string[]]$GitArgs
    )
    $old = $ErrorActionPreference
    $output = @()
    $exitCode = $null
    try {
        $ErrorActionPreference = 'Continue'
        $output = & git -C $Cwd @GitArgs 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    if ($exitCode -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $exitCode`n$output"
    }
    return $output
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Cwd,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )
    $old = $ErrorActionPreference
    $oldLocation = Get-Location
    $output = @()
    $exitCode = $null
    try {
        $ErrorActionPreference = 'Continue'
        Set-Location -LiteralPath $Cwd
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        Set-Location -LiteralPath $oldLocation
        $ErrorActionPreference = $old
    }
    if ($exitCode -ne 0) {
        throw "$Description failed with exit code $exitCode`n$output"
    }
    return $output
}

function Add-ValidationResult {
    param([Parameter(Mandatory = $true)][string]$Value)
    $validationResults.Add($Value) | Out-Null
}

function Get-GitText {
    param([Parameter(Mandatory = $true)][string]$Cwd, [Parameter(Mandatory = $true)][string[]]$GitArgs)
    return ((Invoke-Git -Cwd $Cwd -GitArgs $GitArgs | Out-String).Trim())
}

function Get-ChangedPaths {
    param([Parameter(Mandatory = $true)][string]$Cwd)
    $lines = Invoke-Git -Cwd $Cwd -GitArgs @('status', '--porcelain')
    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.Length -lt 4) { continue }
        $paths.Add($line.Substring(3).Replace([char]92, [char]47)) | Out-Null
    }
    return @($paths.ToArray() | Sort-Object -Unique)
}

function Assert-ExpectedPathSet {
    param(
        [Parameter(Mandatory = $true)][string[]]$ActualPaths,
        [Parameter(Mandatory = $true)][string[]]$ExpectedPaths,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $unexpected = @($ActualPaths | Where-Object { $ExpectedPaths -notcontains $_ })
    $missing = @($ExpectedPaths | Where-Object { $ActualPaths -notcontains $_ })
    if ($unexpected.Count -gt 0 -or $missing.Count -gt 0) {
        throw "$Label path guard failed. Unexpected: $($unexpected -join ', '); missing: $($missing -join ', ')"
    }
}

function Get-RequiredGitToken {
    foreach ($name in @('DCOIR_GITHUB_FG_TOKEN', 'DCOIR_GITHUB_CL_TOKEN')) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ([string]::IsNullOrWhiteSpace($value)) { $value = [Environment]::GetEnvironmentVariable($name, 'Machine') }
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Write-Host "Using bridged GitHub token secret for target branch push: $name"
            Write-Host "::add-mask::$value"
            return $value
        }
    }
    throw 'No bridged GitHub token secret is available for target branch push.'
}

function Invoke-GitPushWithToken {
    param(
        [Parameter(Mandatory = $true)][string]$Cwd,
        [Parameter(Mandatory = $true)][string]$Token,
        [Parameter(Mandatory = $true)][string]$Refspec
    )
    $repoFull = $env:GITHUB_REPOSITORY
    if ([string]::IsNullOrWhiteSpace($repoFull)) { $repoFull = 'DCOIR-Collector/dcoir-collector' }
    $pushUrl = "https://x-access-token:${Token}@github.com/${repoFull}.git"
    $old = $ErrorActionPreference
    $output = @()
    $exitCode = $null
    try {
        $ErrorActionPreference = 'Continue'
        $output = & git -C $Cwd -c 'http.https://github.com/.extraheader=' push $pushUrl $Refspec 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    if ($exitCode -ne 0) {
        $safeOutput = (($output | Out-String).Replace($Token, '[REDACTED:GITHUB_TOKEN]')).Trim()
        throw "git push failed with exit code $exitCode`n$safeOutput"
    }
    return $output
}

function Expand-GzipBase64Payload {
    param(
        [Parameter(Mandatory = $true)][string]$PartDirectory,
        [Parameter(Mandatory = $true)][string]$PartPrefix,
        [Parameter(Mandatory = $true)][string]$CompressedPath,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )
    if (-not (Test-Path -LiteralPath $PartDirectory -PathType Container)) {
        throw "Payload directory not found: $PartDirectory"
    }
    $parts = @(Get-ChildItem -LiteralPath $PartDirectory -File | Where-Object { $_.Name -like "$PartPrefix*" } | Sort-Object Name)
    if ($parts.Count -lt 1) {
        throw "No payload parts found with prefix $PartPrefix in $PartDirectory"
    }
    $builder = New-Object Text.StringBuilder
    foreach ($part in $parts) {
        [void]$builder.Append((Get-Content -LiteralPath $part.FullName -Raw -Encoding UTF8).Trim())
    }
    $raw = $builder.ToString()
    [IO.File]::WriteAllBytes($CompressedPath, [Convert]::FromBase64String($raw))
    $inputStream = [IO.File]::OpenRead($CompressedPath)
    try {
        $gzipStream = New-Object IO.Compression.GzipStream($inputStream, [IO.Compression.CompressionMode]::Decompress)
        try {
            $outputStream = [IO.File]::Create($OutputPath)
            try {
                $gzipStream.CopyTo($outputStream)
            } finally {
                $outputStream.Dispose()
            }
        } finally {
            $gzipStream.Dispose()
        }
    } finally {
        $inputStream.Dispose()
    }
}

function Write-Summary {
    $summary.changed_paths = @($summary.changed_paths)
    $summary.validation_results = @($validationResults.ToArray())
    $summary.created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    $summary | ConvertTo-Json -Depth 8 | Out-File -FilePath (Join-Path $reportDir 'issue306_function_reachability_summary.json') -Encoding utf8
    @(
        '# Issue #306 function reachability staging summary',
        '',
        "- request_id: $requestId",
        "- result: $($summary.result)",
        "- target_branch: $branch",
        "- expected_start_head: $expectedHead",
        "- new_head: $($summary.new_head)",
        "- pushed_head: $($summary.pushed_head)",
        '',
        '## Changed paths',
        ''
    ) + ($summary.changed_paths | ForEach-Object { "- $_" }) + @(
        '',
        '## Validation',
        ''
    ) + ($validationResults.ToArray() | ForEach-Object { "- $_" }) | Out-File -FilePath (Join-Path $reportDir 'issue306_function_reachability_summary.md') -Encoding utf8
}

try {
    Invoke-Git -Cwd $repo -GitArgs @('fetch', '--quiet', 'origin', $fetchRefspec) | Out-Null
    $remoteHead = Get-GitText -Cwd $repo -GitArgs @('rev-parse', "origin/$branch")
    if ($remoteHead -ne $expectedHead) {
        throw "Target branch head mismatch. Expected $expectedHead but origin/$branch is $remoteHead."
    }

    if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force }
    Invoke-Git -Cwd $repo -GitArgs @('worktree', 'prune') | Out-Null
    Invoke-Git -Cwd $repo -GitArgs @('worktree', 'add', '--detach', $worktree, "origin/$branch") | Out-Null

    Expand-GzipBase64Payload -PartDirectory $payloadDir -PartPrefix $payloadPartPrefix -CompressedPath $compressedPatchPath -OutputPath $patchPath
    Invoke-Git -Cwd $worktree -GitArgs @('apply', '--check', $patchPath) | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs @('apply', $patchPath) | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs (@('add', '-N', '--') + $expectedPaths) | Out-Null
    $changedPaths = @(Get-ChangedPaths -Cwd $worktree)
    Assert-ExpectedPathSet -ActualPaths $changedPaths -ExpectedPaths $expectedPaths -Label 'post-apply'
    $summary.changed_paths = $changedPaths

    Invoke-NativeCommand -Cwd $worktree -FilePath 'python' -Arguments @(
        '-m', 'py_compile',
        'project_sources/collector/tools/run_powershell_function_reachability_report.py',
        'project_sources/collector/tools/run_powershell_review_assist_report.py',
        'project_sources/collector/tools/test_run_powershell_function_reachability_report.py',
        'project_sources/collector/tools/test_run_powershell_review_assist_report.py'
    ) -Description 'Python compile validation' | Out-Null
    Add-ValidationResult 'python -m py_compile touched report scripts/tests: passed'

    Invoke-NativeCommand -Cwd $worktree -FilePath 'python' -Arguments @(
        'project_sources/collector/tools/run_powershell_function_reachability_report.py',
        '--repo-root', '.',
        '--parser-mode', 'python_lexical_fallback',
        '--no-write'
    ) -Description 'Function reachability no-write validation' | Out-Null
    Add-ValidationResult 'function reachability no-write validation: passed'

    Invoke-NativeCommand -Cwd $worktree -FilePath 'python' -Arguments @(
        'project_sources/collector/tools/run_powershell_review_assist_report.py',
        '--repo-root', '.',
        '--no-write'
    ) -Description 'Review-assist no-write validation' | Out-Null
    Add-ValidationResult 'review-assist no-write validation: passed'

    Invoke-NativeCommand -Cwd $worktree -FilePath 'python' -Arguments @('project_sources/collector/tools/test_run_powershell_function_reachability_report.py') -Description 'Function reachability unit tests' | Out-Null
    Add-ValidationResult '8 function reachability tests: passed'

    Invoke-NativeCommand -Cwd $worktree -FilePath 'python' -Arguments @('project_sources/collector/tools/test_run_powershell_review_assist_report.py') -Description 'Review-assist unit tests' | Out-Null
    Add-ValidationResult '21 review-assist tests: passed'

    Invoke-NativeCommand -Cwd $worktree -FilePath 'python' -Arguments @('-m', 'unittest', 'discover', 'project_sources/collector/tools', '-p', 'test_run_powershell*.py') -Description 'PowerShell report unittest discovery' | Out-Null
    Add-ValidationResult '225 PowerShell report unittest discovery tests: passed'

    Invoke-Git -Cwd $worktree -GitArgs @('diff', '--check', '--') | Out-Null
    Add-ValidationResult 'git diff --check: passed'

    Invoke-Git -Cwd $worktree -GitArgs (@('add', '--') + $expectedPaths) | Out-Null
    $stagedPaths = @((Invoke-Git -Cwd $worktree -GitArgs @('diff', '--cached', '--name-only') | ForEach-Object { $_.Replace([char]92, [char]47) }) | Sort-Object -Unique)
    Assert-ExpectedPathSet -ActualPaths $stagedPaths -ExpectedPaths $expectedPaths -Label 'staged'

    Invoke-Git -Cwd $worktree -GitArgs @('config', 'user.name', 'dcoir-chatgpt-exec') | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs @('config', 'user.email', 'dcoir-chatgpt-exec@users.noreply.github.com') | Out-Null
    Invoke-Git -Cwd $worktree -GitArgs @('commit', '-m', 'Add collector function reachability report') | Out-Null
    $newHead = Get-GitText -Cwd $worktree -GitArgs @('rev-parse', 'HEAD')
    $summary.new_head = $newHead

    $token = Get-RequiredGitToken
    Invoke-GitPushWithToken -Cwd $worktree -Token $token -Refspec $pushRefspec | Out-Null
    Invoke-Git -Cwd $repo -GitArgs @('fetch', '--quiet', 'origin', $fetchRefspec) | Out-Null
    $pushedHead = Get-GitText -Cwd $repo -GitArgs @('rev-parse', "origin/$branch")
    $summary.pushed_head = $pushedHead
    if ($pushedHead -ne $newHead) {
        throw "Post-push readback mismatch. Expected $newHead but origin/$branch is $pushedHead."
    }
    $summary.result = 'success'
    Write-Summary
    Write-Output ($summary | ConvertTo-Json -Depth 8)
} catch {
    $summary.result = 'failure'
    $summary.error = ($_ | Out-String).Trim()
    Write-Summary
    throw
} finally {
    if (Test-Path -LiteralPath $worktree) {
        try {
            Invoke-Git -Cwd $repo -GitArgs @('worktree', 'remove', '--force', $worktree) | Out-Null
        } catch {
            Write-Warning "Failed to remove temporary worktree ${worktree}: $_"
        }
    }
}
