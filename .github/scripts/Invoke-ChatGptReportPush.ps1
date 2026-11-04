param(
  [Parameter(Mandatory=$true)][string]$CommitMessage,
  [Parameter(Mandatory=$true)][string[]]$Paths,
  [object]$MaxAttempts = 5,
  [switch]$RequirePush,
  [Parameter(ValueFromRemainingArguments=$true)][string[]]$ExtraPaths
)

$ErrorActionPreference = 'Continue'

$AllPaths = @()
foreach ($path in $Paths) {
  if (-not [string]::IsNullOrWhiteSpace($path)) { $AllPaths += $path }
}

$MaxAttemptCount = 5
if ($null -ne $MaxAttempts) {
  $parsed = 0
  if ([int]::TryParse([string]$MaxAttempts, [ref]$parsed)) {
    $MaxAttemptCount = $parsed
  } else {
    $AllPaths += [string]$MaxAttempts
  }
}

foreach ($path in $ExtraPaths) {
  if (-not [string]::IsNullOrWhiteSpace($path)) { $AllPaths += $path }
}

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git config core.longpaths true

function Write-ChatGptReportUrls {
  param([string[]]$CandidatePaths)

  $repo = $env:GITHUB_REPOSITORY
  if ([string]::IsNullOrWhiteSpace($repo)) { return }

  $serverUrl = $env:GITHUB_SERVER_URL
  if ([string]::IsNullOrWhiteSpace($serverUrl)) { $serverUrl = 'https://github.com' }

  $reportPaths = @()
  foreach ($candidate in $CandidatePaths) {
    if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
    $normalized = ([string]$candidate).Trim() -replace '\\','/'
    if ($normalized -eq 'workflow_report.md' -or $normalized.EndsWith('/workflow_report.md')) {
      $reportPaths += $normalized
      continue
    }
    if (Test-Path -LiteralPath $normalized -PathType Container) {
      $foundReports = Get-ChildItem -LiteralPath $normalized -Recurse -File -Filter 'workflow_report.md' |
        ForEach-Object { $_.FullName.Substring((Get-Location).Path.Length).TrimStart('\','/') -replace '\\','/' }
      $reportPaths += $foundReports
    }
  }

  $reportPaths = @($reportPaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
  if ($reportPaths.Count -eq 0) { return }

  if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    "## ChatGPT workflow report" | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Encoding utf8 -Append
  }
  foreach ($reportPath in $reportPaths) {
    $url = "$serverUrl/$repo/blob/main/$reportPath"
    Write-Host "ChatGPT workflow report: $url"
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
      $url | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Encoding utf8 -Append
    }
  }
}

$ExpandedPaths = @()
foreach ($path in $AllPaths) {
  foreach ($item in ($path -split '\|')) {
    if (-not [string]::IsNullOrWhiteSpace($item)) {
      $normalized = ([string]$item).Trim() -replace '\\','/'
      if (-not [string]::IsNullOrWhiteSpace($normalized)) { $ExpandedPaths += $normalized }
    }
  }
}
$ExpandedPaths = @($ExpandedPaths | Select-Object -Unique)

if ($ExpandedPaths.Count -eq 0) {
  Write-Host "No report paths supplied for: $CommitMessage"
  if ($RequirePush) {
    throw "Required report push had no paths to stage for: $CommitMessage"
  }
  exit 0
}

Write-Host "Staging report paths for: $CommitMessage"
foreach ($path in $ExpandedPaths) { Write-Host "  $path" }

$StagePaths = @()
foreach ($pathToStage in $ExpandedPaths) {
  $tracked = & git -c core.longpaths=true ls-files --error-unmatch -- $pathToStage 2>$null
  $isTracked = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($tracked | Out-String)))

  if ($isTracked) {
    $StagePaths += $pathToStage
    continue
  }

  if (Test-Path -LiteralPath $pathToStage) {
    & git -c core.longpaths=true check-ignore -q -- $pathToStage 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Skipping ignored untracked report path: $pathToStage"
      continue
    }
    $StagePaths += $pathToStage
    continue
  }

  Write-Host "Skipping absent untracked report path: $pathToStage"
}

$StagePaths = @($StagePaths | Select-Object -Unique)
if ($StagePaths.Count -eq 0) {
  Write-Host "No existing or tracked report paths to stage for: $CommitMessage"
  if ($RequirePush) {
    throw "Required report push had no stageable paths for: $CommitMessage"
  }
  exit 0
}

