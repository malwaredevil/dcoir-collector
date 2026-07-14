configured safe and hard thresholds, logs the result, and throws when the manifest is
out of bounds.

.FUNCTION NAME
Invoke-AttachmentBudgetVerification

.INPUTS
StepName string and ManifestPath string.

.OUTPUTS
No direct return value beyond harness logging; throws when the budget check fails.
#>
function Invoke-AttachmentBudgetVerification {
  param([string]$StepName,[string]$ManifestPath)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @("STEP=$StepName","MANIFEST_PATH=$ManifestPath","SAFE_PER_FILE_KB=$SafePerFileKB","HARD_PER_FILE_KB=$HardPerFileKB","SAFE_PER_PROMPT_KB=$SafePerPromptKB","HARD_PER_PROMPT_KB=$HardPerPromptKB")
  if (-not (Test-Path -LiteralPath $ManifestPath)) {
    $message = 'Attachment budget manifest missing.'
    $lines += "STATUS=FAIL"
    $lines += "MESSAGE=$message"
  } else {
    $obj = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $rows = @($obj.recommended_upload_files)
    $total = 0
    $violations = New-Object System.Collections.ArrayList
    foreach ($row in $rows) {
      $total += [int]$row.size_kb
      $lines += ('FILE={0} SIZE_KB={1}' -f $row.path, $row.size_kb)
      if ([int]$row.size_kb -gt $SafePerFileKB) { [void]$violations.Add(('safe per-file exceeded: {0}' -f $row.path)) }
      if ([int]$row.size_kb -gt $HardPerFileKB) { [void]$violations.Add(('hard per-file exceeded: {0}' -f $row.path)) }
    }
    $lines += "TOTAL_RECOMMENDED_KB=$total"
    if ($total -gt $SafePerPromptKB) { [void]$violations.Add('safe total exceeded') }
    if ($total -gt $HardPerPromptKB) { [void]$violations.Add('hard total exceeded') }
    if (@($violations).Count -eq 0) {
      $status = 'PASS'
      $message = 'Recommended upload set is within the configured safe budget.'
    } else {
      $status = 'FAIL'
      $message = ($violations -join '; ')
    }
    $lines += "STATUS=$status"
    $lines += "MESSAGE=$message"
  }
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $script:CollectorRunId -EnrichSessionId $script:CollectorSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies enrich-session reuse behavior.

.DESCRIPTION
Checks that enrich-start created a new session, enrich-add reused the same session, and
the recorded session-resolution modes match the expected model.

.FUNCTION NAME
Invoke-SessionBehaviorVerification

.INPUTS
StepName string, start/add session IDs, and start/add session-resolution modes.

.OUTPUTS
No direct return value beyond harness logging; throws when the session behavior is
incorrect.
#>
function Invoke-SessionBehaviorVerification {
  param([string]$StepName,[string]$StartSessionId,[string]$AddSessionId,[string]$StartMode,[string]$AddMode)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @("STEP=$StepName","START_SESSION_ID=$StartSessionId","ADD_SESSION_ID=$AddSessionId","START_MODE=$StartMode","ADD_MODE=$AddMode")
  if ($StartSessionId -and $AddSessionId -and ($StartSessionId -eq $AddSessionId) -and ($StartMode -eq 'CREATED_NEW_SESSION') -and ($AddMode -like 'REUSED_*')) {
    $status = 'PASS'
    $message = 'enrich-add reused the existing open session as expected.'
  } else {
    $message = 'Session reuse behavior did not match the expected start/add model.'
  }
  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $script:CollectorRunId -EnrichSessionId $script:CollectorSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}


<#
.SYNOPSIS
Verifies one enrich-session resolution result.

.DESCRIPTION
Checks that an enrich step used the expected session-resolution mode and optional
session identity constraints, including required or forbidden session IDs.

.FUNCTION NAME
Invoke-SessionResolutionVerification

.INPUTS
StepName string, SessionStep result object, expected mode, and optional expected or
unexpected session IDs.

.OUTPUTS
No direct return value beyond harness logging; throws when the resolution behavior does
not match the expected mode or identity constraints.
#>
function Invoke-SessionResolutionVerification {
  param(
    [string]$StepName,
    [object]$SessionStep,
    [string]$ExpectedMode,
    [string]$ExpectedSessionId = '',
    [string]$UnexpectedSessionId = ''
  )
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "SESSION_ID=$($SessionStep.EnrichSessionId)",
    "EXPECTED_SESSION_ID=$ExpectedSessionId",
    "UNEXPECTED_SESSION_ID=$UnexpectedSessionId",
    "SESSION_RESOLUTION_MODE=$($SessionStep.SessionResolutionMode)",
    "EXPECTED_MODE=$ExpectedMode"
  )

  $modeOk = -not [string]::IsNullOrWhiteSpace($ExpectedMode) -and $SessionStep.SessionResolutionMode -eq $ExpectedMode
  $expectedIdOk = [string]::IsNullOrWhiteSpace($ExpectedSessionId) -or $SessionStep.EnrichSessionId -eq $ExpectedSessionId
  $unexpectedIdOk = [string]::IsNullOrWhiteSpace($UnexpectedSessionId) -or $SessionStep.EnrichSessionId -ne $UnexpectedSessionId
  if ($SessionStep.ExitCode -eq 0 -and $SessionStep.Status -eq 'PASS' -and $modeOk -and $expectedIdOk -and $unexpectedIdOk) {
    $status = 'PASS'
    $message = 'Session resolution behavior matched the expected mode and session identity constraints.'
  } else {
    $message = 'Session resolution behavior did not match the expected mode or session identity constraints.'
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $script:CollectorRunId -EnrichSessionId $SessionStep.EnrichSessionId -CollectorReportedStatus $SessionStep.CollectorReportedStatus -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Checks a timestamp field against an expected UTC instant.

.DESCRIPTION
Reads a single FIELD=value line from harness artifact text, parses it as a timestamp,
and compares its UTC instant to the expected timestamp value.

.FUNCTION NAME
Test-HarnessUtcTimestampLine

.INPUTS
Artifact text, field name, and expected timestamp value.

.OUTPUTS
Boolean indicating whether the field exists once and matches the expected UTC instant.
#>
function Test-HarnessUtcTimestampLine {
  param([string]$Text,[string]$FieldName,[string]$ExpectedValue)
  if ([string]::IsNullOrWhiteSpace($Text) -or [string]::IsNullOrWhiteSpace($FieldName) -or [string]::IsNullOrWhiteSpace($ExpectedValue)) { return $false }
  $matches = [regex]::Matches($Text, ('(?m)^{0}=(.+)$' -f [regex]::Escape($FieldName)))
  if ($matches.Count -ne 1) { return $false }
  $actualText = $matches[0].Groups[1].Value.Trim()
  if ($actualText -notmatch '(Z|[+-]\d{2}:\d{2})$') { return $false }
  try {
    $actualUtc = ([datetime]::Parse($actualText)).ToUniversalTime()
    $expectedUtc = ([datetime]::Parse($ExpectedValue)).ToUniversalTime()
    return ($actualUtc -eq $expectedUtc)
  } catch {
    return $false
  }
}

<#
.SYNOPSIS
Verifies the targeted-collection artifact contract.

.DESCRIPTION
Checks that targeted collect emitted collection scope, parallelism assessment, targeted
plan, high-signal metadata, and optional explicit event-window values.

.FUNCTION NAME
Invoke-TargetedCollectionVerification

.INPUTS
StepName string, CollectStep result object, optional explicit-window expectation, and
optional expected WindowStart and WindowEnd strings.

.OUTPUTS
No direct return value beyond harness logging; throws when targeted artifacts are missing
or malformed.
#>
function Invoke-TargetedCollectionVerification {
  param(
    [string]$StepName,
    [object]$CollectStep,
    [object]$ExpectedExplicitEventWindow = $null,
    [string]$ExpectedWindowStart = '',
    [string]$ExpectedWindowEnd = '',
    [string]$ExpectedTargetProfile = '',
    [string]$ExpectedFocusProcess = '',
    [string]$ExpectedFocusPath = '',
    [string]$ExpectedFocusIndicator = '',
    [string]$ExpectedFocusIndicatorType = '',
    [string]$ExpectedUserReport = '',
    [string[]]$ExpectedIncludedArtifactCategories = @(),
    [string[]]$ExpectedPlanMarkers = @()
  )
  $start = Get-Date
  $status = "FAIL"
  $message = ""
  $lines = @(
    "STEP=$StepName",
    "COLLECTION_SCOPE_PATH=$($CollectStep.CollectionScopePath)",
    "PARALLELISM_ASSESSMENT_PATH=$($CollectStep.ParallelismAssessmentPath)",
    "TARGETED_COLLECTION_PLAN_PATH=$($CollectStep.TargetedCollectionPlanPath)"
  )

  $required = @(
    @{ Label = "COLLECTION_SCOPE_PATH"; Path = $CollectStep.CollectionScopePath },
    @{ Label = "PARALLELISM_ASSESSMENT_PATH"; Path = $CollectStep.ParallelismAssessmentPath },
    @{ Label = "TARGETED_COLLECTION_PLAN_PATH"; Path = $CollectStep.TargetedCollectionPlanPath }
  )

  $missing = New-Object System.Collections.ArrayList
  foreach ($row in $required) {
    $candidate = [string]$row.Path
    if ([string]::IsNullOrWhiteSpace($candidate)) {
      [void]$missing.Add(("{0} was not emitted by the collector response." -f $row.Label))
      continue
    }
    if (-not (Test-Path -LiteralPath $candidate)) {
      [void]$missing.Add(("{0} path does not exist: {1}" -f $row.Label, $candidate))
    }
  }

  if (@($missing).Count -eq 0) {
    $scopeText = Get-Content -LiteralPath $CollectStep.CollectionScopePath -Raw
    $planText = Get-Content -LiteralPath $CollectStep.TargetedCollectionPlanPath -Raw
    $metadataText = if ($CollectStep.SecurityHighSignalSummaryPath -and (Test-Path -LiteralPath $CollectStep.SecurityHighSignalSummaryPath)) { Get-Content -LiteralPath $CollectStep.SecurityHighSignalSummaryPath -Raw } else { '' }
    $scopeLineMap = @{}
    foreach ($line in ($scopeText -split "`r?`n")) {
      if ($line -match '^(?<key>[A-Z_]+)=(?<value>.*)$') {
        $scopeLineMap[$matches['key']] = $matches['value']
      }
    }
    $expectedWindowOk = $true
    if ($null -ne $ExpectedExplicitEventWindow) {
      $expectedValue = if ([bool]$ExpectedExplicitEventWindow) { 'True' } else { 'False' }
      $expectedWindowOk = ($metadataText -match ("HAS_EXPLICIT_TIME_WINDOW={0}" -f $expectedValue))
      $lines += ("EXPECTED_EXPLICIT_EVENT_WINDOW={0}" -f $expectedValue)
    }
    $expectedWindowValuesOk = $true
    if (-not [string]::IsNullOrWhiteSpace($ExpectedWindowStart)) {
      $expectedStartText = ([datetime]::Parse($ExpectedWindowStart)).ToUniversalTime().ToString('o')
      $expectedWindowValuesOk = $expectedWindowValuesOk -and (Test-HarnessUtcTimestampLine -Text $scopeText -FieldName 'WINDOW_START' -ExpectedValue $ExpectedWindowStart) -and (Test-HarnessUtcTimestampLine -Text $metadataText -FieldName 'WINDOW_START' -ExpectedValue $ExpectedWindowStart)
      $lines += ("EXPECTED_WINDOW_START={0}" -f $expectedStartText)
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedWindowEnd)) {
      $expectedEndText = ([datetime]::Parse($ExpectedWindowEnd)).ToUniversalTime().ToString('o')
      $expectedWindowValuesOk = $expectedWindowValuesOk -and (Test-HarnessUtcTimestampLine -Text $scopeText -FieldName 'WINDOW_END' -ExpectedValue $ExpectedWindowEnd) -and (Test-HarnessUtcTimestampLine -Text $metadataText -FieldName 'WINDOW_END' -ExpectedValue $ExpectedWindowEnd)
      $lines += ("EXPECTED_WINDOW_END={0}" -f $expectedEndText)
    }
    $expectedTargetProfileOk = $true
    if (-not [string]::IsNullOrWhiteSpace($ExpectedTargetProfile)) {
      $expectedTargetProfileOk = (($scopeLineMap['TARGET_PROFILE'] -eq $ExpectedTargetProfile) -and ($planText -match ("PROFILE={0}" -f [regex]::Escape($ExpectedTargetProfile))))
      $lines += ("EXPECTED_TARGET_PROFILE={0}" -f $ExpectedTargetProfile)
    }
    $expectedScopeFieldOk = $true
    foreach ($fieldCheck in @(
      @{ Field = 'FOCUS_PROCESS'; Expected = $ExpectedFocusProcess },
      @{ Field = 'FOCUS_PATH'; Expected = $ExpectedFocusPath },
      @{ Field = 'FOCUS_INDICATOR'; Expected = $ExpectedFocusIndicator },
      @{ Field = 'FOCUS_INDICATOR_TYPE'; Expected = $ExpectedFocusIndicatorType },
      @{ Field = 'USER_REPORT'; Expected = $ExpectedUserReport }
    )) {
      if ([string]::IsNullOrWhiteSpace([string]$fieldCheck.Expected)) {
        continue
      }
      $lines += ("EXPECTED_{0}={1}" -f $fieldCheck.Field, $fieldCheck.Expected)
      if (-not $scopeLineMap.ContainsKey($fieldCheck.Field)) {
        $expectedScopeFieldOk = $false
        continue
      }
      if ([string]$scopeLineMap[$fieldCheck.Field] -ne [string]$fieldCheck.Expected) {
        $expectedScopeFieldOk = $false
      }
    }
    $expectedCategoriesOk = $true
    if (@($ExpectedIncludedArtifactCategories).Count -gt 0) {
      $lines += ("EXPECTED_INCLUDED_ARTIFACT_CATEGORIES={0}" -f (@($ExpectedIncludedArtifactCategories) -join ', '))
      $actualCategoryLine = if ($scopeLineMap.ContainsKey('INCLUDED_ARTIFACT_CATEGORIES')) { [string]$scopeLineMap['INCLUDED_ARTIFACT_CATEGORIES'] } else { '' }
      foreach ($category in @($ExpectedIncludedArtifactCategories)) {
        if ($actualCategoryLine -notmatch [regex]::Escape($category)) {
          $expectedCategoriesOk = $false
        }
      }
    }
    $expectedPlanMarkersOk = $true
    if (@($ExpectedPlanMarkers).Count -gt 0) {
      foreach ($marker in @($ExpectedPlanMarkers)) {
        $lines += ("EXPECTED_PLAN_MARKER={0}" -f $marker)
        if ($planText -notmatch [regex]::Escape($marker)) {
          $expectedPlanMarkersOk = $false
        }
      }
    }
    if (($scopeText -match 'TARGETED_COLLECTION_SCOPE') -and ($planText -match 'TARGETED_COLLECTION_PLAN') -and ($scopeText -match 'WINDOW_START=') -and ($scopeText -match 'WINDOW_END=') -and ($metadataText -match 'WINDOW_START=') -and ($metadataText -match 'WINDOW_END=') -and $expectedWindowOk -and $expectedWindowValuesOk -and $expectedTargetProfileOk -and $expectedScopeFieldOk -and $expectedCategoriesOk -and $expectedPlanMarkersOk) {
      $status = "PASS"
      $message = "Targeted collection artifacts were produced and contained expected markers, profile-specific fields, and exact effective event-window fields."
    } else {
      $message = "Targeted collection artifact markers, profile-specific fields, or exact effective event-window fields were missing or unexpected."
    }
  } else {
    $message = ($missing -join '; ')
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
