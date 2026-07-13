$ErrorActionPreference = 'Stop'
$requestId = 'exec-20260520-wbs06-final-verify-retirement-packet-001'
$outputPrefix = 'dcoir_wbs06_final_verify_retirement_packet_source'
$expectedTableCount = 21
$tableList = @('Work Items','Session Checkpoints','Idea Inbox','Plans','Operator Preferences','Validation Test Cases','Queue Control','Gemini Research Reference','Governance Control Plane','Repo Surface Registry','dcoir-memory-preflight','dcoir-decision-policy','dcoir-validation-orchestrator','Validation Evidence','Admin Registry','DCOIR Lifecycle Ledger','Local Configuration Registry','Operator Tools Registry','DCOIR Cleanup WBS','DCOIR Cleanup Scaffold Registry','GitHub Workflow Inventory')
$expectedRenames = @(
  [pscustomobject]@{table='Plans';field_id='fldvsVffETaqyuB0H';expected='legacy_active_plan_task_id_review'},
  [pscustomobject]@{table='Plans';field_id='fldLYnjrlPY6QfKNH';expected='legacy_plan_buffer_marker_review'},
  [pscustomobject]@{table='Plans';field_id='fldyfFi5VTw9ffaPq';expected='legacy_pending_plan_buffer_items_review'},
  [pscustomobject]@{table='Plans';field_id='fld4QqRiSFLzEvKuD';expected='legacy_promotion_candidates_review'},
  [pscustomobject]@{table='Plans';field_id='fldzT3tVTcvhSWPNa';expected='legacy_remain_local_notes_review'},
  [pscustomobject]@{table='Plans';field_id='fldZoUV6BFJyKuOhz';expected='legacy_last_updated_text_review'},
  [pscustomobject]@{table='Gemini Research Reference';field_id='fldH0t18dHVNkfTrA';expected='legacy_research_batch_review'},
  [pscustomobject]@{table='GitHub Workflow Inventory';field_id='fldNGAE9cbd9YSYzz';expected='avoid_when'},
  [pscustomobject]@{table='Idea Inbox';field_id='fldyhuC1RXb6TQBu3';expected='github_promotion_completed'},
  [pscustomobject]@{table='GitHub Workflow Inventory';field_id='fldhfcwoRfNHkL1ya';expected='legacy_review_after_date_review'},
  [pscustomobject]@{table='Plans';field_id='fldCC1FicmWE2pra2';expected='legacy_review_after_date_review'},
  [pscustomobject]@{table='Idea Inbox';field_id='fldXRAz2DLHzOQmK2';expected='legacy_source_checkpoint_id_review'},
  [pscustomobject]@{table='Plans';field_id='fldwS46tOH9fTVQSO';expected='legacy_created_at_review'},
  [pscustomobject]@{table='Validation Evidence';field_id='fldOIWWUP1cPo9zEb';expected='legacy_release_key_review'}
)
function Env([string]$n){$v=[Environment]::GetEnvironmentVariable($n,'Process');if([string]::IsNullOrWhiteSpace($v)){$v=[Environment]::GetEnvironmentVariable($n,'Machine')};if([string]::IsNullOrWhiteSpace($v)){throw "Missing env: $n"};return $v.Trim()}
function SaveJson($p,$o,$d=40){$dir=Split-Path -Parent $p;if($dir -and -not(Test-Path -LiteralPath $dir)){New-Item -ItemType Directory -Force -Path $dir|Out-Null};$enc=New-Object System.Text.UTF8Encoding($false);[System.IO.File]::WriteAllText($p,($o|ConvertTo-Json -Depth $d),$enc)}
function IsBlank($v){if($null -eq $v){return $true};if($v -is [string]){return [string]::IsNullOrWhiteSpace($v)};if($v -is [System.Array]){return $v.Count -eq 0};if($v.PSObject -and $v.PSObject.Properties.Count -eq 0){return $true};return $false}
function SafeStr($v){if($null -eq $v){return ''};if($v -is [string]){return $v};try{return (($v|ConvertTo-Json -Depth 8 -Compress) -replace '\s+',' ').Trim()}catch{return [string]$v}}
$repoRoot=Env 'DCOIR_REPO_ROOT';$downloadsDir=Env 'DCOIR_DOWNLOADS_DIR'
$exportScript=Join-Path $repoRoot 'operator_tools\github_desktop_lane\scripts\New-DcoirAirtableDatabaseHealthExport.ps1'
$statusRoot=Join-Path $repoRoot ("chatgpt_staging\status_reports\chatgpt-exec\{0}\wbs06_final_verify_retirement_packet" -f $requestId)
if(Test-Path -LiteralPath $statusRoot){Remove-Item -LiteralPath $statusRoot -Recurse -Force};New-Item -ItemType Directory -Force -Path $statusRoot|Out-Null
$before=@(Get-ChildItem -LiteralPath $downloadsDir -Directory -Filter ($outputPrefix+'_*') -ErrorAction SilentlyContinue|Select-Object -ExpandProperty FullName)
& $exportScript -ExportMode FullRecords -FullRecordDump -MetadataScope 'All' -ProbeUnsupportedMetadata -TableList ($tableList -join ',') -OutputNamePrefix $outputPrefix -NoZip
if($LASTEXITCODE -and $LASTEXITCODE -ne 0){throw "Export failed with exit code $LASTEXITCODE"}
$after=@(Get-ChildItem -LiteralPath $downloadsDir -Directory -Filter ($outputPrefix+'_*') -ErrorAction SilentlyContinue|Sort-Object LastWriteTimeUtc -Descending)
$runFolder=$null;foreach($c in $after){if($before -notcontains $c.FullName){$runFolder=$c;break}};if($null -eq $runFolder){$runFolder=$after|Select-Object -First 1};if($null -eq $runFolder){throw 'No export folder found'}
$manifest=Get-Content -LiteralPath (Join-Path $runFolder.FullName 'export_manifest.json') -Raw|ConvertFrom-Json;$runSummary=Get-Content -LiteralPath (Join-Path $runFolder.FullName 'run_summary.json') -Raw|ConvertFrom-Json
if($runSummary.success -ne $true){throw 'Source export did not report success'};if([int]$manifest.selected_table_count -ne $expectedTableCount){throw "Expected $expectedTableCount tables; observed $($manifest.selected_table_count)"}
Copy-Item -LiteralPath (Join-Path $runFolder.FullName 'export_manifest.json') -Destination (Join-Path $statusRoot 'source_export_manifest.json') -Force;Copy-Item -LiteralPath (Join-Path $runFolder.FullName 'run_summary.json') -Destination (Join-Path $statusRoot 'source_run_summary.json') -Force
$recordsByTable=@{};foreach($rf in @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'records') -Filter '*.records.json' -File)){ $p=Get-Content -LiteralPath $rf.FullName -Raw|ConvertFrom-Json;$recordsByTable[[string]$p.table_id]=$p }
$fields=New-Object System.Collections.Generic.List[object];$fieldMap=@{}
foreach($sf in @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'schema') -Filter 'table.*.schema.json' -File)){ $t=Get-Content -LiteralPath $sf.FullName -Raw|ConvertFrom-Json;$rp=$recordsByTable[[string]$t.id];$recs=@();if($rp -and $rp.records){$recs=@($rp.records)};foreach($f in @($t.fields)){ $bc=0;$nb=0;$obs=New-Object System.Collections.Generic.List[string];foreach($r in $recs){$val=$null;$prop=$r.fields.PSObject.Properties[[string]$f.name];if($prop){$val=$prop.Value};if(IsBlank $val){$bc++}else{$nb++;if($obs.Count -lt 5){$sv=SafeStr $val;if($sv.Length -gt 180){$sv=$sv.Substring(0,180)+'...'};if(-not $obs.Contains($sv)){$obs.Add($sv)|Out-Null}}}};$br=if($recs.Count -gt 0){[Math]::Round(($bc/[double]$recs.Count),4)}else{0.0};$row=[pscustomobject]@{table_name=[string]$t.name;table_id=[string]$t.id;field_id=[string]$f.id;current_name=[string]$f.name;field_type=[string]$f.type;record_count=$recs.Count;blank_count=$bc;nonblank_count=$nb;blank_ratio=$br;observed_values=@($obs.ToArray());legacy_review_name=([string]$f.name -match '^legacy_.*_review$')};$fields.Add($row)|Out-Null;$fieldMap[[string]$f.id]=$row} }
$verify=New-Object System.Collections.Generic.List[object];foreach($e in $expectedRenames){$actual=$fieldMap[[string]$e.field_id];$ok=($actual -and $actual.current_name -eq $e.expected);$verify.Add([pscustomobject]@{table_name=$e.table;field_id=$e.field_id;expected_name=$e.expected;actual_name=if($actual){$actual.current_name}else{$null};verified=[bool]$ok})|Out-Null}
$retire=@($fields.ToArray()|Where-Object {$_.legacy_review_name -eq $true}|Sort-Object table_name,current_name)
SaveJson (Join-Path $statusRoot 'final_field_inventory.json') @($fields.ToArray()) 30;SaveJson (Join-Path $statusRoot 'expected_rename_readback.json') @($verify.ToArray()) 20;SaveJson (Join-Path $statusRoot 'field_retirement_packet_candidates.json') $retire 30
$fields|Select-Object table_name,table_id,field_id,current_name,field_type,record_count,blank_count,nonblank_count,blank_ratio,legacy_review_name|Export-Csv -Path (Join-Path $statusRoot 'final_field_inventory.csv') -NoTypeInformation -Encoding UTF8
$retire|Select-Object table_name,table_id,field_id,current_name,field_type,record_count,blank_count,nonblank_count,blank_ratio|Export-Csv -Path (Join-Path $statusRoot 'field_retirement_packet_candidates.csv') -NoTypeInformation -Encoding UTF8
$fail=@($verify.ToArray()|Where-Object {$_.verified -ne $true})
$summary=[ordered]@{schema='dcoir.wbs06.final_verify_retirement_packet.v1';request_id=$requestId;result=if($fail.Count -eq 0){'success'}else{'verification_failed'};source_export_folder=$runFolder.FullName;selected_table_count=[int]$manifest.selected_table_count;field_count=@($fields.ToArray()).Count;expected_rename_count=@($expectedRenames).Count;expected_rename_verified_count=(@($verify.ToArray()|Where-Object {$_.verified -eq $true}).Count);expected_rename_failed_count=$fail.Count;retirement_candidate_count=$retire.Count;safety=@{airtable_writes=0;field_renames=0;record_updates=0;field_deletes=0;type_conversions=0;delete_queue_rows=0};created_utc=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')}
SaveJson (Join-Path $statusRoot 'wbs06_final_verify_summary.json') $summary 20
$md=@('# WBS06 final verification and retirement packet','',"- request_id: $requestId","- result: $($summary.result)","- tables analyzed: $($summary.selected_table_count)","- fields inventoried: $($summary.field_count)","- expected rename readbacks verified: $($summary.expected_rename_verified_count) / $($summary.expected_rename_count)","- retirement packet candidates: $($summary.retirement_candidate_count)",'- safety: no Airtable writes, no field renames, no record updates, no field deletion, no type conversion, no Delete Queue rows','','## Retirement packet candidates','','| Table | Field ID | Current name | Blank ratio | Nonblank |','|---|---|---|---:|---:|');foreach($x in $retire){$md += "| $($x.table_name) | $($x.field_id) | $($x.current_name) | $($x.blank_ratio) | $($x.nonblank_count) |"};$md|Set-Content -LiteralPath (Join-Path $statusRoot 'wbs06_final_verify_report.md') -Encoding UTF8
if($fail.Count -gt 0){throw 'One or more expected rename readbacks failed'}
Write-Output ($summary|ConvertTo-Json -Depth 20)