# Some callers, including ChatGPT Apply-In, stage approved product files before
# invoking this helper with report paths. Preserve those explicitly staged
# changes; the original git commit published both groups.
$CallerStagedPaths = @(& git -c core.longpaths=true -c core.quotepath=false diff --cached --no-renames --name-only)
if ($LASTEXITCODE -ne 0) {
  throw 'Cannot inspect pre-staged caller changes; refusing report publication.'
}
$CallerStagedPaths = @($CallerStagedPaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
if ($CallerStagedPaths.Count -gt 0) {
  # The temporary index uses file contents from the worktree. Reject an
  # unstaged mutation that differs from the caller-approved staged snapshot.
  & git -c core.longpaths=true diff --quiet -- @CallerStagedPaths
  if ($LASTEXITCODE -ne 0) {
    throw 'Unstaged changes differ from the caller-approved index; refusing report publication.'
  }
}
# Preserve the exact caller-approved index blob/mode or deletion before
# entering the temporary index. Worktree paths are not a staging contract.
$CallerApprovedIndex = @{}
foreach ($callerPath in $CallerStagedPaths) {
  $entries = @(& git -c core.longpaths=true -c core.quotepath=false ls-files --stage -- $callerPath)
  if ($LASTEXITCODE -ne 0 -or $entries.Count -gt 1) {
    throw "Cannot inspect caller-approved staged entry: $callerPath"
  }
  foreach ($reportPath in $StagePaths) {
    if ($callerPath -eq $reportPath -or $callerPath.StartsWith(($reportPath.TrimEnd('/') + '/'), [StringComparison]::Ordinal)) {
      throw "Caller-staged paths cannot overlap report publishing paths: $callerPath"
    }
  }
  if ($entries.Count -eq 0) {
    if (Test-Path -LiteralPath $callerPath) {
      throw "Staged deletion was recreated in the worktree: $callerPath"
    }
    $CallerApprovedIndex[$callerPath] = $null
  } else {
    if ([string]$entries[0] -notmatch '^([0-7]{6}) ([0-9a-f]{40,64}) 0\t') {
      throw "Cannot parse caller-approved index entry: $callerPath"
    }
    $CallerApprovedIndex[$callerPath] = @{ Mode = $Matches[1]; Blob = $Matches[2] }
  }
}

# A request can publish multiple report phases from one runner while main moves.
# Never rebase this runner's prior report commits onto main: that can replay
# already-published files as add/add conflicts. Instead build a report-only
# commit on the newly fetched main tree with an isolated index each attempt.
# Record exact published report evidence in a local ref scoped by request
# and workflow run/job. Another publisher must not authorize our stale copy.
$ReportRoots = @()
foreach ($candidate in $StagePaths) {
  $rootMatch = [regex]::Match([string]$candidate, '^\.github/chatgpt_staging/status_reports/[^/]+/[^/]+')
  if ($rootMatch.Success) { $ReportRoots += $rootMatch.Value }
}
$ReportRoots = @($ReportRoots | Select-Object -Unique)
if ($ReportRoots.Count -ne 1) {
  throw 'Report publication needs exactly one request-scoped report root.'
}
$observedIdentity = @($env:GITHUB_RUN_ID, $env:GITHUB_RUN_ATTEMPT, $env:GITHUB_JOB, $ReportRoots[0]) -join '|'
$shaTool = [Security.Cryptography.SHA256]::Create()
try {
  $observedId = ([BitConverter]::ToString(
    $shaTool.ComputeHash([Text.Encoding]::UTF8.GetBytes($observedIdentity))
  )).Replace('-', '').ToLowerInvariant()
} finally {
  $shaTool.Dispose()
}
$ObservedReportRef = "refs/dcoir-report-push/last-published/$observedId"
$ObservedReportCommit = [string](& git rev-parse --verify $ObservedReportRef 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ObservedReportCommit)) {
  $ObservedReportCommit = 'HEAD'
} else {
  $ObservedReportCommit = $ObservedReportCommit.Trim()
}

