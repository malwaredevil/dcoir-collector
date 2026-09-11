$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$requestId = 'issue548-pr549-response-read-regression-fix-001'
$targetBranch = 'fix/issue-548-provider-transport-retry'
$expectedHead = '6d068c50306a4ac7701203351cd7a271fbc6a9d9'
$reviewedBase = 'd7b44e227176cdbbd90ff06d6f684d1b9f95b0d4'
$expectedCommandCount = 58
$targetPath = '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py'
$repoRoot = (Get-Location).Path
$worktree = Join-Path $env:RUNNER_TEMP $requestId
$summaryDir = Join-Path $repoRoot ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
$summaryPath = Join-Path $summaryDir 'validation-summary.md'
$result = 'failure'
$failureMessage = ''
$remoteHeadBefore = ''
$newHead = ''
$remoteHeadAfter = ''
$mergeBase = ''
$successfulCommandCount = 0
$compiledPythonCount = 0
$credentialsRemoved = $false
$prDiffCheckPassed = $false
$finalWorktreeClean = $false
$pushPerformed = $false

$credentialNames = @(
    'DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY',
    'OPENROUTER_API_KEY','DCOIR_OPENROUTER_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','GEMINI_API_KEY',
    'DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN'
)

$changedPythonFiles = @(
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py',
    '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v58.py'
)

function Invoke-CheckedNative {
    param([Parameter(Mandatory=$true)][string]$Label,[Parameter(Mandatory=$true)][scriptblock]$Action)
    Write-Host "==> $Label"
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

function Replace-ExactlyOnce {
    param(
        [Parameter(Mandatory=$true)][string]$Text,
        [Parameter(Mandatory=$true)][string]$Old,
        [Parameter(Mandatory=$true)][string]$New,
        [Parameter(Mandatory=$true)][string]$Label
    )
    $count = $Text.Split(@($Old), [StringSplitOptions]::None).Count - 1
    if ($count -ne 1) { throw "$Label expected exactly once; observed $count occurrences" }
    return $Text.Replace($Old, $New)
}

function Write-ValidationSummary {
    New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
    $safeFailure = ($failureMessage -replace '[\r\n]+',' ').Trim()
    @(
        '# PR #549 response.read regression repair + exact-head validation summary','',
        "- request_id: $requestId",
        "- result: $result",
        "- target_branch: $targetBranch",
        "- expected_remote_head_before: $expectedHead",
        "- observed_remote_head_before: $remoteHeadBefore",
        "- reviewed_base_sha: $reviewedBase",
        "- reviewed_base_merge_base_with_new_head: $mergeBase",
        "- locally_committed_validated_head_sha: $newHead",
        "- remote_branch_head_after_push: $remoteHeadAfter",
        "- changed_python_files_expected: $($changedPythonFiles.Count)",
        "- changed_python_files_compiled: $compiledPythonCount",
        "- governed_validation_commands_expected: $expectedCommandCount",
        "- governed_validation_commands_passed: $successfulCommandCount",
        "- provider_and_github_secret_env_removed_before_validation: $($credentialsRemoved.ToString().ToLowerInvariant())",
        "- pr_range_git_diff_check_passed: $($prDiffCheckPassed.ToString().ToLowerInvariant())",
        "- final_worktree_clean: $($finalWorktreeClean.ToString().ToLowerInvariant())",
        "- source_branch_push_performed: $($pushPerformed.ToString().ToLowerInvariant())",
        '- source_change_scope: test-only correction so the #548 regression raises IncompleteRead from FakeResponse.read after urlopen returns a response; production v58 code unchanged',
        '- live_dcoir_review_invocation: false',
        '- live_model_provider_calls: false',
        '- ready_transition: false',
        '- merge_performed: false',
        "- failure: $safeFailure"
    ) | Out-File -LiteralPath $summaryPath -Encoding utf8
}

try {
    if (Test-Path -LiteralPath $worktree) {
        $old = $ErrorActionPreference; $ErrorActionPreference='SilentlyContinue'
        & git worktree remove --force $worktree 2>$null | Out-Null
        $ErrorActionPreference=$old
        if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force }
    }

    Invoke-CheckedNative 'Fetch source branch' { git fetch --no-tags origin "refs/heads/${targetBranch}:refs/remotes/origin/${targetBranch}" }
    $remoteHeadBefore = (git rev-parse "refs/remotes/origin/$targetBranch").Trim()
    if ($remoteHeadBefore -ne $expectedHead) { throw "Remote branch drifted: expected $expectedHead but observed $remoteHeadBefore" }

    Invoke-CheckedNative 'Create detached repair worktree' { git worktree add --detach $worktree $expectedHead }
    Push-Location $worktree
    try {
        $file = Join-Path (Get-Location).Path $targetPath
        $text = [IO.File]::ReadAllText($file).Replace("`r`n", "`n")

        $oldFake = @'
class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._raw
'@
        $newFake = @'
class FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        read_error: Exception | None = None,
    ) -> None:
        if payload is None and read_error is None:
            raise ValueError("fake response requires payload or read_error")
        self._raw = (
            json.dumps(payload).encode("utf-8") if payload is not None else b""
        )
        self._read_error = read_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        if self._read_error is not None:
            raise self._read_error
        return self._raw
'@
        $text = Replace-ExactlyOnce $text $oldFake $newFake 'FakeResponse replacement'

        $oldInstall = @'
        item = remaining.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)
