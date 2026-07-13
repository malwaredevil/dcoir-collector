$ErrorActionPreference = 'Stop'

$requestId = 'exec-20260520-wbs06-rename-ledger-dryrun-001'
$outputPrefix = 'dcoir_wbs06_rename_ledger_source'
$expectedTableCount = 21
$tableList = @(
  'Work Items',
  'Session Checkpoints',
  'Idea Inbox',
  'Plans',
  'Operator Preferences',
  'Validation Test Cases',
  'Queue Control',
  'Gemini Research Reference',
  'Governance Control Plane',
  'Repo Surface Registry',
  'dcoir-memory-preflight',
  'dcoir-decision-policy',
  'dcoir-validation-orchestrator',
  'Validation Evidence',
  'Admin Registry',
  'DCOIR Lifecycle Ledger',
  'Local Configuration Registry',
  'Operator Tools Registry',
  'DCOIR Cleanup WBS',
  'DCOIR Cleanup Scaffold Registry',
  'GitHub Workflow Inventory'
)

function Get-RequiredEnvValue {
  param([Parameter(Mandatory=$true)][string]$Name)
  $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
  if ([string]::IsNullOrWhiteSpace($value)) { $value = [Environment]::GetEnvironmentVariable($Name, 'Machine') }
  if ([string]::IsNullOrWhiteSpace($value)) { throw "Missing required environment variable: $Name" }
  return $value.Trim()
}

function Write-JsonFile {
  param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)]$Object, [int]$Depth = 40)
  $parent = Split-Path -Parent $Path
  if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  $Object | ConvertTo-Json -Depth $Depth | Out-File -FilePath $Path -Encoding utf8
}

function Convert-ToSafeString {
  param([AllowNull()]$Value)
  if ($null -eq $Value) { return '' }
  if ($Value -is [string]) { return $Value }
  try { return (($Value | ConvertTo-Json -Depth 8 -Compress) -replace '\s+', ' ').Trim() } catch { return ([string]$Value) }
}

function Test-BlankValue {
  param([AllowNull()]$Value)
  if ($null -eq $Value) { return $true }
  if ($Value -is [string]) { return [string]::IsNullOrWhiteSpace($Value) }
  if ($Value -is [System.Array]) { return ($Value.Count -eq 0) }
  if ($Value.PSObject -and $Value.PSObject.Properties.Count -eq 0) { return $true }
  return $false
}

function Get-ProposedLegacyName {
  param([Parameter(Mandatory=$true)][string]$Name)
  $n = $Name.Trim()
  $n = $n -replace '__+', '_'
  $n = $n -replace '_do_not_use$', ''
  $n = $n -replace 'do_not_use$', ''
  $n = $n.Trim('_')
  if ($n -notmatch '^legacy_') { $n = 'legacy_' + $n }
  if ($n -notmatch '_review$') { $n = $n + '_review' }
  $n = $n -replace '__+', '_'
  return $n
}

$appliedRenameSeeds = @{
  'fldvsVffETaqyuB0H' = @{ old_name = 'active_plan_task_id'; current_name = 'legacy_active_plan_task_id_review'; reason = 'Plans field already marked as legacy review during WBS06.02.' }
  'fldLYnjrlPY6QfKNH' = @{ old_name = 'flush_trigger'; current_name = 'legacy_plan_buffer_marker_review'; reason = 'Plans field already renamed to clearer buffer-marker review name during WBS06.02.' }
  'fldyfFi5VTw9ffaPq' = @{ old_name = 'pending_flush_items'; current_name = 'legacy_pending_plan_buffer_items_review'; reason = 'Plans field already marked as legacy review during WBS06.02.' }
  'fld4QqRiSFLzEvKuD' = @{ old_name = 'promotion_candidates'; current_name = 'legacy_promotion_candidates_review'; reason = 'Plans field already marked as legacy review during WBS06.02.' }
  'fldzT3tVTcvhSWPNa' = @{ old_name = 'remain_local_notes'; current_name = 'legacy_remain_local_notes_review'; reason = 'Plans field already marked as legacy review during WBS06.02.' }
  'fldZoUV6BFJyKuOhz' = @{ old_name = 'last_updated_text'; current_name = 'legacy_last_updated_text_review'; reason = 'Plans text timestamp duplicate already marked as legacy review during WBS06.02.' }
}

