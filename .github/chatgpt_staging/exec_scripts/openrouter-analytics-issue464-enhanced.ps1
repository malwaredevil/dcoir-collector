[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$key = [Environment]::GetEnvironmentVariable('OPENROUTER_MANAGEMENT_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($key)) { throw 'OPENROUTER_MANAGEMENT_KEY is unavailable.' }
$downloadsDir = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR', 'Process')
if ([string]::IsNullOrWhiteSpace($downloadsDir)) { throw 'DCOIR_DOWNLOADS_DIR is unavailable.' }
New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null
$headers = @{ Authorization = "Bearer $key" }

function Write-JsonFile {
    param([string]$Path, $Value)
    $Value | ConvertTo-Json -Depth 40 | Out-File -LiteralPath $Path -Encoding utf8
}

$meta = Invoke-RestMethod -Method Get -Uri 'https://openrouter.ai/api/v1/analytics/meta' -Headers $headers -TimeoutSec 60
Write-JsonFile -Path (Join-Path $downloadsDir 'openrouter_analytics_meta.json') -Value $meta
$metricNames = @($meta.data.metrics | ForEach-Object { [string]$_.name })
$dimensionNames = @($meta.data.dimensions | ForEach-Object { [string]$_.name })

$wantedMetrics = @(
    'total_usage','request_count','tokens_total','tokens_prompt','tokens_completion','reasoning_tokens',
    'cached_tokens','possible_cached_tokens','cache_hit_rate','possible_cache_hit_rate','cache_capture_rate',
    'avg_latency','p50_latency','p90_latency','p99_latency',
    'blended_cost_per_million_tokens','avg_throughput','p50_throughput','p90_throughput','p99_throughput',
    'response_cached_count','response_cached_rate','usage_upstream','usage_cache','usage_data',
    'credits_usage','openrouter_usage','byok_usage','byok_fees'
)
$metrics = @($wantedMetrics | Where-Object { $metricNames -contains $_ })
if ($metrics.Count -eq 0) { throw 'No requested metrics are exposed by OpenRouter analytics meta.' }

$sessionDimension = if ($dimensionNames -contains 'session_id') { 'session_id' } elseif ($dimensionNames -contains 'session') { 'session' } else { $null }
$modelDimension = if ($dimensionNames -contains 'model') { 'model' } else { $null }
$providerDimension = if ($dimensionNames -contains 'provider') { 'provider' } else { $null }
$generationDimension = if ($dimensionNames -contains 'generation_id') { 'generation_id' } elseif ($dimensionNames -contains 'generation') { 'generation' } else { $null }
if ($null -eq $sessionDimension) { throw 'OpenRouter analytics meta did not expose a session dimension.' }

$windows = @(
    [ordered]@{ run_id='33405123156'; start='2026-08-31T14:52:00Z'; end='2026-08-31T15:15:45Z' },
    [ordered]@{ run_id='33409318802'; start='2026-08-31T15:35:30Z'; end='2026-08-31T16:02:00Z' },
    [ordered]@{ run_id='33415614759'; start='2026-08-31T16:42:45Z'; end='2026-08-31T16:56:40Z' },
    [ordered]@{ run_id='33417552462'; start='2026-08-31T17:04:10Z'; end='2026-08-31T17:15:05Z' }
)

$results = @()
foreach ($window in $windows) {
    $queryShapes = @(
        [pscustomobject]@{ suffix='by_session'; dimensions=@($sessionDimension) }
    )
    if ($null -ne $modelDimension) {
        $queryShapes += [pscustomobject]@{ suffix='by_session_model'; dimensions=@($sessionDimension,$modelDimension) }
    }
    if ($null -ne $providerDimension) {
        $queryShapes += [pscustomobject]@{ suffix='by_session_provider'; dimensions=@($sessionDimension,$providerDimension) }
    }
    if ($null -ne $generationDimension -and $null -ne $modelDimension) {
        $queryShapes += [pscustomobject]@{ suffix='by_generation_model'; dimensions=@($generationDimension,$modelDimension) }
    }

    foreach ($shape in $queryShapes) {
        $name = "run_$($window.run_id)_$($shape.suffix)"
        $path = Join-Path $downloadsDir ($name + '.json')
        $body = [ordered]@{
            metrics = $metrics
            dimensions = @($shape.dimensions)
            time_range = [ordered]@{ start=$window.start; end=$window.end }
            limit = 2000
        }
        if ($metrics -contains 'total_usage') {
            $body['order_by'] = [ordered]@{ field='total_usage'; direction='desc' }
        }
        try {
            $response = Invoke-RestMethod -Method Post -Uri 'https://openrouter.ai/api/v1/analytics/query' -Headers $headers -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 20 -Compress) -TimeoutSec 60
            Write-JsonFile -Path $path -Value $response
            $results += [pscustomobject]@{ name=$name; result='success'; output_file=[IO.Path]::GetFileName($path); error=$null }
        }
        catch {
            $safe = [ordered]@{ name=$name; result='failure'; error_type=$_.Exception.GetType().FullName; error_message=$_.Exception.Message }
            Write-JsonFile -Path $path -Value $safe
            $results += [pscustomobject]@{ name=$name; result='failure'; output_file=[IO.Path]::GetFileName($path); error=$_.Exception.Message }
        }
    }
}

$manifest = [ordered]@{
    schema='dcoir.openrouter_analytics_issue464_enhanced.v1'
    generated_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    purpose='Read-only historical OpenRouter economics/cache/latency evidence for GitHub issue 464.'
    inference_endpoints_called=$false
    endpoints=@('/api/v1/analytics/meta','/api/v1/analytics/query')
    metrics=$metrics
    dimensions=[ordered]@{ session=$sessionDimension; model=$modelDimension; provider=$providerDimension; generation=$generationDimension }
    windows=$windows
    queries=$results
}
Write-JsonFile -Path (Join-Path $downloadsDir 'openrouter_analytics_enhanced_manifest.json') -Value $manifest
$success = @($results | Where-Object { $_.result -eq 'success' }).Count
$failed = @($results | Where-Object { $_.result -ne 'success' }).Count
Write-Output ("Enhanced OpenRouter analytics completed: {0} successful queries, {1} failed queries, no inference endpoints called." -f $success,$failed)
