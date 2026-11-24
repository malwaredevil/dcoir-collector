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

  # HEAD and the last runner-observed tree alone cannot identify a report
  # published and deleted by another runner between checkout and first push.
  # Inspect intervening history so stale local evidence cannot be resurrected.
  $interveningDeletes = @(& git -c core.longpaths=true -c core.quotepath=false log --first-parent --diff-merges=first-parent --no-renames --diff-filter=D --format= --name-only "HEAD..$RemoteHead" -- @CandidatePaths)
  if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Cannot inspect report deletions in intervening main history.'
    return $false
  }
  foreach ($deletedPath in ($interveningDeletes | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)) {
    $path = [string]$deletedPath
    if ($path.StartsWith('.github/chatgpt_staging/status_reports/', [StringComparison]::OrdinalIgnoreCase) -and
        (-not $remoteFileSet.ContainsKey($path)) -and
        (Test-Path -LiteralPath $path -PathType Leaf)) {
      Write-Warning "Intervening report deletion on main cannot be resurrected: $path"
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

# Keep branch-only request cleanup safe without growing the main push driver.
function Get-StageableReportPushPaths {
  param([string]$RemoteHead, [string[]]$CandidatePaths)

  $stageable = @()
  foreach ($stagePath in $CandidatePaths) {
    if ($stagePath -match '^\.github/chatgpt_staging/exec_requests/[A-Za-z0-9._-]+\.json$') {
      $mainEntries = @(& git -c core.longpaths=true ls-tree -r --name-only $RemoteHead -- $stagePath)
      if ($LASTEXITCODE -ne 0) { throw "Cannot inspect main exec request path: $stagePath" }
      if ($mainEntries -notcontains $stagePath) {
        if (Test-Path -LiteralPath $stagePath -PathType Leaf) {
          throw "Refusing to publish branch-only exec request to main: $stagePath"
        }
        Write-Information -MessageData "Absent branch-only exec request cleanup is a no-op: $stagePath" -InformationAction Continue
        continue
      }
    }
    $stageable += $stagePath
  }
  return $stageable
}