$repo = Get-RequiredEnvValue -Name 'DCOIR_REPO_ROOT'
$downloads = Get-RequiredEnvValue -Name 'DCOIR_DOWNLOADS_DIR'
$exportScript = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\New-DcoirAirtableDatabaseHealthExport.ps1'
if (-not (Test-Path -LiteralPath $exportScript -PathType Leaf)) { throw "Missing export script: $exportScript" }
if (-not (Test-Path -LiteralPath $downloads -PathType Container)) { New-Item -ItemType Directory -Force -Path $downloads | Out-Null }

$statusRoot = Join-Path $repo ("chatgpt_staging\status_reports\chatgpt-exec\{0}\wbs06_rename_ledger" -f $requestId)
if (Test-Path -LiteralPath $statusRoot) { Remove-Item -LiteralPath $statusRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $statusRoot | Out-Null

$before = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter ($outputPrefix + '_*') -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
$tableListText = ($tableList -join ',')
& $exportScript -ExportMode FullRecords -FullRecordDump -MetadataScope 'All' -ProbeUnsupportedMetadata -TableList $tableListText -OutputNamePrefix $outputPrefix -NoZip
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Airtable export script returned exit code $LASTEXITCODE" }

$after = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter ($outputPrefix + '_*') -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
$runFolder = $null
foreach ($candidate in $after) {
  if ($before -notcontains $candidate.FullName) { $runFolder = $candidate; break }
}
if ($null -eq $runFolder) { $runFolder = $after | Select-Object -First 1 }
if ($null -eq $runFolder) { throw 'Could not locate WBS06 source export output folder.' }

$manifestPath = Join-Path $runFolder.FullName 'export_manifest.json'
$runSummaryPath = Join-Path $runFolder.FullName 'run_summary.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Missing export_manifest.json from source export.' }
if (-not (Test-Path -LiteralPath $runSummaryPath -PathType Leaf)) { throw 'Missing run_summary.json from source export.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$runSummary = Get-Content -LiteralPath $runSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($runSummary.success -ne $true) { throw 'Source export run_summary.success was not true.' }
if ([int]$manifest.selected_table_count -ne $expectedTableCount) { throw "Expected $expectedTableCount tables; observed $($manifest.selected_table_count)." }

Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $statusRoot 'source_export_manifest.json') -Force
Copy-Item -LiteralPath $runSummaryPath -Destination (Join-Path $statusRoot 'source_run_summary.json') -Force
$schemaSummary = Join-Path $runFolder.FullName 'schema\schema.summary.json'
if (Test-Path -LiteralPath $schemaSummary -PathType Leaf) { Copy-Item -LiteralPath $schemaSummary -Destination (Join-Path $statusRoot 'source_schema_summary.json') -Force }

$recordsByTableId = @{}
$recordFiles = @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'records') -Filter '*.records.json' -File -ErrorAction Stop)
foreach ($recordFile in $recordFiles) {
  $payload = Get-Content -LiteralPath $recordFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  $recordsByTableId[[string]$payload.table_id] = $payload
}