function Test-PublishedProgressIsPreserved {
  param([string]$RemoteHead, [string[]]$CandidatePaths, [string]$ObservedCommit)

  $remoteFiles = @(& git -c core.longpaths=true ls-tree -r --name-only $RemoteHead -- @CandidatePaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect committed report history on main.'
    return $false
  }
  $baseFiles = @(& git -c core.longpaths=true ls-tree -r --name-only HEAD -- @CandidatePaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect report files from the checkout base.'
    return $false
  }
  $remoteFileSet = @{}
  foreach ($path in $remoteFiles) { $remoteFileSet[[string]$path] = $true }
  $baseFileSet = @{}
  foreach ($path in $baseFiles) { $baseFileSet[[string]$path] = $true }

  # Include the last version published by this runner: HEAD may predate every
  # report file, while a later runner can explicitly delete published history.
  # Never silently resurrect history deleted from main with git add -A.
  $observedFiles = @(& git -c core.longpaths=true ls-tree -r --name-only $ObservedCommit -- @CandidatePaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect previously observed progress history.'
    return $false
  }
  $knownHistoryPaths = @($baseFiles + $observedFiles |
    Where-Object {
      ([string]$_).StartsWith('.github/chatgpt_staging/status_reports/', [StringComparison]::OrdinalIgnoreCase) -and
      [IO.Path]::GetFileName([string]$_) -eq 'progress_history.jsonl'
    } | Select-Object -Unique)
  foreach ($historyPath in $knownHistoryPaths) {
    if (-not $remoteFileSet.ContainsKey([string]$historyPath)) {
      Write-Warning "Previously tracked progress history was deleted on main; refusing to recreate it: $historyPath"
      return $false
    }
  }

  # A runner can have published summaries absent from checkout HEAD. If main
  # subsequently deletes one, never re-create stale evidence from the worktree.
  $knownReportPaths = @($baseFiles + $observedFiles |
    Where-Object {
      ([string]$_).StartsWith('.github/chatgpt_staging/status_reports/', [StringComparison]::OrdinalIgnoreCase) -and
      [IO.Path]::GetFileName([string]$_) -ne 'progress_history.jsonl'
    } | Select-Object -Unique)
  foreach ($reportPath in $knownReportPaths) {
    if ((-not $remoteFileSet.ContainsKey([string]$reportPath)) -and
        (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
      Write-Warning "Previously published report was deleted on main; refusing to recreate it: $reportPath"
      return $false
    }
  }

  foreach ($remotePath in $remoteFiles) {
    if ([IO.Path]::GetFileName([string]$remotePath) -ne 'progress_history.jsonl') { continue }
    if (-not (Test-Path -LiteralPath $remotePath -PathType Leaf)) {
      Write-Warning "Refusing to remove published progress history: $remotePath"
      return $false
    }
    $remoteLines = @(& git -c core.longpaths=true show ($RemoteHead + ':' + $remotePath) 2>$null)
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "Cannot read published progress history: $remotePath"
      return $false
    }
    $localLines = @(Get-Content -LiteralPath $remotePath -Encoding UTF8)
    if ($remoteLines.Count -gt $localLines.Count) {
      Write-Warning "Local progress history omits previously published entries: $remotePath"
      return $false
    }
    for ($line = 0; $line -lt $remoteLines.Count; $line++) {
      if ($remoteLines[$line] -cne $localLines[$line]) {
        Write-Warning "Divergent progress history requires reconciliation before push: $remotePath"
        return $false
      }
    }
  }

  $reportPaths = @($remoteFiles + $baseFiles |
    Where-Object {
      ([string]$_).StartsWith('.github/chatgpt_staging/status_reports/', [StringComparison]::OrdinalIgnoreCase) -and
      [IO.Path]::GetFileName([string]$_) -ne 'progress_history.jsonl'
    } |
    Select-Object -Unique)
  foreach ($reportPath in $reportPaths) {
    $remoteHash = ''
    if ($remoteFileSet.ContainsKey([string]$reportPath)) {
      $remoteHash = [string](& git -c core.longpaths=true rev-parse --verify "$($RemoteHead):$reportPath" 2>$null)
      if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($remoteHash)) {
        Write-Warning "Cannot read published report version: $reportPath"
        return $false
      }
      $remoteHash = $remoteHash.Trim()
    }

    $baseHash = ''
    if ($baseFileSet.ContainsKey([string]$reportPath)) {
      $baseHash = [string](& git -c core.longpaths=true rev-parse --verify "HEAD:$reportPath" 2>$null)
      if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($baseHash)) {
        Write-Warning "Cannot read checkout-base report version: $reportPath"
        return $false
      }
      $baseHash = $baseHash.Trim()
    }

    # Remote content must have been present at checkout or published/observed
    # by this exact runner. The rule also applies to explicit file deletions.
    $observedPaths = @(& git -c core.longpaths=true ls-tree -r --name-only $ObservedCommit -- $reportPath)
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "Cannot inspect previously observed report state: $reportPath"
      return $false
    }
    $observedHash = ''
    if ($observedPaths -contains $reportPath) {
      $observedHash = [string](& git -c core.longpaths=true rev-parse --verify "$($ObservedCommit):$reportPath" 2>$null)
      if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($observedHash)) {
        Write-Warning "Cannot read previously observed report blob: $reportPath"
        return $false
      }
      $observedHash = $observedHash.Trim()
    }

    $localHash = ''
    if (Test-Path -LiteralPath $reportPath -PathType Leaf) {
      $localHash = [string](& git -c core.longpaths=true hash-object "--path=$reportPath" -- $reportPath 2>$null)
      if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($localHash)) {
        Write-Warning "Cannot read local report version: $reportPath"
        return $false
      }
      $localHash = $localHash.Trim()
    } else {
      # A named deletion must not erase a remote version unknown to this runner.
      if (($CandidatePaths -contains $reportPath) -and $remoteHash -ne '' -and $remoteHash -ne $baseHash -and $remoteHash -ne $observedHash) {
        Write-Warning "Unobserved remote report content cannot be deleted: $reportPath"
        return $false
      }
      continue
    }

    if ($localHash -eq $remoteHash -or $remoteHash -eq $baseHash -or $remoteHash -eq $observedHash) { continue }

    Write-Warning "Unobserved remote report content requires reconciliation before push: $reportPath"
    return $false
  }
  return $true
}

