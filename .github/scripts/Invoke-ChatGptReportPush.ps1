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
    Write-Error "Required report push had no paths to stage for: $CommitMessage"
    exit 1
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
    Write-Error "Required report push had no stageable paths for: $CommitMessage"
    exit 1
  }
  exit 0
}

# Some callers, including ChatGPT Apply-In, stage approved product files before
# invoking this helper with report paths. Preserve those explicitly staged
# changes; the original git commit published both groups.
$CallerStagedPaths = @(& git -c core.longpaths=true -c core.quotepath=false diff --cached --no-renames --name-only)
if ($LASTEXITCODE -ne 0) {
  Write-Error 'Cannot inspect pre-staged caller changes; refusing report publication.'
  exit 1
}
$CallerStagedPaths = @($CallerStagedPaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
if ($CallerStagedPaths.Count -gt 0) {
  # The temporary index uses file contents from the worktree. Reject an
  # unstaged mutation that differs from the caller-approved staged snapshot.
  & git -c core.longpaths=true diff --quiet -- @CallerStagedPaths
  if ($LASTEXITCODE -ne 0) {
    Write-Error 'Unstaged changes differ from the caller-approved index; refusing report publication.'
    exit 1
  }
}
$CommitPaths = @($StagePaths + $CallerStagedPaths | Select-Object -Unique)

# A request can publish multiple report phases from one runner while main moves.
# Never rebase this runner's prior report commits onto main: that can replay
# already-published files as add/add conflicts. Instead build a report-only
# commit on the newly fetched main tree with an isolated index each attempt.
function Get-ReportArtifactTimestamp {
  param([string]$Path, [string]$Content)

  $timestampText = ''
  switch ([IO.Path]::GetFileName($Path)) {
    'workflow_report.md' {
      $match = [regex]::Match($Content, '(?m)^- report_updated_utc:\s*(\S+)\s*$')
      if ($match.Success) { $timestampText = $match.Groups[1].Value }
    }
    'latest_progress_marker.json' {
      try { $timestampText = [string](ConvertFrom-Json -InputObject $Content -ErrorAction Stop).updated_utc }
      catch { return $null }
    }
    'final_readback_marker.json' {
      try { $timestampText = [string](ConvertFrom-Json -InputObject $Content -ErrorAction Stop).created_utc }
      catch { return $null }
    }
    default { return $null }
  }

  $timestamp = [DateTimeOffset]::MinValue
  if ([string]::IsNullOrWhiteSpace($timestampText) -or
      -not [DateTimeOffset]::TryParse(
        $timestampText,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal,
        [ref]$timestamp
      )) {
    return $null
  }
  return $timestamp
}

function Test-PublishedProgressIsPreserved {
  param([string]$RemoteHead, [string[]]$CandidatePaths)

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

    $localHash = ''
    $localContent = ''
    if (Test-Path -LiteralPath $reportPath -PathType Leaf) {
      $localHash = [string](& git -c core.longpaths=true hash-object "--path=$reportPath" -- $reportPath 2>$null)
      if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($localHash)) {
        Write-Warning "Cannot read local report version: $reportPath"
        return $false
      }
      $localHash = $localHash.Trim()
      $localContent = [string](Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8)
    } else {
      continue
    }

    if ($localHash -eq $remoteHash -or $remoteHash -eq $baseHash) { continue }

    $remoteContentLines = @(& git -c core.longpaths=true show "$($RemoteHead):$reportPath" 2>$null)
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "Cannot read published report content: $reportPath"
      return $false
    }
    $remoteContent = $remoteContentLines -join "`n"
    $localTimestamp = Get-ReportArtifactTimestamp -Path $reportPath -Content $localContent
    $remoteTimestamp = Get-ReportArtifactTimestamp -Path $reportPath -Content $remoteContent
    if ($null -ne $localTimestamp -and $null -ne $remoteTimestamp -and $localTimestamp -gt $remoteTimestamp) {
      continue
    }

    Write-Warning "Divergent published report requires reconciliation before push: $reportPath"
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
  if (-not (Test-PublishedProgressIsPreserved -RemoteHead $remoteHead -CandidatePaths $StagePaths)) {
    Write-Warning 'Refusing a report push that would discard published progress history.'
    if ($RequirePush) { exit 1 }
    exit 0
  }

  if ($CallerStagedPaths.Count -gt 0) {
    $overlap = @(& git -c core.longpaths=true -c core.quotepath=false diff --no-renames --name-only HEAD $remoteHead -- @CallerStagedPaths)
    if ($LASTEXITCODE -ne 0 -or $overlap.Count -gt 0) {
      Write-Error "Main changed pre-staged caller paths since checkout; refusing to overwrite: $($overlap -join ', ')"
      exit 1
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
      & git -c core.longpaths=true add -A -- @CommitPaths
      if ($LASTEXITCODE -eq 0 -and (Restore-RemoteOnlyReportFiles -RemoteHead $remoteHead -CandidatePaths $CommitPaths)) {
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
  } finally {
    if ($hadIndex) { $env:GIT_INDEX_FILE = $previousIndex }
    else { Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $tempIndex -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath ($tempIndex + '.lock') -Force -ErrorAction SilentlyContinue
  }

  if ($stageOutcome -eq 'no_changes') {
    Write-Host "No new report changes relative to fetched main for: $CommitMessage"
    if ($RequirePush) {
      Write-Error "Required report push had no changes to publish for: $CommitMessage"
      exit 1
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
    Write-Host "Report push succeeded on attempt $attempt."
    Write-ChatGptReportUrls -CandidatePaths $StagePaths
    exit 0
  }
  Write-Warning "git push failed on attempt $attempt; rebuilding from latest main."
  Start-Sleep -Seconds ([Math]::Min(30, 5 * $attempt))
}

Write-Warning "Report push failed after $MaxAttemptCount attempts."
if ($RequirePush) { exit 1 }
exit 0
