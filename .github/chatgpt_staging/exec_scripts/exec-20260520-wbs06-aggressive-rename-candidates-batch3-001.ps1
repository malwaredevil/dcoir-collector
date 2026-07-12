$ErrorActionPreference = 'Stop'
$requestId = 'exec-20260520-wbs06-aggressive-rename-candidates-batch3-001'
$outputPrefix = 'dcoir_wbs06_aggressive_rename_candidates_batch3_source'
$expectedTableCount = 21
$tableList = @('Work Items','Session Checkpoints','Idea Inbox','Plans','Operator Preferences','Validation Test Cases','Queue Control','Gemini Research Reference','Governance Control Plane','Repo Surface Registry','dcoir-memory-preflight','dcoir-decision-policy','dcoir-validation-orchestrator','Validation Evidence','Admin Registry','DCOIR Lifecycle Ledger','Local Configuration Registry','Operator Tools Registry','DCOIR Cleanup WBS','DCOIR Cleanup Scaffold Registry','GitHub Workflow Inventory')
function Env([string]$n){ $v=[Environment]::GetEnvironmentVariable($n,'Process'); if([string]::IsNullOrWhiteSpace($v)){ $v=[Environment]::GetEnvironmentVariable($n,'Machine') }; if([string]::IsNullOrWhiteSpace($v)){ throw "Missing env: $n" }; return $v.Trim() }
function SaveJson($p,$o,$d=40){ $dir=Split-Path -Parent $p; if($dir -and -not(Test-Path -LiteralPath $dir)){ New-Item -ItemType Directory -Force -Path $dir|Out-Null }; $enc=New-Object System.Text.UTF8Encoding($false); [System.IO.File]::WriteAllText($p,($o|ConvertTo-Json -Depth $d),$enc) }
function IsBlank($v){ if($null -eq $v){return $true}; if($v -is [string]){return [string]::IsNullOrWhiteSpace($v)}; if($v -is [System.Array]){return $v.Count -eq 0}; if($v.PSObject -and $v.PSObject.Properties.Count -eq 0){return $true}; return $false }
function SafeName([string]$name){ $n=$name.Trim().ToLowerInvariant(); $n=$n -replace '[^a-z0-9]+','_'; return ($n -replace '_+','_').Trim('_') }
function LegacyName([string]$name){ $n=SafeName $name; $n=$n -replace '(^|_)do_not_use($|_)','_'; $n=$n -replace '(^|_)deprecated($|_)','_'; $n=$n -replace '(^|_)old($|_)','_'; $n=($n -replace '_+','_').Trim('_'); if([string]::IsNullOrWhiteSpace($n)){ $n='field' }; if($n -notmatch '^legacy_'){ $n='legacy_'+$n }; if($n -notmatch '_review$'){ $n=$n+'_review' }; return ($n -replace '_+','_') }
function Proposal($t,$f,[int]$rc,[double]$br){
  $name=[string]$f.name; $s=SafeName $name; $type=[string]$f.type
  if([string]$f.id -eq [string]$t.primaryFieldId){return $null}
  if(@('formula','rollup','lookup','count','createdTime','lastModifiedTime','createdBy','lastModifiedBy','autoNumber','multipleRecordLinks') -contains $type){return $null}
  if($s -match '^legacy_.*_review$'){return $null}
  if($s -match '^(avoid_when|github_promotion_completed)$'){return $null}
  if($name -match '__' -or $s -match 'do_not_use|deprecated'){return [pscustomobject]@{proposed_name=(LegacyName $name);category='legacy_normalization';reason='Normalize deprecated/do-not-use/double-underscore naming.'}}
  $trans='(flush|pending|candidate|scratch|temp|buffer|local|stale|migration|remain|unused|orphan|draft|backfill|temporary|obsolete|legacy)'
  if($rc -gt 0 -and $br -eq 1.0 -and $s -match $trans){return [pscustomobject]@{proposed_name=(LegacyName $name);category='blank_transitional';reason='Fully blank transitional/legacy helper field.'}}
  if($rc -gt 0 -and $br -ge 0.95 -and $s -match $trans){return [pscustomobject]@{proposed_name=(LegacyName $name);category='sparse_transitional';reason='Highly sparse transitional/legacy helper field.'}}
  return $null
}
$repoRoot=Env 'DCOIR_REPO_ROOT'; $downloadsDir=Env 'DCOIR_DOWNLOADS_DIR'
$exportScript=Join-Path $repoRoot 'operator_tools\github_desktop_lane\scripts\New-DcoirAirtableDatabaseHealthExport.ps1'
$statusRoot=Join-Path $repoRoot ("chatgpt_staging\status_reports\chatgpt-exec\{0}\wbs06_aggressive_rename_candidates_batch3" -f $requestId)
if(Test-Path -LiteralPath $statusRoot){Remove-Item -LiteralPath $statusRoot -Recurse -Force}; New-Item -ItemType Directory -Force -Path $statusRoot|Out-Null
$before=@(Get-ChildItem -LiteralPath $downloadsDir -Directory -Filter ($outputPrefix+'_*') -ErrorAction SilentlyContinue|Select-Object -ExpandProperty FullName)
& $exportScript -ExportMode FullRecords -FullRecordDump -MetadataScope 'All' -ProbeUnsupportedMetadata -TableList ($tableList -join ',') -OutputNamePrefix $outputPrefix -NoZip
$after=@(Get-ChildItem -LiteralPath $downloadsDir -Directory -Filter ($outputPrefix+'_*') -ErrorAction SilentlyContinue|Sort-Object LastWriteTimeUtc -Descending)
$runFolder=$null; foreach($c in $after){ if($before -notcontains $c.FullName){$runFolder=$c; break} }; if($null -eq $runFolder){$runFolder=$after|Select-Object -First 1}; if($null -eq $runFolder){throw 'No export folder found'}
$manifest=Get-Content -LiteralPath (Join-Path $runFolder.FullName 'export_manifest.json') -Raw|ConvertFrom-Json; $runSummary=Get-Content -LiteralPath (Join-Path $runFolder.FullName 'run_summary.json') -Raw|ConvertFrom-Json
if($runSummary.success -ne $true){throw 'Export failed'}; if([int]$manifest.selected_table_count -ne $expectedTableCount){throw "Expected $expectedTableCount tables; observed $($manifest.selected_table_count)"}
Copy-Item -LiteralPath (Join-Path $runFolder.FullName 'export_manifest.json') -Destination (Join-Path $statusRoot 'source_export_manifest.json') -Force; Copy-Item -LiteralPath (Join-Path $runFolder.FullName 'run_summary.json') -Destination (Join-Path $statusRoot 'source_run_summary.json') -Force
$recordsByTable=@{}; foreach($rf in @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'records') -Filter '*.records.json' -File)){ $p=Get-Content -LiteralPath $rf.FullName -Raw|ConvertFrom-Json; $recordsByTable[[string]$p.table_id]=$p }
$rows=New-Object System.Collections.Generic.List[object]
foreach($sf in @(Get-ChildItem -LiteralPath (Join-Path $runFolder.FullName 'schema') -Filter 'table.*.schema.json' -File)){ $t=Get-Content -LiteralPath $sf.FullName -Raw|ConvertFrom-Json; $rp=$recordsByTable[[string]$t.id]; $recs=@(); if($rp -and $rp.records){$recs=@($rp.records)}; foreach($f in @($t.fields)){ $bc=0;$nb=0; foreach($r in $recs){ $v=$null; $prop=$r.fields.PSObject.Properties[[string]$f.name]; if($prop){$v=$prop.Value}; if(IsBlank $v){$bc++}else{$nb++} }; $br=if($recs.Count -gt 0){[Math]::Round(($bc/[double]$recs.Count),4)}else{0.0}; $pr=Proposal $t $f $recs.Count $br; $rows.Add([pscustomobject]@{table_name=[string]$t.name;table_id=[string]$t.id;field_id=[string]$f.id;current_name=[string]$f.name;field_type=[string]$f.type;record_count=$recs.Count;blank_count=$bc;nonblank_count=$nb;blank_ratio=$br;proposed_name=if($pr){$pr.proposed_name}else{$null};action=if($pr){'rename_candidate'}else{'no_change'};category=if($pr){$pr.category}else{$null};reason=if($pr){$pr.reason}else{$null}})|Out-Null } }
$ranked=@($rows.ToArray()|Where-Object {$_.action -eq 'rename_candidate' -and $_.current_name -ne $_.proposed_name}|Sort-Object table_name,current_name)
SaveJson (Join-Path $statusRoot 'field_inventory_with_candidates.json') @($rows.ToArray()) 30; SaveJson (Join-Path $statusRoot 'rename_candidates_ranked.json') $ranked 30
$rows|Select-Object table_name,table_id,field_id,current_name,field_type,record_count,blank_count,nonblank_count,blank_ratio,proposed_name,action,category,reason|Export-Csv -Path (Join-Path $statusRoot 'field_inventory_with_candidates.csv') -NoTypeInformation -Encoding UTF8
$summary=[ordered]@{schema='dcoir.wbs06.aggressive_rename_candidates.v1';request_id=$requestId;result='success';source_export_folder=$runFolder.FullName;selected_table_count=[int]$manifest.selected_table_count;field_inventory_count=@($rows.ToArray()).Count;candidate_count=$ranked.Count;safety=@{airtable_writes=0;field_renames=0;record_updates=0;field_deletes=0;type_conversions=0;delete_queue_rows=0};created_utc=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')}
SaveJson (Join-Path $statusRoot 'aggressive_rename_candidates_summary.json') $summary 20
$md=@('# WBS06 aggressive rename candidates batch 3','',"- request_id: $requestId","- result: success","- tables analyzed: $($summary.selected_table_count)","- fields inventoried: $($summary.field_inventory_count)","- candidates found: $($summary.candidate_count)",'- safety: no Airtable writes; candidate generation only','','| Table | Field ID | Current name | Proposed name | Blank ratio | Category |','|---|---|---|---|---:|---|'); foreach($x in @($ranked|Select-Object -First 40)){ $md += "| $($x.table_name) | $($x.field_id) | $($x.current_name) | $($x.proposed_name) | $($x.blank_ratio) | $($x.category) |" }; $md|Set-Content -LiteralPath (Join-Path $statusRoot 'aggressive_rename_candidates_report.md') -Encoding UTF8
Write-Output ($summary|ConvertTo-Json -Depth 20)
