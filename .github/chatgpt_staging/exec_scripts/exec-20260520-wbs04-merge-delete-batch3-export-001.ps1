$ErrorActionPreference = 'Stop'

$requestId = 'exec-20260520-wbs04-merge-delete-batch3-export-001'
$tableList = 'Admin Registry,DCOIR Lifecycle Ledger,Local Configuration Registry,Operator Tools Registry,DCOIR Cleanup WBS,DCOIR Cleanup Scaffold Registry,GitHub Workflow Inventory'
$outputPrefix = 'dcoir_wbs04_merge_delete_batch3_export'
$expectedTableCount = 7

function Get-DcoirRequiredEnvValue {
    param([Parameter(Mandatory=$true)][string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, 'Machine')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $Name"
    }
    return $value.Trim()
}

$repo = Get-DcoirRequiredEnvValue -Name 'DCOIR_REPO_ROOT'
$downloads = Get-DcoirRequiredEnvValue -Name 'DCOIR_DOWNLOADS_DIR'

$exportScript = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\New-DcoirAirtableDatabaseHealthExport.ps1'
if (-not (Test-Path -LiteralPath $exportScript -PathType Leaf)) {
    throw "Airtable export script not found: $exportScript"
}
if (-not (Test-Path -LiteralPath $downloads -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
}

$reportDir = Join-Path $repo (Join-Path 'chatgpt_staging\status_reports\chatgpt-exec' $requestId)
$readbackDir = Join-Path $reportDir 'wbs04_export_readback'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
if (Test-Path -LiteralPath $readbackDir) {
    Remove-Item -LiteralPath $readbackDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $readbackDir | Out-Null

$before = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter ($outputPrefix + '_*') -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)

& $exportScript -ExportMode FullRecords -FullRecordDump -MetadataScope 'All' -ProbeUnsupportedMetadata -TableList $tableList -OutputNamePrefix $outputPrefix
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Airtable export script returned exit code $LASTEXITCODE"
}

$after = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter ($outputPrefix + '_*') -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
$runFolder = $null
foreach ($candidate in $after) {
    if ($before -notcontains $candidate.FullName) {
        $runFolder = $candidate
        break
    }
}
if ($null -eq $runFolder) {
    $runFolder = $after | Select-Object -First 1
}
if ($null -eq $runFolder) {
    throw 'Could not locate Airtable export output folder.'
}

$runSummaryPath = Join-Path $runFolder.FullName 'run_summary.json'
$exportManifestPath = Join-Path $runFolder.FullName 'export_manifest.json'
if (-not (Test-Path -LiteralPath $runSummaryPath -PathType Leaf)) {
    throw "Missing run_summary.json in export folder: $($runFolder.FullName)"
}
if (-not (Test-Path -LiteralPath $exportManifestPath -PathType Leaf)) {
    throw "Missing export_manifest.json in export folder: $($runFolder.FullName)"
}

$runSummary = Get-Content -LiteralPath $runSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$exportManifest = Get-Content -LiteralPath $exportManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($runSummary.success -ne $true) {
    throw 'Airtable export run_summary reported success=false.'
}
if ([int]$exportManifest.selected_table_count -ne $expectedTableCount) {
    throw "Expected $expectedTableCount selected tables; got $($exportManifest.selected_table_count)."
}

Copy-Item -LiteralPath $runSummaryPath -Destination (Join-Path $readbackDir 'run_summary.json') -Force
Copy-Item -LiteralPath $exportManifestPath -Destination (Join-Path $readbackDir 'export_manifest.json') -Force

foreach ($relative in @('diagnostic_index.md','command_context.json','metadata\metadata_coverage.json','schema\schema.summary.json')) {
    $source = Join-Path $runFolder.FullName $relative
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        $dest = Join-Path $readbackDir ($relative -replace '[\\/]', '_')
        Copy-Item -LiteralPath $source -Destination $dest -Force
    }
}