'@
        $newInstall = @'
        item = remaining.pop(0)
        if isinstance(item, FakeResponse):
            return item
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)
'@
        $text = Replace-ExactlyOnce $text $oldInstall $newInstall 'install_sequence replacement'

        $oldPrimary = '                http.client.IncompleteRead(partial, len(partial) + 10),'
        $newPrimary = @'
                FakeResponse(
                    read_error=http.client.IncompleteRead(
                        partial, len(partial) + 10
                    )
                ),
'@.TrimEnd("`r","`n")
        $text = Replace-ExactlyOnce $text $oldPrimary $newPrimary 'primary response.read failure replacement'

        $oldDirect = '            [http.client.IncompleteRead(b"direct-partial", 30)],'
        $newDirect = @'
            [
                FakeResponse(
                    read_error=http.client.IncompleteRead(b"direct-partial", 30)
                )
            ],
'@.TrimEnd("`r","`n")
        $text = Replace-ExactlyOnce $text $oldDirect $newDirect 'direct response.read failure replacement'

        $oldProd = '                http.client.IncompleteRead(b"prod-partial", 99),'
        $newProd = @'
                FakeResponse(
                    read_error=http.client.IncompleteRead(b"prod-partial", 99)
                ),
'@.TrimEnd("`r","`n")
        $text = Replace-ExactlyOnce $text $oldProd $newProd 'production wrapper response.read failure replacement'

        $oldComment = @'
        # Exact production failure shape: an incomplete chunked response on the
        # first attempt followed by a clean same-model response. The partial bytes
        # contain valid-looking JSON and must never be parsed as model output.
'@
        $newComment = @'
        # Exact production failure shape: urlopen returns a response object and
        # response.read() raises IncompleteRead on the first attempt, followed by a
        # clean same-model response. The partial bytes contain valid-looking JSON
        # and must never be parsed as model output.
