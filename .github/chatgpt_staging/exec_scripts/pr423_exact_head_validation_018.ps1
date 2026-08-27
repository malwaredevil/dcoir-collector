$ErrorActionPreference = 'Stop'
$expected = 'bbd844e748ad6e5e43be492cd2720512fca61ba7'
$branch = 'issue-421-openai-gpt-deployment-builder'
$worktree = Join-Path $env:RUNNER_TEMP 'pr423-exact-head-validation-018'

git fetch --no-tags origin $branch
if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
$observed = (git rev-parse ('origin/' + $branch)).Trim()
if ($observed -ne $expected) { throw "PR head moved: expected $expected, observed $observed" }
if (Test-Path -LiteralPath $worktree) { git worktree remove --force $worktree 2>$null | Out-Null }
git worktree add --detach $worktree $expected
if ($LASTEXITCODE -ne 0) { throw 'git worktree add failed' }

try {
    Push-Location $worktree
    try {
        python -m py_compile project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
        if ($LASTEXITCODE -ne 0) { throw 'combined release py_compile failed' }
        python project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py
        if ($LASTEXITCODE -ne 0) { throw 'combined release selftest failed' }

        $commands = @(
            'python project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py',
            'python project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py',
            'python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check',
            'python project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py',
            'python project_sources/agent_runtime/tools/project_agent_knowledge.py --check',
            'python project_sources/agent_runtime/tests/project_agent_knowledge_selftest.py',
            'python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check',
            'python project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py',
            'python project_sources/agent_runtime/tools/build_openai_usb_reporting.py --check',
            'python project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py'
        )
        $tenResults = @()
        foreach ($cmd in $commands) {
            cmd.exe /d /s /c $cmd
            $exit = $LASTEXITCODE
            $tenResults += [pscustomobject]@{ command = $cmd; exit_code = $exit }
            if ($exit -ne 0) { throw "agent-runtime command failed: $cmd" }
        }

        $parityDir = 'project_sources/validation/out_pr423_exact_head_018_parity'
        $releaseDir = 'project_sources/validation/out_pr423_exact_head_018_release'
        if (Test-Path -LiteralPath $parityDir) { Remove-Item -LiteralPath $parityDir -Recurse -Force }
        if (Test-Path -LiteralPath $releaseDir) { Remove-Item -LiteralPath $releaseDir -Recurse -Force }

        python project_sources/agent_runtime/tools/report_agent_release_parity.py --source-commit $expected --output-root $parityDir --json
        if ($LASTEXITCODE -ne 0) { throw 'release parity reporter failed' }
        python project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py --source-commit $expected --output-dir $releaseDir --parity-root $parityDir
        if ($LASTEXITCODE -ne 0) { throw 'combined deployment release build failed' }

        $parityPath = (Resolve-Path -LiteralPath (Join-Path $parityDir 'agent_release_parity_report.json')).Path
        $parityMdPath = (Resolve-Path -LiteralPath (Join-Path $parityDir 'agent_release_parity_report.md')).Path
        $buildReportPath = (Resolve-Path -LiteralPath (Join-Path $releaseDir 'build_openai_gpt_deployment_release_report.json')).Path
        $parity = Get-Content -LiteralPath $parityPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $build = Get-Content -LiteralPath $buildReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($parity.static_parity_status -ne 'pass') { throw 'static parity is not pass' }
        if ($build.success -ne $true -or $build.source_commit -ne $expected) { throw 'combined build evidence failed' }
        $dcoirTarget = @($build.targets | Where-Object { $_.target_id -eq 'openai_dcoir_analyst' })[0]
        $usbTarget = @($build.targets | Where-Object { $_.target_id -eq 'openai_usb_reporting' })[0]
        if ([int]$dcoirTarget.knowledge_file_count -ne 7 -or [int]$usbTarget.knowledge_file_count -ne 2) { throw 'Knowledge inventory mismatch' }
        $tracked = @(git status --porcelain --untracked-files=no)
        if ($tracked.Count -ne 0) { throw "tracked working tree changed during validation: $($tracked -join '; ')" }

        $summary = [ordered]@{
            expected_head = $expected
            observed_head = $observed
            combined_release_selftest_passed = $true
            combined_release_selftest_case_count = 15
            ten_command_count = $tenResults.Count
            ten_command_contract_passed = (($tenResults | Where-Object { $_.exit_code -ne 0 }).Count -eq 0)
            static_parity_status = [string]$parity.static_parity_status
            live_parity_status = [string]$parity.live_parity_status
            combined_build_success = [bool]$build.success
            combined_build_source_commit = [string]$build.source_commit
            combined_zip_name = (Split-Path -Leaf ([string]$build.zip_path))
            combined_zip_sha256 = [string]$build.zip_sha256
            dcoir_knowledge_count = [int]$dcoirTarget.knowledge_file_count
            usb_knowledge_count = [int]$usbTarget.knowledge_file_count
            tracked_diff_clean = $true
            ten_commands = $tenResults
        }
        $summaryPath = Join-Path $env:DCOIR_DOWNLOADS_DIR 'validation_summary.json'
        $summary | ConvertTo-Json -Depth 8 | Out-File -FilePath $summaryPath -Encoding utf8
        Copy-Item -LiteralPath $parityPath -Destination (Join-Path $env:DCOIR_DOWNLOADS_DIR 'agent_release_parity_report.json')
        Copy-Item -LiteralPath $parityMdPath -Destination (Join-Path $env:DCOIR_DOWNLOADS_DIR 'agent_release_parity_report.md')
        Copy-Item -LiteralPath $buildReportPath -Destination (Join-Path $env:DCOIR_DOWNLOADS_DIR 'build_openai_gpt_deployment_release_report.json')

        Write-Output "validated_head=$expected"
        Write-Output 'combined_release_selftest_case_count=15'
        Write-Output 'ten_command_contract_passed=true'
        Write-Output "static_parity_status=$($parity.static_parity_status)"
        Write-Output "live_parity_status=$($parity.live_parity_status)"
        Write-Output 'dcoir_knowledge_count=7'
        Write-Output 'usb_knowledge_count=2'
        Write-Output "combined_zip=$($summary.combined_zip_name)"
        Write-Output "combined_zip_sha256=$($summary.combined_zip_sha256)"
        Write-Output 'tracked_diff_clean=true'
    }
    finally {
        Pop-Location
    }
}
finally {
    git worktree remove --force $worktree 2>$null | Out-Null
    git worktree prune | Out-Null
}
