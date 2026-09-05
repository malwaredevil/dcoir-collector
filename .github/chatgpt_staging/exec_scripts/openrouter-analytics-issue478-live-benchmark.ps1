[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$key = [Environment]::GetEnvironmentVariable('OPENROUTER_MANAGEMENT_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($key)) { throw 'OPENROUTER_MANAGEMENT_KEY is unavailable.' }
$out = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR', 'Process')
if ([string]::IsNullOrWhiteSpace($out)) { throw 'DCOIR_DOWNLOADS_DIR is unavailable.' }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$headers = @{ Authorization = "Bearer $key" }

function Write-JsonFile {
    param([string]$Path, $Value)
    $Value | ConvertTo-Json -Depth 40 | Out-File -LiteralPath $Path -Encoding utf8
}

function Get-SafeHttpErrorBody {
    param($ErrorRecord)
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

$cases = @(
    [ordered]@{
        name = 'historical_baseline_33417552462'
        run_id = '33417552462'
        session_id = 'dcoir-review:malwaredevil-dcoir-collector:pr-448'
        start = '2026-08-31T17:04:10Z'
        end = '2026-08-31T17:15:05Z'
        target_head = '89bf8634fdc8d934a22c6919150380118f5daa18'
        outcome = 'historical-success-zero-published'
        comparison_role = 'pre-architecture-b-cumulative-baseline'
    },
    [ordered]@{
        name = 'architecture_b_failed_anchor_33954836006'
        run_id = '33954836006'
        session_id = 'dcoir-review:malwaredevil-dcoir-collector:pr-479'
        start = '2026-09-05T08:16:45Z'
        end = '2026-09-05T08:25:20Z'
        target_head = '32dfa2ff7df56481bcf476b75e21dd9cafe3eb37'
        outcome = 'failed-before-reviewed-head-publication'
        comparison_role = 'architecture-b-partial-anchor-cost-signal-not-acceptance'
    }
)

$meta = Invoke-RestMethod -Method Get -Uri 'https://openrouter.ai/api/v1/analytics/meta' -Headers $headers -TimeoutSec 60
Write-JsonFile -Path (Join-Path $out 'openrouter_analytics_meta.json') -Value $meta
$metricNames = @($meta.data.metrics | ForEach-Object { [string]$_.name })
$dimensionNames = @($meta.data.dimensions | ForEach-Object { [string]$_.name })
foreach ($requiredDimension in @('session_id','model','provider')) {
    if (-not ($dimensionNames -contains $requiredDimension)) { throw "Live analytics schema does not expose $requiredDimension." }
}

$groupDefinitions = [ordered]@{
    tokens = @('request_count','tokens_total','tokens_prompt','tokens_completion','reasoning_tokens','cached_tokens')
    cost = @('request_count','total_usage','usage_upstream','usage_cache','usage_data','credits_usage','openrouter_usage','byok_usage','byok_fees')
    latency = @('request_count','avg_latency','p50_latency','p90_latency','p99_latency')
    throughput = @('request_count','avg_throughput','p50_throughput','p90_throughput','p99_throughput')
    response_cache = @('request_count','response_cached_count','response_cached_rate')
}
$groups = [ordered]@{}
foreach ($groupName in $groupDefinitions.Keys) {
    $available = @($groupDefinitions[$groupName] | Where-Object { $metricNames -contains $_ })
    if ($available.Count -gt 0) { $groups[$groupName] = $available }
}

$results = @()
foreach ($case in $cases) {
    foreach ($groupName in $groups.Keys) {
        $metrics = @($groups[$groupName])
        $name = "$($case.name)_$groupName"
        $path = Join-Path $out ($name + '.json')
        $body = [ordered]@{
            metrics = $metrics
            dimensions = @('model','provider')
            time_range = [ordered]@{ start=$case.start; end=$case.end }
            filters = @([ordered]@{ field='session_id'; operator='eq'; value=$case.session_id })
            limit = 200
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
            if ($response.PSObject.Properties.Name -contains 'data' -and $null -ne $response.data -and $response.data.PSObject.Properties.Name -contains 'metadata') { $metadata = $response.data.metadata }
            $results += [pscustomobject]@{
                name=$name; result='success'; output_file=[IO.Path]::GetFileName($path); metrics=$metrics;
                row_count=if ($null -ne $metadata) { $metadata.row_count } else { $null };
                truncated=if ($null -ne $metadata) { $metadata.truncated } else { $null };
                error=$null
            }
        }
        catch {
            $safe = [ordered]@{
                name=$name; result='failure'; metrics=$metrics;
                error_type=$_.Exception.GetType().FullName; error_message=$_.Exception.Message;
                http_error_body=(Get-SafeHttpErrorBody -ErrorRecord $_)
            }
            Write-JsonFile -Path $path -Value $safe
            $results += [pscustomobject]@{ name=$name; result='failure'; output_file=[IO.Path]::GetFileName($path); metrics=$metrics; row_count=$null; truncated=$null; error=$_.Exception.Message }
        }
    }

    if ($dimensionNames -contains 'generation_id') {
        $generationMetrics = @('request_count','total_usage','tokens_total','tokens_prompt','tokens_completion','reasoning_tokens','cached_tokens' | Where-Object { $metricNames -contains $_ })
        if ($generationMetrics.Count -gt 0) {
            $name = "$($case.name)_generations"
            $path = Join-Path $out ($name + '.json')
            $body = [ordered]@{
                metrics = $generationMetrics
                dimensions = @('generation_id','model','provider')
                time_range = [ordered]@{ start=$case.start; end=$case.end }
                filters = @([ordered]@{ field='session_id'; operator='eq'; value=$case.session_id })
                limit = 5000
            }
            try {
                $response = Invoke-RestMethod -Method Post -Uri 'https://openrouter.ai/api/v1/analytics/query' -Headers $headers -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 20 -Compress) -TimeoutSec 60
                Write-JsonFile -Path $path -Value $response
                $results += [pscustomobject]@{ name=$name; result='success'; output_file=[IO.Path]::GetFileName($path); metrics=$generationMetrics; row_count=$response.data.metadata.row_count; truncated=$response.data.metadata.truncated; error=$null }
            }
            catch {
                Write-JsonFile -Path $path -Value ([ordered]@{ name=$name; result='failure'; error_message=$_.Exception.Message })
                $results += [pscustomobject]@{ name=$name; result='failure'; output_file=[IO.Path]::GetFileName($path); metrics=$generationMetrics; row_count=$null; truncated=$null; error=$_.Exception.Message }
            }
        }
    }
}

$manifest = [ordered]@{
    schema='dcoir.openrouter_analytics_issue478_live_benchmark.v1'
    generated_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    purpose='Read-only OpenRouter token/cost/provider/cache/latency evidence for the fixed-stack Architecture-B live acceptance benchmark.'
    inference_endpoints_called=$false
    endpoints=@('/api/v1/analytics/meta','/api/v1/analytics/query')
    cases=$cases
    group_metrics=$groups
    queries=$results
    interpretation=@(
        'The historical baseline is the pre-Architecture-B cumulative run on target head 89bf8634.',
        'The current Architecture-B run failed before successful reviewed-head publication and is only a partial cost/time signal; it is not the small-delta acceptance comparison.',
        'The acceptance comparison remains the later successful PR #479 second run on target head 89bf8634 after a successful Architecture-B anchor review at 32dfa2ff.'
    )
}
Write-JsonFile -Path (Join-Path $out 'openrouter_issue478_live_benchmark_manifest.json') -Value $manifest
$success = @($results | Where-Object { $_.result -eq 'success' }).Count
$failed = @($results | Where-Object { $_.result -ne 'success' }).Count
Write-Output ("Issue 478 OpenRouter analytics completed: {0} successful queries, {1} failed queries, no inference endpoints called." -f $success,$failed)
