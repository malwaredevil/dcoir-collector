$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$requestId = 'exec-20260519-wbs04-four-table-export-002'
$tableList = 'Work Items,Session Checkpoints,Validation Evidence,Admin Registry'
$outputPrefix = 'dcoir_wbs04_four_table_export'

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'Missing Machine/System environment variable: DCOIR_REPO_ROOT' }

$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'Missing Machine/System environment variable: DCOIR_DOWNLOADS_DIR' }

$exportScript = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\New-DcoirAirtableDatabaseHealthExport.ps1'
if (-not (Test-Path -LiteralPath $exportScript -PathType Leaf)) { throw "Airtable export script not found: $exportScript" }

$reportDir = Join-Path $repo (Join-Path 'chatgpt_staging\status_reports\chatgpt-exec' $requestId)
$readbackDir = Join-Path $reportDir 'wbs04_export_readback'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
if (Test-Path -LiteralPath $readbackDir) { Remove-Item -LiteralPath $readbackDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $readbackDir | Out-Null

$before = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter ($outputPrefix + '_*') -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)

& $exportScript -ExportMode FullRecords -FullRecordDump -MetadataScope 'All' -ProbeUnsupportedMetadata -TableList $tableList -OutputNamePrefix $outputPrefix
if (-not $?) { throw 'Airtable export script returned a non-success status.' }

$after = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter ($outputPrefix + '_*') -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
$runFolder = $null
foreach ($candidate in $after) {
    if ($before -notcontains $candidate.FullName) { $runFolder = $candidate; break }
}
if ($null -eq $runFolder) { $runFolder = $after | Select-Object -First 1 }
if ($null -eq $runFolder) { throw 'Could not locate Airtable export output folder.' }

$runSummaryPath = Join-Path $runFolder.FullName 'run_summary.json'
$exportManifestPath = Join-Path $runFolder.FullName 'export_manifest.json'
if (-not (Test-Path -LiteralPath $runSummaryPath -PathType Leaf)) { throw "Missing run_summary.json in export folder: $($runFolder.FullName)" }
if (-not (Test-Path -LiteralPath $exportManifestPath -PathType Leaf)) { throw "Missing export_manifest.json in export folder: $($runFolder.FullName)" }

$runSummary = Get-Content -LiteralPath $runSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$exportManifest = Get-Content -LiteralPath $exportManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($runSummary.success -ne $true) { throw 'Airtable export run_summary reported success=false.' }
if ([int]$exportManifest.selected_table_count -ne 4) { throw "Expected 4 selected tables; got $($exportManifest.selected_table_count)." }

Copy-Item -LiteralPath $runSummaryPath -Destination (Join-Path $readbackDir 'run_summary.json') -Force
Copy-Item -LiteralPath $exportManifestPath -Destination (Join-Path $readbackDir 'export_manifest.json') -Force
foreach ($relative in @('diagnostic_index.md','command_context.json','metadata\metadata_coverage.json','schema\schema.summary.json')) {
    $source = Join-Path $runFolder.FullName $relative
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        $dest = Join-Path $readbackDir ($relative -replace '[\\/]', '_')
        Copy-Item -LiteralPath $source -Destination $dest -Force
    }
}

$recordReadbackDir = Join-Path $readbackDir 'records'
New-Item -ItemType Directory -Force -Path $recordReadbackDir | Out-Null
$recordFiles = @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'records') -Filter '*.records.json' -File -ErrorAction Stop | Sort-Object Name)
foreach ($file in $recordFiles) {
    Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $recordReadbackDir $file.Name) -Force
}

$tableSummaries = @()
foreach ($file in $recordFiles) {
    $recordPayload = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $tableSummaries += [pscustomobject]@{
        table_name = [string]$recordPayload.table_name
        table_id = [string]$recordPayload.table_id
        record_count_exported = [int]$recordPayload.record_count_exported
        records_file = 'records/' + $file.Name
    }
}

$summary = [ordered]@{
    schema = 'dcoir.wbs04.four_table_export.readback.v1'
    request_id = $requestId
    success = $true
    purpose = 'Read-only WBS04 four-table export for duplicate-prevention and cleanup candidate analysis.'
    table_list = @('Work Items','Session Checkpoints','Validation Evidence','Admin Registry')
    selected_table_count = [int]$exportManifest.selected_table_count
    export_mode = [string]$exportManifest.export_mode
    full_record_dump = [bool]$exportManifest.full_record_dump
    read_only_airtable = $true
    no_airtable_writes = $true
    no_delete_queue_rows = $true
    no_record_deletions = $true
    output_folder = [string]$runFolder.FullName
    output_zip = [string]$runSummary.output_zip
    tables = @($tableSummaries)
    created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$summary | ConvertTo-Json -Depth 12 | Out-File -FilePath (Join-Path $readbackDir 'wbs04_four_table_export_summary.json') -Encoding utf8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# WBS04 four-table Airtable export readback')
$lines.Add('')
$lines.Add("- request_id: $requestId")
$lines.Add('- result: success')
$lines.Add('- safety: read-only Airtable export; no writes; no Delete Queue rows; no deletions')
$lines.Add("- output_zip: $($summary.output_zip)")
$lines.Add('')
$lines.Add('| Table | Records exported | Readback file |')
$lines.Add('|---|---:|---|')
foreach ($t in $tableSummaries) {
    $lines.Add("| $($t.table_name) | $($t.record_count_exported) | $($t.records_file) |")
}
$lines | Out-File -FilePath (Join-Path $readbackDir 'wbs04_four_table_export_report.md') -Encoding utf8

Write-Output ($summary | ConvertTo-Json -Depth 12)
