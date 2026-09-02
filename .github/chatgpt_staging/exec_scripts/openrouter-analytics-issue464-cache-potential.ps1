[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$key = [Environment]::GetEnvironmentVariable('OPENROUTER_MANAGEMENT_KEY','Process')
if ([string]::IsNullOrWhiteSpace($key)) { throw 'OPENROUTER_MANAGEMENT_KEY is unavailable.' }
$downloadsDir = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Process')
if ([string]::IsNullOrWhiteSpace($downloadsDir)) { throw 'DCOIR_DOWNLOADS_DIR is unavailable.' }
New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null
$headers = @{ Authorization = "Bearer $key" }

function Write-JsonFile { param([string]$Path,$Value) $Value | ConvertTo-Json -Depth 30 | Out-File -LiteralPath $Path -Encoding utf8 }

$meta = Invoke-RestMethod -Method Get -Uri 'https://openrouter.ai/api/v1/analytics/meta' -Headers $headers -TimeoutSec 60
Write-JsonFile (Join-Path $downloadsDir 'openrouter_analytics_meta.json') $meta
$available = @($meta.data.metrics | ForEach-Object { [string]$_.name })
$wanted = @('tokens_prompt','cached_tokens','possible_cached_tokens','cache_hit_rate','possible_cache_hit_rate','cache_capture_rate')
$metrics = @($wanted | Where-Object { $available -contains $_ })
if ($metrics.Count -eq 0) { throw 'No cache-potential metrics exposed by live meta.' }

$windows = @(
 [ordered]@{run_id='33405123156';start='2026-08-31T14:52:00Z';end='2026-08-31T15:15:45Z'},
 [ordered]@{run_id='33409318802';start='2026-08-31T15:35:30Z';end='2026-08-31T16:02:00Z'},
 [ordered]@{run_id='33415614759';start='2026-08-31T16:42:45Z';end='2026-08-31T16:56:40Z'},
 [ordered]@{run_id='33417552462';start='2026-08-31T17:04:10Z';end='2026-08-31T17:15:05Z'}
)
$results=@()
foreach($w in $windows){
 $body=[ordered]@{metrics=$metrics;dimensions=@('model','provider');time_range=[ordered]@{start=$w.start;end=$w.end};limit=100}
 $name="run_$($w.run_id)_cache_potential"
 $path=Join-Path $downloadsDir ($name+'.json')
 try {
  $r=Invoke-RestMethod -Method Post -Uri 'https://openrouter.ai/api/v1/analytics/query' -Headers $headers -ContentType 'application/json' -Body ($body|ConvertTo-Json -Depth 20 -Compress) -TimeoutSec 60
  Write-JsonFile $path $r
  $results += [pscustomobject]@{name=$name;result='success';output_file=[IO.Path]::GetFileName($path);row_count=$r.data.metadata.row_count;truncated=$r.data.metadata.truncated;error=$null}
 } catch {
  $results += [pscustomobject]@{name=$name;result='failure';output_file=[IO.Path]::GetFileName($path);row_count=$null;truncated=$null;error=$_.Exception.Message}
  Write-JsonFile $path ([ordered]@{name=$name;result='failure';error_message=$_.Exception.Message})
 }
}
Write-JsonFile (Join-Path $downloadsDir 'openrouter_cache_potential_manifest.json') ([ordered]@{schema='dcoir.openrouter_analytics_issue464_cache_potential.v1';generated_at_utc=(Get-Date).ToUniversalTime().ToString('o');purpose='Read-only cache-potential query for exact historical DCOIR windows; no session filter because OpenRouter declares possible-cache metrics incompatible with session_id filters.';inference_endpoints_called=$false;metrics=$metrics;dimensions=@('model','provider');windows=$windows;queries=$results})
$ok=@($results|Where-Object{$_.result -eq 'success'}).Count
$bad=@($results|Where-Object{$_.result -ne 'success'}).Count
Write-Output ("OpenRouter cache-potential collector completed: {0} successful queries, {1} failed queries, no inference endpoints called." -f $ok,$bad)