# Staging a directory from a stale runner against a newer main must not delete
# tracked summaries published by other phases and absent from this checkout.
# Only explicitly named file paths (such as final request cleanup) may delete.
function Restore-RemoteOnlyReportFiles {
  param([string]$RemoteHead, [string[]]$CandidatePaths)

  $deletedPaths = @(& git -c core.longpaths=true diff --cached --name-only --diff-filter=D $RemoteHead -- @CandidatePaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect staged report deletions.'
    return $false
  }
  foreach ($deletedPath in $deletedPaths) {
    if ($CandidatePaths -contains $deletedPath) { continue }
    & git -c core.longpaths=true reset -q $RemoteHead -- $deletedPath
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "Could not preserve remote-only report file: $deletedPath"
      return $false
    }
  }
  return $true
}

# Verify ALL non-status staged tracked paths against the checkout base before
# publishing a candidate constructed on freshly fetched main. git add -A can
# otherwise reintroduce stale tracked content or delete newer tracked payloads.
# Status report files have separate history/causal checks above.
function Test-NonReportStagedPathsSafe {
  param([string]$RemoteHead, [string[]]$CandidatePaths)

  $nonReportPaths = @($CandidatePaths | Where-Object {
    $path = ([string]$_).TrimEnd('/')
    -not ($path -eq '.github/chatgpt_staging/status_reports' -or
      $path.StartsWith('.github/chatgpt_staging/status_reports/', [StringComparison]::OrdinalIgnoreCase))
  })
  if ($nonReportPaths.Count -eq 0) { return $true }

  # Tree-to-tree changes identify remotely modified, added, or deleted paths.
  $remoteChangedPaths = @(& git -c core.longpaths=true -c core.quotepath=false diff --no-renames --name-only HEAD $RemoteHead -- @nonReportPaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect remote changes under non-report staged paths.'
    return $false
  }
  if ($remoteChangedPaths.Count -eq 0) { return $true }

  # This runs with the temporary index in scope, AFTER remote-only files have
  # been restored. A path changed on main is safe only if the staged candidate
  # preserves exactly the remote tree entry (including deletion).
  $candidateChanges = @(& git -c core.longpaths=true -c core.quotepath=false diff --cached --no-renames --name-only $RemoteHead -- @nonReportPaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect staged changes under non-report staged paths.'
    return $false
  }
  $candidateChangedSet = @{}
  foreach ($path in $candidateChanges) { $candidateChangedSet[[string]$path] = $true }
  foreach ($path in $remoteChangedPaths) {
    if ($candidateChangedSet.ContainsKey([string]$path)) {
      Write-Warning "Concurrent tracked file change requires reconciliation before push: $path"
      return $false
    }
  }
  return $true
}


