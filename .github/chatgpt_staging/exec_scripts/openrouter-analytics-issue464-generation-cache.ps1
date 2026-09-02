[CmdletBinding()]
param()
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$key=[Environment]::GetEnvironmentVariable('OPENROUTER_MANAGEMENT_KEY','Process')
if([string]::IsNullOrWhiteSpace($key)){throw 'OPENROUTER_MANAGEMENT_KEY is unavailable.'}
$out=[Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Process')
if([string]::IsNullOrWhiteSpace($out)){throw 'DCOIR_DOWNLOADS_DIR is unavailable.'}
New-Item -ItemType Directory -Force -Path $out|Out-Null
$headers=@{Authorization="Bearer $key"}
function W([string]$p,$v){$v|ConvertTo-Json -Depth 30|Out-File -LiteralPath $p -Encoding utf8}
$meta=Invoke-RestMethod -Method Get -Uri 'https://openrouter.ai/api/v1/analytics/meta' -Headers $headers -TimeoutSec 60
W (Join-Path $out 'openrouter_analytics_meta.json') $meta
$avail=@($meta.data.metrics|ForEach-Object{[string]$_.name})
$metrics=@('tokens_prompt','cached_tokens','possible_cached_tokens','cache_hit_rate','possible_cache_hit_rate','cache_capture_rate'|Where-Object{$avail -contains $_})
$windows=@(
 [ordered]@{run_id='33405123156';start='2026-08-31T14:52:00Z';end='2026-08-31T15:15:45Z'},
 [ordered]@{run_id='33409318802';start='2026-08-31T15:35:30Z';end='2026-08-31T16:02:00Z'},
 [ordered]@{run_id='33415614759';start='2026-08-31T16:42:45Z';end='2026-08-31T16:56:40Z'},
 [ordered]@{run_id='33417552462';start='2026-08-31T17:04:10Z';end='2026-08-31T17:15:05Z'}
)
$results=@()
foreach($w in $windows){
 $name="run_$($w.run_id)_generation_cache"
 $path=Join-Path $out ($name+'.json')
 $body=[ordered]@{metrics=$metrics;dimensions=@('generation_id','model');time_range=[ordered]@{start=$w.start;end=$w.end};limit=10000}
 try{
  $r=Invoke-RestMethod -Method Post -Uri 'https://openrouter.ai/api/v1/analytics/query' -Headers $headers -ContentType 'application/json' -Body ($body|ConvertTo-Json -Depth 20 -Compress) -TimeoutSec 60
  W $path $r
  $results+=[pscustomobject]@{name=$name;result='success';row_count=$r.data.metadata.row_count;truncated=$r.data.metadata.truncated;error=$null}
 }catch{
  W $path ([ordered]@{name=$name;result='failure';error_message=$_.Exception.Message})
  $results+=[pscustomobject]@{name=$name;result='failure';row_count=$null;truncated=$null;error=$_.Exception.Message}
 }
}
W (Join-Path $out 'openrouter_generation_cache_manifest.json') ([ordered]@{schema='dcoir.openrouter_analytics_issue464_generation_cache.v1';generated_at_utc=(Get-Date).ToUniversalTime().ToString('o');purpose='Generation-level cache-potential analytics for local intersection with exact DCOIR generation IDs; no inference calls.';inference_endpoints_called=$false;metrics=$metrics;dimensions=@('generation_id','model');windows=$windows;queries=$results})
$ok=@($results|Where-Object{$_.result -eq 'success'}).Count;$bad=@($results|Where-Object{$_.result -ne 'success'}).Count
Write-Output ("Generation-level OpenRouter cache collector completed: {0} successful queries, {1} failed queries, no inference endpoints called." -f $ok,$bad)
