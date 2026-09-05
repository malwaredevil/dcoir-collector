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
    $Value | ConvertTo-Json -Depth 50 | Out-File -LiteralPath $Path -Encoding utf8
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
        outcome = 'failed-runtime-integration'
        comparison_role = 'partial-detector-heavy-cost-signal'
    },
    [ordered]@{
        name = 'architecture_b_transient_credit_failure_33962385719'
        run_id = '33962385719'
        session_id = 'dcoir-review:malwaredevil-dcoir-collector:pr-479'
        start = '2026-09-05T11:05:24Z'
        end = '2026-09-05T11:21:46Z'
        target_head = '32dfa2ff7df56481bcf476b75e21dd9cafe3eb37'
        outcome = 'failed-transient-credit-at-verifier'
        comparison_role = 'failure-cost-signal'
    },
    [ordered]@{
        name = 'architecture_b_successful_anchor_33965096173'
        run_id = '33965096173'
        session_id = 'dcoir-review:malwaredevil-dcoir-collector:pr-479'
        start = '2026-09-05T12:06:19Z'
        end = '2026-09-05T12:30:35Z'
        target_head = '32dfa2ff7df56481bcf476b75e21dd9cafe3eb37'
        outcome = 'successful-anchor-one-true-positive'
        comparison_role = 'architecture-b-initial-cumulative-anchor'
    },
    [ordered]@{
        name = 'architecture_b_incremental_acceptance_33972246508'
        run_id = '33972246508'
        session_id = 'dcoir-review:malwaredevil-dcoir-collector:pr-479'
        start = '2026-09-05T14:35:11Z'
        end = '2026-09-05T14:37:04Z'
        target_head = '89bf8634fdc8d934a22c6919150380118f5daa18'
        outcome = 'successful-zero-published'
        comparison_role = 'architecture-b-small-delta-acceptance'
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
}

$manifest = [ordered]@{
    schema='dcoir.openrouter_analytics_issue478_successful_replay.v1'
    generated_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    purpose='Read-only OpenRouter economics/provider/cache evidence for the fixed-stack Architecture-B live replay, including successful anchor and small-delta acceptance run.'
    inference_endpoints_called=$false
    endpoints=@('/api/v1/analytics/meta','/api/v1/analytics/query')
    cases=$cases
    group_metrics=$groups
    queries=$results
    interpretation=@(
        'Do not combine detector-heavy, failed, initial-anchor, and small-delta runs into one undifferentiated mean.',
        'The acceptance comparison is historical_baseline_33417552462 versus architecture_b_incremental_acceptance_33972246508.',
        'The successful 31-file anchor is measured separately because an initial deep review is expected to retain the full quality floor.',
        'No inference endpoint is called by this collector.'
    )
}
Write-JsonFile -Path (Join-Path $out 'openrouter_issue478_successful_replay_manifest.json') -Value $manifest
$success = @($results | Where-Object { $_.result -eq 'success' }).Count
$failed = @($results | Where-Object { $_.result -ne 'success' }).Count
Write-Output ("Issue 478 successful-replay OpenRouter analytics completed: {0} successful queries, {1} failed queries, no inference endpoints called." -f $success,$failed)