'@
        $text = Replace-ExactlyOnce $text $oldComment $newComment 'production failure comment replacement'

        [IO.File]::WriteAllText($file,$text,(New-Object Text.UTF8Encoding($false)))

        Invoke-CheckedNative 'git diff --check after regression repair' { git diff --check }
        $changed = @(git diff --name-only)
        if ($changed.Count -ne 1 -or $changed[0] -ne $targetPath) { throw "Repair touched unexpected paths: $($changed -join ', ')" }

        git config user.name 'chatgpt-exec'
        git config user.email 'chatgpt-exec@users.noreply.github.com'
        git add -- $targetPath
        Invoke-CheckedNative 'Commit response.read regression repair' { git commit -m 'test(dcoir): exercise incomplete read at response boundary' }
        $newHead = (git rev-parse HEAD).Trim()

        $mergeBase = (git merge-base $reviewedBase $newHead).Trim()
        if ($LASTEXITCODE -ne 0 -or $mergeBase -ne $reviewedBase) { throw "Reviewed base is not merge-base ancestor of new head: $mergeBase" }

        $env:PYTHONDONTWRITEBYTECODE='1'
        foreach ($name in $credentialNames) { Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue }
        foreach ($name in $credentialNames) { if (Test-Path -Path "Env:$name") { throw "Credential env remained available: $name" } }
        $credentialsRemoved=$true

        $pythonExe = if (Get-Command python3 -ErrorAction SilentlyContinue) {'python3'} elseif (Get-Command python -ErrorAction SilentlyContinue) {'python'} else { throw 'Neither python3 nor python is available.' }

        Invoke-CheckedNative 'git diff --check reviewed PR range' { git diff --check "$reviewedBase...$newHead" }
        $prDiffCheckPassed=$true

        foreach ($path in $changedPythonFiles) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Changed Python file missing: $path" }
            Invoke-CheckedNative "py_compile $path" { & $pythonExe -m py_compile $path }
            $compiledPythonCount++
        }

        $lines = Get-Content -LiteralPath '.github/dcoir_review/openrouter-pr-review-pareto.yml'
        $commands = New-Object System.Collections.Generic.List[string]
        $inside=$false
        foreach ($line in $lines) {
            if ($line -eq 'validation_commands:') { $inside=$true; continue }
            if (-not $inside) { continue }
            if ($line -match '^[A-Za-z0-9_].*:$') { break }
            if ($line -match '^  - (.+)$') { [void]$commands.Add($Matches[1]) }
        }
        if ($commands.Count -ne $expectedCommandCount) { throw "Expected $expectedCommandCount validation commands; found $($commands.Count)" }

        $index=0
        foreach ($command in $commands) {
            $index++
            $execCommand=$command
            if ($pythonExe -eq 'python' -and $execCommand -match '^python3\s+') { $execCommand=$execCommand -replace '^python3\s+','python ' }
            Write-Host ("[{0:D2}/{1}] {2}" -f $index,$expectedCommandCount,$execCommand)
            cmd.exe /d /s /c $execCommand
            if ($LASTEXITCODE -ne 0) { throw "Governed validation command $index failed with exit code ${LASTEXITCODE}: $execCommand" }
            $successfulCommandCount++
        }

        $status=@(git status --porcelain)
        if ($status.Count -ne 0) { throw "Validated committed worktree became dirty: $($status -join '; ')" }
        $finalWorktreeClean=$true

        Invoke-CheckedNative 'Push validated regression repair to source branch' { git push origin "${newHead}:refs/heads/${targetBranch}" }
        $pushPerformed=$true
        Invoke-CheckedNative 'Refresh source branch after push' { git fetch --no-tags origin "refs/heads/${targetBranch}:refs/remotes/origin/${targetBranch}" }
        $remoteHeadAfter=(git rev-parse "refs/remotes/origin/$targetBranch").Trim()
        if ($remoteHeadAfter -ne $newHead) { throw "Post-push branch mismatch: expected $newHead observed $remoteHeadAfter" }

        $result='pass'
        Write-Host 'VALIDATION_RECEIPT_BEGIN'
        Write-Host "reviewed_base_sha=$reviewedBase"
        Write-Host "validated_head_sha=$newHead"
        Write-Host "remote_branch_head_after=$remoteHeadAfter"
        Write-Host "changed_python_files_compiled=$compiledPythonCount"
        Write-Host "governed_validation_commands_passed=$successfulCommandCount"
        Write-Host 'governed_validation_result=pass'
        Write-Host 'final_worktree_clean=true'
        Write-Host 'live_dcoir_review_invocation=false'
        Write-Host 'live_model_provider_calls=false'
        Write-Host 'VALIDATION_RECEIPT_END'
    }
    finally { Pop-Location }
}
catch {
    $failureMessage=$_.Exception.Message
    Write-Host "VALIDATION_FAILURE: $failureMessage"
    throw
}
finally {
    Set-Location $repoRoot
    if (Test-Path -LiteralPath $worktree) {
        $old=$ErrorActionPreference; $ErrorActionPreference='SilentlyContinue'
        & git worktree remove --force $worktree 2>$null | Out-Null
        $ErrorActionPreference=$old
        if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Write-ValidationSummary
}