for ($attempt = 1; $attempt -le $MaxAttemptCount; $attempt++) {
  Write-Host "Report push attempt $attempt of $MaxAttemptCount for: $CommitMessage"
  & git -c core.longpaths=true fetch origin main
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "git fetch failed on attempt $attempt."
    Start-Sleep -Seconds ([Math]::Min(30, 5 * $attempt))
    continue
  }
  $remoteHead = [string](& git rev-parse --verify FETCH_HEAD)
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($remoteHead)) {
    Write-Warning "Could not determine fetched main on attempt $attempt."
    continue
  }
  $remoteHead = $remoteHead.Trim()
  if (-not (Test-PublishedProgressIsPreserved -RemoteHead $remoteHead -CandidatePaths $StagePaths -ObservedCommit $ObservedReportCommit)) {
    Write-Warning 'Refusing a report push that would discard published progress history.'
    if ($RequirePush) { throw 'Required report push could not preserve published progress history.' }
    exit 0
  }

  if ($CallerStagedPaths.Count -gt 0) {
    $overlap = @(& git -c core.longpaths=true -c core.quotepath=false diff --no-renames --name-only HEAD $remoteHead -- @CallerStagedPaths)
    if ($LASTEXITCODE -ne 0 -or $overlap.Count -gt 0) {
      $message = "Main changed pre-staged caller paths since checkout; refusing to overwrite: $($overlap -join ', ')"
      throw $message
    }
  }

  $tempIndex = Join-Path ([IO.Path]::GetTempPath()) ('dcoir-report-index-' + [guid]::NewGuid().ToString('N'))
  $previousIndex = $env:GIT_INDEX_FILE
  $hadIndex = Test-Path Env:GIT_INDEX_FILE
  $candidateCommit = ''
  $stageOutcome = 'failure'
  try {
    $env:GIT_INDEX_FILE = $tempIndex
    & git -c core.longpaths=true read-tree $remoteHead
    if ($LASTEXITCODE -eq 0) {
      & git -c core.longpaths=true add -A -- @StagePaths
      if ($LASTEXITCODE -eq 0 -and (Restore-RemoteOnlyReportFiles -RemoteHead $remoteHead -CandidatePaths $StagePaths) -and (Test-NonReportStagedPathsSafe -RemoteHead $remoteHead -CandidatePaths $StagePaths)) {
        $callerIndexApplied = $true
        foreach ($callerPath in $CallerStagedPaths) {
          $entry = $CallerApprovedIndex[$callerPath]
          if ($null -eq $entry) {
            & git -c core.longpaths=true update-index --force-remove -- $callerPath
          } else {
            $cacheinfo = "$($entry.Mode),$($entry.Blob),$callerPath"
            & git -c core.longpaths=true update-index --add --cacheinfo $cacheinfo
          }
          if ($LASTEXITCODE -ne 0) {
            Write-Warning "Cannot apply approved caller index state: $callerPath"
            $callerIndexApplied = $false
            break
          }
        }
        if ($callerIndexApplied) {
          & git -c core.longpaths=true diff --cached --quiet $remoteHead --
          $diffExit = $LASTEXITCODE
          if ($diffExit -eq 0) {
            $stageOutcome = 'no_changes'
          } elseif ($diffExit -eq 1) {
            $tree = [string](& git -c core.longpaths=true write-tree)
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($tree)) {
              $tree = $tree.Trim()
              $candidateCommit = [string](& git -c core.longpaths=true commit-tree $tree -p $remoteHead -m $CommitMessage)
              if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($candidateCommit)) {
                $candidateCommit = $candidateCommit.Trim()
                $stageOutcome = 'ready'
              }
            }
          }
        }
      }
    }
  } finally {
    if ($hadIndex) { $env:GIT_INDEX_FILE = $previousIndex }
    else { Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $tempIndex -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath ($tempIndex + '.lock') -Force -ErrorAction SilentlyContinue
  }

  if ($stageOutcome -eq 'no_changes') {
    Write-Host "No new report changes relative to fetched main for: $CommitMessage"
    if ($RequirePush) {
      throw "Required report push had no changes to publish for: $CommitMessage"
    }
    exit 0
  }
  if ($stageOutcome -ne 'ready') {
    Write-Warning "Could not prepare report-only commit on attempt $attempt."
    Start-Sleep -Seconds ([Math]::Min(30, 5 * $attempt))
    continue
  }

  # A concurrent advance of main rejects this non-forced push. Refetch and
  # reconstruct only the approved report paths rather than replaying commits.
  & git -c core.longpaths=true push origin ($candidateCommit + ':refs/heads/main')
  if ($LASTEXITCODE -eq 0) {
    & git update-ref $ObservedReportRef $candidateCommit
    if ($LASTEXITCODE -ne 0) {
      Write-Warning 'Report was published, but the runner-observed ref was not recorded; a later unobserved publication will fail closed.'
    }
    Write-Host "Report push succeeded on attempt $attempt."
    Write-ChatGptReportUrls -CandidatePaths $StagePaths
    exit 0
  }
  Write-Warning "git push failed on attempt $attempt; rebuilding from latest main."
  Start-Sleep -Seconds ([Math]::Min(30, 5 * $attempt))
}

Write-Warning "Report push failed after $MaxAttemptCount attempts."
if ($RequirePush) { throw "Required report push failed after $MaxAttemptCount attempts." }
exit 0
