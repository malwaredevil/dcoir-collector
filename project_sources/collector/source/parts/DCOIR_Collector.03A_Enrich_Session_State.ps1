<#
.SYNOPSIS
DCOIR collector enrich-session state helpers.

.DESCRIPTION
Maintains enrichment session lookup, creation, reuse, and finalization state for the
DCOIR collector. These helpers keep enrichment work appended to the correct session,
write session metadata and summaries, and package finalized enrichment output into a
bundle that can be retrieved later.

.FILE NAME
DCOIR_Collector.03A_Enrich_Session_State.ps1

.INPUTS
Hashtable state objects, requested session identifiers, and tool-map/runtime context
needed to create or finalize an enrichment session.

.OUTPUTS
Hashtables representing the selected or newly created enrichment session, or the final
bundle path when a session is finalized.
#>

<#
.SYNOPSIS
Returns one enrichment session from collector state by session identifier.

.DESCRIPTION
Searches the in-memory collector state for a session whose SessionId matches the
requested identifier. Returns null when no matching session exists.

.FUNCTION NAME
Get-SessionById

.INPUTS
State hashtable containing EnrichSessions and the session identifier string to match.

.OUTPUTS
Hashtable for the matching enrichment session, or null when the session is absent.
#>
function Get-SessionById {
  param([hashtable]$State,[string]$SessionId)
  foreach ($session in @($State.EnrichSessions)) {
    if ($session.SessionId -eq $SessionId) { return $session }
  }
  return $null
}

<#
.SYNOPSIS
Creates, reuses, or resolves the active enrichment session for the current run.

.DESCRIPTION
Normalizes the collector state for enrichment-session tracking, honors an explicitly
requested session when present, reuses the current open session when appropriate, and
creates a new session directory structure when a fresh session is required. It also
writes the initial session summary header and updates the state fields that track the
open session and last resolution mode.

.FUNCTION NAME
Initialize-EnrichSession

.INPUTS
Collector state hashtable, optional requested session identifier, an optional ForceNew
switch that suppresses reuse of the currently open session, and an optional guard that
requires an existing open session for finalize-only calls.

.OUTPUTS
Hashtable describing the resolved enrichment session, whether reused or newly created.
#>
function Initialize-EnrichSession {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [hashtable]$State,
    [string]$RequestedSessionId,
    [switch]$ForceNew,
    [switch]$RequireExistingOpenSession
  )

  if (-not $State.ContainsKey("EnrichSessions") -or $null -eq $State.EnrichSessions) {
    $State.EnrichSessions = @()
  } else {
    $State.EnrichSessions = @($State.EnrichSessions)
  }
  if (-not $State.ContainsKey("EnrichSessionCounter") -or $null -eq $State.EnrichSessionCounter) {
    $State.EnrichSessionCounter = 0
  }

  if (-not $State.ContainsKey('LastSessionResolutionMode')) {
    $State.LastSessionResolutionMode = $null
  }

  if (-not [string]::IsNullOrWhiteSpace($RequestedSessionId)) {
    $existing = Get-SessionById -State $State -SessionId $RequestedSessionId
    if ($existing) {
      if ($existing.Finalized) {
        throw "Requested enrichment session is finalized and cannot be appended: $RequestedSessionId"
      }
      $existing.SessionResolutionMode = 'REUSED_REQUESTED_SESSION'
      $State.LastSessionResolutionMode = 'REUSED_REQUESTED_SESSION'
      return $existing
    }
    throw "Requested enrichment session was not found: $RequestedSessionId"
  }

  if (-not $ForceNew -and -not [string]::IsNullOrWhiteSpace([string]$State.OpenEnrichSessionId)) {
    $open = Get-SessionById -State $State -SessionId ([string]$State.OpenEnrichSessionId)
    if ($open -and -not $open.Finalized) {
      $open.SessionResolutionMode = 'REUSED_OPEN_SESSION'
      $State.LastSessionResolutionMode = 'REUSED_OPEN_SESSION'
      return $open
    }
  }

  if ($RequireExistingOpenSession) {
    throw "No open enrichment session is available to finalize. Start an enrich session or provide -EnrichSessionId for a non-finalized session."
  }

  $nextSessionCounter = [int]$State.EnrichSessionCounter + 1
  $sessionNumber = "{0:D3}" -f $nextSessionCounter
  $sessionStamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $sessionId = "ENRICH_{0}_{1}" -f $sessionNumber, $sessionStamp

  $sessionRoot = Join-Path $State.EnrichSessionsDir $sessionId
  $sessionArtifactsDir = Join-Path $sessionRoot "artifacts"
  $sessionStagedDir = Join-Path $sessionRoot "staged"
  $sessionLogsDir = Join-Path $sessionRoot "logs"

  $session = @{
    SessionId = $sessionId
    SessionRoot = $sessionRoot
    ArtifactsDir = $sessionArtifactsDir
    StagedDir = $sessionStagedDir
    LogsDir = $sessionLogsDir
    SummaryPath = (Join-Path $sessionRoot ("DCOIR_ENRICH_SUMMARY_{0}_{1}_{2}.txt" -f $sessionId, $env:COMPUTERNAME, $State.RunId))
    ManifestPath = (Join-Path $sessionRoot ("manifest_{0}.json" -f $sessionId))
    BundlePath = $null
    CreatedLocal = (Get-Date).ToString("o")
    Finalized = $false
    ActionCount = 0
    SessionResolutionMode = 'CREATED_NEW_SESSION'
    CreationSkipped = $false
  }

  $header = @(
    "CollectorVersion=$ScriptVersion"
    "Mode=Enrich"
    "RunId=$($State.RunId)"
    "EnrichSessionId=$sessionId"
    "SessionResolutionMode=CREATED_NEW_SESSION"
    "Host=$env:COMPUTERNAME"
    "SessionCreatedLocal=$(Get-Date -Format o)"
    "SessionRoot=$sessionRoot"
  ) -join [Environment]::NewLine
  if ($PSCmdlet.ShouldProcess($sessionRoot, 'Create enrichment session directories and summary')) {
    Ensure-Directory -Path $sessionRoot
    Ensure-Directory -Path $sessionArtifactsDir
    Ensure-Directory -Path $sessionStagedDir
    Ensure-Directory -Path $sessionLogsDir
    Set-Content -Path $session.SummaryPath -Value $header -Encoding UTF8 -ErrorAction Stop
    $State.EnrichSessionCounter = $nextSessionCounter
    $State.EnrichSessions = @($State.EnrichSessions) + @($session)
    $State.OpenEnrichSessionId = $sessionId
    $State.LastSessionResolutionMode = 'CREATED_NEW_SESSION'
    return $session
  }

  $session.CreationSkipped = $true
  $session.SessionResolutionMode = 'CREATE_SKIPPED'
  return $session
}

