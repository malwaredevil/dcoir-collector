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
$sessionId = 'dcoir-review:malwaredevil-dcoir-collector:pr-448'

function Write-JsonFile {
    param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)]$Value)
    $Value | ConvertTo-Json -Depth 40 | Out-File -LiteralPath $Path -Encoding utf8
}

function Get-SafeHttpErrorBody {
    param([Parameter(Mandatory=$true)]$ErrorRecord)
    try {
        $response = $ErrorRecord.Exception.Response
        if ($null -eq $response) { return $null }
        $stream = $response.GetResponseStream()
        if ($null -eq $stream) { return $null }
        $reader = New-Object System.IO.StreamReader($stream)
        try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    }
    catch { return $null }
}

$meta = Invoke-RestMethod -Method Get -Uri 'https://openrouter.ai/api/v1/analytics/meta' -Headers $headers -TimeoutSec 60
Write-JsonFile -Path (Join-Path $downloadsDir 'openrouter_analytics_meta.json') -Value $meta
$metricNames = @($meta.data.metrics | ForEach-Object { [string]$_.name })
$dimensionNames = @($meta.data.dimensions | ForEach-Object { [string]$_.name })
if (-not ($dimensionNames -contains 'session_id')) { throw 'Live analytics schema does not expose session_id.' }
if (-not ($dimensionNames -contains 'model')) { throw 'Live analytics schema does not expose model.' }
if (-not ($dimensionNames -contains 'provider')) { throw 'Live analytics schema does not expose provider.' }

$groupDefinitions = [ordered]@{
    cache_efficiency = @('tokens_prompt','cached_tokens','possible_cached_tokens','cache_hit_rate','possible_cache_hit_rate','cache_capture_rate')
    cost_breakdown = @('total_usage','usage_upstream','usage_cache','usage_data','credits_usage','openrouter_usage')
    latency = @('request_count','avg_latency','p50_latency','p90_latency','p99_latency')
    throughput = @('request_count','avg_throughput','p50_throughput','p90_throughput','p99_throughput')
    response_cache = @('request_count','response_cached_count','response_cached_rate')
}

$groups = [ordered]@{}
foreach ($groupName in $groupDefinitions.Keys) {
    $available = @($groupDefinitions[$groupName] | Where-Object { $metricNames -contains $_ })
    if ($available.Count -gt 0) { $groups[$groupName] = $available }
}

$windows = @(
    [ordered]@{ run_id='33405123156'; start='2026-08-31T14:52:00Z'; end='2026-08-31T15:15:45Z' },
    [ordered]@{ run_id='33409318802'; start='2026-08-31T15:35:30Z'; end='2026-08-31T16:02:00Z' },
    [ordered]@{ run_id='33415614759'; start='2026-08-31T16:42:45Z'; end='2026-08-31T16:56:40Z' },
    [ordered]@{ run_id='33417552462'; start='2026-08-31T17:04:10Z'; end='2026-08-31T17:15:05Z' }
)

$results = @()
foreach ($window in $windows) {
    foreach ($groupName in $groups.Keys) {
        $metrics = @($groups[$groupName])
        $name = "run_$($window.run_id)_$groupName"
        $path = Join-Path $downloadsDir ($name + '.json')
        $body = [ordered]@{
            metrics = $metrics
            dimensions = @('model','provider')
            time_range = [ordered]@{ start=$window.start; end=$window.end }
            filters = @(
                [ordered]@{ field='session_id'; operator='eq'; value=$sessionId }
            )
            limit = 100
        }
        if ($metrics -contains 'total_usage') {
            $body['order_by'] = [ordered]@{ field='total_usage'; direction='desc' }
        }
        elseif ($metrics -contains 'request_count') {
            $body['order_by'] = [ordered]@{ field='request_count'; direction='desc' }
        }

        try {
            $response = Invoke-RestMethod -Method Post -Uri 'https://openrouter.ai/api/v1/analytics/query' -Headers $headers -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 20 -Compress) -TimeoutSec 60
            Write-JsonFile -Path $path -Value $response
            $metadata = $null
            if ($response.PSObject.Properties.Name -contains 'data' -and $null -ne $response.data -and $response.data.PSObject.Properties.Name -contains 'metadata') {
                $metadata = $response.data.metadata
            }
            $results += [pscustomobject]@{
                name=$name; result='success'; output_file=[IO.Path]::GetFileName($path); metrics=$metrics;
                row_count=if ($null -ne $metadata) { $metadata.row_count } else { $null };
                truncated=if ($null -ne $metadata) { $metadata.truncated } else { $null };
                error=$null
            }
        }
        catch {
            $httpBody = Get-SafeHttpErrorBody -ErrorRecord $_
            $safe = [ordered]@{
                name=$name
                result='failure'
                metrics=$metrics
                error_type=$_.Exception.GetType().FullName
                error_message=$_.Exception.Message
                http_error_body=$httpBody
            }
            Write-JsonFile -Path $path -Value $safe
            $results += [pscustomobject]@{
                name=$name; result='failure'; output_file=[IO.Path]::GetFileName($path); metrics=$metrics;
                row_count=$null; truncated=$null; error=$_.Exception.Message
            }
        }
    }
}

$manifest = [ordered]@{
    schema='dcoir.openrouter_analytics_issue464_grouped.v1'
    generated_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    purpose='Session-filtered, read-only OpenRouter analytics evidence grouped by compatible metric family for GitHub issue 464.'
    inference_endpoints_called=$false
    endpoints=@('/api/v1/analytics/meta','/api/v1/analytics/query')
    session_id=$sessionId
    group_metrics=$groups
    dimensions=@('model','provider')
    windows=$windows
    queries=$results
}
Write-JsonFile -Path (Join-Path $downloadsDir 'openrouter_analytics_grouped_manifest.json') -Value $manifest

$success = @($results | Where-Object { $_.result -eq 'success' }).Count
$failed = @($results | Where-Object { $_.result -ne 'success' }).Count
Write-Output ("Grouped OpenRouter analytics completed: {0} successful queries, {1} failed queries, no inference endpoints called." -f $success,$failed)