$ledger = New-Object System.Collections.Generic.List[object]
$tableSummaries = New-Object System.Collections.Generic.List[object]
$schemaFiles = @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'schema') -Filter 'table.*.schema.json' -File -ErrorAction Stop)
foreach ($schemaFile in $schemaFiles) {
  $table = Get-Content -LiteralPath $schemaFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  $tableId = [string]$table.id
  $tableName = [string]$table.name
  $recordsPayload = $recordsByTableId[$tableId]
  $records = @()
  if ($recordsPayload -and $recordsPayload.records) { $records = @($recordsPayload.records) }
  $recordCount = $records.Count
  $tableFieldCount = 0
  foreach ($field in @($table.fields)) {
    $tableFieldCount++
    $fieldId = [string]$field.id
    $name = [string]$field.name
    $type = [string]$field.type
    $isPrimary = ($fieldId -eq [string]$table.primaryFieldId)
    $blankCount = 0
    $nonBlankCount = 0
    $observed = New-Object System.Collections.Generic.List[string]
    foreach ($record in $records) {
      $value = $null
      $prop = $record.fields.PSObject.Properties[$name]
      if ($prop) { $value = $prop.Value }
      if (Test-BlankValue -Value $value) { $blankCount++ }
      else {
        $nonBlankCount++
        if ($observed.Count -lt 8) {
          $sv = Convert-ToSafeString -Value $value
          if ($sv.Length -gt 180) { $sv = $sv.Substring(0,180) + '...' }
          if (-not $observed.Contains($sv)) { $observed.Add($sv) | Out-Null }
        }
      }
    }
    $blankRatio = if ($recordCount -gt 0) { [Math]::Round(($blankCount / [double]$recordCount), 4) } else { $null }
    $protectedType = @('formula','rollup','lookup','count','createdTime','lastModifiedTime','createdBy','lastModifiedBy','autoNumber','multipleRecordLinks') -contains $type
    $action = 'review'
    $proposedName = $name
    $reason = 'Needs human review; no automatic rename recommendation.'
    $risk = 'medium'
    if ($appliedRenameSeeds.ContainsKey($fieldId)) {
      $action = 'already_applied'
      $proposedName = $name
      $reason = [string]$appliedRenameSeeds[$fieldId].reason
      $risk = 'low'
    }
    elseif ($isPrimary -or $protectedType) {
      $action = 'protect'
      $reason = 'Primary, formula, linked, or system-derived field; do not rename in aggressive legacy pass without dedicated dependency review.'
      $risk = 'high'
    }
    elseif ($name -match '^legacy_.*_review$') {
      $action = 'already_review_marked'
      $reason = 'Already follows WBS06 single-underscore legacy review naming convention.'
      $risk = 'low'
    }
    elseif ($name -match '__|do_not_use') {
      $action = 'rename_candidate'
      $proposedName = Get-ProposedLegacyName -Name $name
      $reason = 'Name contains double-underscore or do-not-use marker; normalize to WBS06 single-underscore legacy review convention.'
      $risk = 'medium'
    }
    elseif ($recordCount -gt 0 -and $blankRatio -eq 1.0 -and $name -notmatch '(id|key|state|status|title|name|created|updated|owner|authority|evidence|source|notes|context|summary|description|validation|retention)') {
      $action = 'rename_candidate'
      $proposedName = Get-ProposedLegacyName -Name $name
      $reason = 'Field is fully blank in current full-record export and name does not obviously carry protected governance/provenance meaning.'
      $risk = 'medium'
    }
    elseif ($recordCount -gt 0 -and $blankRatio -ge 0.95 -and $name -match '(flush|pending|candidate|scratch|temp|buffer|legacy|stale|local)') {
      $action = 'rename_candidate'
      $proposedName = Get-ProposedLegacyName -Name $name
      $reason = 'Field is highly sparse and its name suggests transitional or legacy workflow state.'
      $risk = 'medium'
    }
    elseif ($recordCount -eq 0) {
      $action = 'table_empty_review'
      $reason = 'Table has zero exported records; field-level rename should wait for table/scaffold disposition rather than infer per-field retirement.'
      $risk = 'medium'
    }
    else {
      $action = 'protect_or_review'
      $reason = 'Field has observed values or plausible current governance/provenance purpose; not safe for automatic rename recommendation.'
      $risk = 'medium'
    }

    $oldName = $null
    if ($appliedRenameSeeds.ContainsKey($fieldId)) { $oldName = [string]$appliedRenameSeeds[$fieldId].old_name }

    $ledger.Add([pscustomobject]@{
      table_name = $tableName
      table_id = $tableId
      field_id = $fieldId
      old_name = $oldName
      current_name = $name
      field_type = $type
      is_primary = [bool]$isPrimary
      record_count = $recordCount
      blank_count = $blankCount
      nonblank_count = $nonBlankCount
      blank_ratio = $blankRatio
      observed_values = @($observed.ToArray())
      proposed_name = $proposedName
      action = $action
      dependency_risk = $risk
      recommendation_reason = $reason
      source = 'live full-record schema/record export via New-DcoirAirtableDatabaseHealthExport.ps1; no Airtable writes'
    }) | Out-Null
  }
  $tableSummaries.Add([pscustomobject]@{
    table_name = $tableName
    table_id = $tableId
    record_count = $recordCount
    field_count = $tableFieldCount
  }) | Out-Null
}