<#
.SYNOPSIS
Finalizes an enrichment session and produces its retrievable bundle.

.DESCRIPTION
Builds the per-session manifest, gathers session summary, artifact, staged, and log
files, packages them into the enrich bundle, updates session finalization flags, and
clears the open-session pointer when the finalized session was the active one.

.FUNCTION NAME
Finalize-EnrichSession

.INPUTS
Collector state hashtable, enrichment-session hashtable, and the resolved collector
ToolMap used to write the manifest.

.OUTPUTS
String path to the finalized enrichment bundle ZIP file.
#>
function Finalize-EnrichSession {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [hashtable]$State,
    [hashtable]$Session,
    [hashtable]$ToolMap
  )

  $manifest = New-Manifest -ManifestPath $Session.ManifestPath -State $State -ModeName "Enrich" -TierName $Tier -Files (
    @($Session.SummaryPath) +
    @(Get-ChildItem -LiteralPath $Session.ArtifactsDir -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }) +
    @(Get-ChildItem -LiteralPath $Session.StagedDir -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }) +
    @(Get-ChildItem -LiteralPath $Session.LogsDir -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
  ) -ToolMap $ToolMap -Extra @{
    enrich_session_id = $Session.SessionId
    action_count = $Session.ActionCount
    session_resolution_mode = $Session.SessionResolutionMode
    append_model = 'enrich-start creates a new session; enrich-add reuses the current open session unless explicitly overridden; enrich-finalize finalizes the current open session.'
  }

  if (-not $manifest) { return $null }

  $bundleInputs = @(
    $Session.SummaryPath,
    $Session.ArtifactsDir,
    $Session.StagedDir,
    $Session.LogsDir,
    $manifest
  )

  $bundlePath = New-BundleZip -BundlesDir $State.BundlesDir -BundleName ("DCOIR_ENRICH_BUNDLE_{0}_{1}_{2}.zip" -f $Session.SessionId, $env:COMPUTERNAME, $State.RunId) -Paths $bundleInputs
  if (-not $bundlePath) { return $null }
  $Session.BundlePath = $bundlePath
  $Session.Finalized = $true
  if ($State.OpenEnrichSessionId -eq $Session.SessionId) {
    $State.OpenEnrichSessionId = $null
  }
  return $bundlePath
}