$recordSourceDir = Join-Path $runFolder.FullName 'records'
if (-not (Test-Path -LiteralPath $recordSourceDir -PathType Container)) {
    throw "Missing records folder in export output: $recordSourceDir"
}
$recordReadbackDir = Join-Path $readbackDir 'records'
New-Item -ItemType Directory -Force -Path $recordReadbackDir | Out-Null
$recordFiles = @(Get-ChildItem -LiteralPath $recordSourceDir -Filter '*.records.json' -File -ErrorAction Stop | Sort-Object Name)
if ($recordFiles.Count -ne $expectedTableCount) {
    throw "Expected $expectedTableCount record files; got $($recordFiles.Count)."
}

$tableSummaries = @()
foreach ($file in $recordFiles) {
    Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $recordReadbackDir $file.Name) -Force
    $recordPayload = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $tableSummaries += [pscustomobject]@{
        table_name = [string]$recordPayload.table_name
        table_id = [string]$recordPayload.table_id
        record_count_exported = [int]$recordPayload.record_count_exported
        records_file = 'records/' + $file.Name
    }
}

$summary = [ordered]@{
    schema = 'dcoir.wbs04.merge_delete_batch_export.readback.v1'
    request_id = $requestId
    success = $true
    purpose = 'Read-only WBS04 merge/delete candidate analysis export, batch 3 rest-of-tables. Full rows and fields for aggressive row reduction analysis. Delete Queue plus Batch 1 and Batch 2 tables intentionally excluded.'
    table_batch = 3
    table_batch_total = 3
    table_list = @('Admin Registry','DCOIR Lifecycle Ledger','Local Configuration Registry','Operator Tools Registry','DCOIR Cleanup WBS','DCOIR Cleanup Scaffold Registry','GitHub Workflow Inventory')
    excluded_tables = @('Delete Queue','Work Items','Session Checkpoints','Idea Inbox','Plans','Operator Preferences','Validation Test Cases','Queue Control','Gemini Research Reference','Governance Control Plane','Repo Surface Registry','dcoir-memory-preflight','dcoir-decision-policy','dcoir-validation-orchestrator','Validation Evidence')
    selected_table_count = [int]$exportManifest.selected_table_count
    export_mode = [string]$exportManifest.export_mode
    full_record_dump = [bool]$exportManifest.full_record_dump
    metadata_scope = 'All'
    read_only_airtable = $true
    no_airtable_writes = $true
    no_delete_queue_rows = $true
    no_record_deletions = $true
    output_folder = [string]$runFolder.FullName
    output_zip = [string]$runSummary.output_zip
    tables = @($tableSummaries)
    created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$summary | ConvertTo-Json -Depth 12 | Out-File -FilePath (Join-Path $readbackDir 'wbs04_merge_delete_batch3_export_summary.json') -Encoding utf8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# WBS04 merge/delete candidate export readback - batch 3 rest-of-tables')
$lines.Add('')
$lines.Add("- request_id: $requestId")
$lines.Add('- result: success')
$lines.Add('- safety: read-only Airtable export; no writes; no Delete Queue rows; no deletions')
$lines.Add('- scope: batch 3 of 3; full-row/full-field intake for aggressive merge/update/delete-candidate analysis')
$lines.Add('- excluded: Delete Queue plus Batch 1 and Batch 2 tables')
$lines.Add("- output_zip: $($summary.output_zip)")
$lines.Add('')
$lines.Add('| Table | Records exported | Readback file |')
$lines.Add('|---|---:|---|')
foreach ($t in $tableSummaries) {
    $lines.Add("| $($t.table_name) | $($t.record_count_exported) | $($t.records_file) |")
}
$lines | Out-File -FilePath (Join-Path $readbackDir 'wbs04_merge_delete_batch3_export_report.md') -Encoding utf8

Write-Output ($summary | ConvertTo-Json -Depth 12)