$ledgerItems = @($ledger.ToArray() | Sort-Object table_name, current_name)
$renameCandidates = @($ledgerItems | Where-Object { $_.action -eq 'rename_candidate' })
$alreadyApplied = @($ledgerItems | Where-Object { $_.action -eq 'already_applied' })
$protected = @($ledgerItems | Where-Object { $_.action -match 'protect' })
$summary = [ordered]@{
  schema = 'dcoir.wbs06.rename_ledger.dryrun.v1'
  request_id = $requestId
  result = 'success'
  safety = [ordered]@{
    airtable_read_only = $true
    airtable_writes = 0
    field_renames = 0
    record_updates = 0
    delete_queue_rows = 0
    deletions = 0
  }
  source_export_folder = $runFolder.FullName
  selected_table_count = [int]$manifest.selected_table_count
  table_count = @($tableSummaries.ToArray()).Count
  field_count = $ledgerItems.Count
  already_applied_count = $alreadyApplied.Count
  rename_candidate_count = $renameCandidates.Count
  protect_or_review_count = ($ledgerItems.Count - $alreadyApplied.Count - $renameCandidates.Count)
  naming_convention = 'single underscore only, e.g. legacy_field_name_review; avoid double underscore markers'
  created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}

Write-JsonFile -Path (Join-Path $statusRoot 'field_rename_ledger.json') -Object $ledgerItems -Depth 30
Write-JsonFile -Path (Join-Path $statusRoot 'field_rename_ledger_summary.json') -Object $summary -Depth 20
Write-JsonFile -Path (Join-Path $statusRoot 'table_inventory_summary.json') -Object @($tableSummaries.ToArray()) -Depth 12

$csvPath = Join-Path $statusRoot 'field_rename_ledger.csv'
$ledgerItems | Select-Object table_name,table_id,field_id,old_name,current_name,field_type,is_primary,record_count,blank_count,nonblank_count,blank_ratio,proposed_name,action,dependency_risk,recommendation_reason | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

$md = New-Object System.Collections.Generic.List[string]
$md.Add('# WBS06 field rename ledger dry run')
$md.Add('')
$md.Add("- request_id: $requestId")
$md.Add('- result: success')
$md.Add('- safety: read-only Airtable export and analysis; no Airtable writes, field renames, record updates, Delete Queue rows, or deletions')
$md.Add("- tables analyzed: $($summary.table_count)")
$md.Add("- fields analyzed: $($summary.field_count)")
$md.Add("- already applied rename markers: $($summary.already_applied_count)")
$md.Add("- rename candidates: $($summary.rename_candidate_count)")
$md.Add("- protect/review/table-empty rows: $($summary.protect_or_review_count)")
$md.Add('')
$md.Add('## Output files')
$md.Add('')
$md.Add('- field_rename_ledger.json')
$md.Add('- field_rename_ledger.csv')
$md.Add('- field_rename_ledger_summary.json')
$md.Add('- table_inventory_summary.json')
$md.Add('- source_export_manifest.json')
$md.Add('- source_run_summary.json')
$md.Add('')
$md.Add('## Top rename candidates')
$md.Add('')
$md.Add('| Table | Field ID | Current name | Proposed name | Blank ratio | Reason |')
$md.Add('|---|---|---|---|---:|---|')
foreach ($item in @($renameCandidates | Select-Object -First 40)) {
  $reason = ([string]$item.recommendation_reason).Replace('|','/')
  $md.Add("| $($item.table_name) | $($item.field_id) | $($item.current_name) | $($item.proposed_name) | $($item.blank_ratio) | $reason |")
}
$md.Add('')
$md.Add('## Already applied seed renames')
$md.Add('')
$md.Add('| Table | Field ID | Old name | Current name |')
$md.Add('|---|---|---|---|')
foreach ($item in $alreadyApplied) { $md.Add("| $($item.table_name) | $($item.field_id) | $($item.old_name) | $($item.current_name) |") }
$md | Out-File -FilePath (Join-Path $statusRoot 'field_rename_ledger_report.md') -Encoding UTF8

Write-Output ($summary | ConvertTo-Json -Depth 20)
