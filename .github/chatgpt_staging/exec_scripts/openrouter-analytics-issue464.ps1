[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$key = [Environment]::GetEnvironmentVariable('OPENROUTER_MANAGEMENT_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($key)) {
    throw 'OPENROUTER_MANAGEMENT_KEY is not available to the approved analytics collector.'
}

$downloadsDir = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR', 'Process')
if ([string]::IsNullOrWhiteSpace($downloadsDir)) {
    throw 'DCOIR_DOWNLOADS_DIR is not available.'
}
New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null

$headers = @{
    Authorization = "Bearer $key"
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)]$Value
    )
    $Value | ConvertTo-Json -Depth 30 | Out-File -LiteralPath $Path -Encoding utf8
}

function Get-AvailableNames {
    param(
        [AllowNull()]$Items
    )
    $names = @()
    foreach ($item in @($Items)) {
        if ($null -ne $item -and $item.PSObject.Properties.Name -contains 'name') {
            $name = [string]$item.name
            if (-not [string]::IsNullOrWhiteSpace($name)) {
                $names += $name
            }
        }
    }
    return @($names)
}

function Invoke-AnalyticsQuery {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)]$Body,
        [Parameter(Mandatory=$true)][string]$OutputPath
    )

    try {
        $payload = $Body | ConvertTo-Json -Depth 20 -Compress
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri 'https://openrouter.ai/api/v1/analytics/query' `
            -Headers $headers `
            -ContentType 'application/json' `
            -Body $payload `
            -TimeoutSec 60
        Write-JsonFile -Path $OutputPath -Value $response
        return [pscustomobject]@{
            name = $Name
            result = 'success'
            output_file = [IO.Path]::GetFileName($OutputPath)
            error = $null
        }
    }
    catch {
        $errorRecord = [ordered]@{
            name = $Name
            result = 'failure'
            error_type = $_.Exception.GetType().FullName
            error_message = $_.Exception.Message
        }
        Write-JsonFile -Path $OutputPath -Value $errorRecord
        return [pscustomobject]@{
            name = $Name
            result = 'failure'
            output_file = [IO.Path]::GetFileName($OutputPath)
            error = $_.Exception.Message
        }
    }
}

$meta = Invoke-RestMethod `
    -Method Get `
    -Uri 'https://openrouter.ai/api/v1/analytics/meta' `
    -Headers $headers `
    -TimeoutSec 60
Write-JsonFile -Path (Join-Path $downloadsDir 'openrouter_analytics_meta.json') -Value $meta

if ($null -eq $meta -or -not ($meta.PSObject.Properties.Name -contains 'data')) {
    throw 'OpenRouter analytics meta response did not include data.'
}

$metricNames = Get-AvailableNames -Items $meta.data.metrics
$dimensionNames = Get-AvailableNames -Items $meta.data.dimensions

$preferredMetrics = @(
    'total_usage',
    'request_count',
    'tokens_total',
    'tokens_prompt',
    'tokens_completion',
    'reasoning_tokens',
    'cached_tokens',
    'cache_hit_rate',
    'latency',
    'latency_p50',
    'latency_p95',
    'latency_p99',
    'generation_time',
    'time_to_first_token',
    'ttft',
    'throughput',
    'throughput_p50',
    'throughput_p95'
)
$selectedMetrics = @($preferredMetrics | Where-Object { $metricNames -contains $_ })
if ($selectedMetrics.Count -eq 0) {
    throw 'No preferred OpenRouter analytics metrics were exposed by the current meta endpoint.'
}

function Resolve-Dimension {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if ($dimensionNames -contains $candidate) { return $candidate }
    }
    return $null
}

$modelDimension = Resolve-Dimension -Candidates @('model')
$providerDimension = Resolve-Dimension -Candidates @('provider')
$keyDimension = Resolve-Dimension -Candidates @('api_key_id','api_key')
$sessionDimension = Resolve-Dimension -Candidates @('session_id','session')
$generationDimension = Resolve-Dimension -Candidates @('generation_id','generation')
$appDimension = Resolve-Dimension -Candidates @('app')

$windows = @(
    [ordered]@{ run_id = '33405123156'; start = '2026-08-31T14:52:00Z'; end = '2026-08-31T15:15:45Z' },
    [ordered]@{ run_id = '33409318802'; start = '2026-08-31T15:35:30Z'; end = '2026-08-31T16:02:00Z' },
    [ordered]@{ run_id = '33415614759'; start = '2026-08-31T16:42:45Z'; end = '2026-08-31T16:56:40Z' },
    [ordered]@{ run_id = '33417552462'; start = '2026-08-31T17:04:10Z'; end = '2026-08-31T17:15:05Z' }
)

$allResults = @()
foreach ($window in $windows) {
    $base = [ordered]@{
        metrics = $selectedMetrics
        time_range = [ordered]@{
            start = $window.start
            end = $window.end
        }
        limit = 2000
    }

    $queries = @()
    $queries += [pscustomobject]@{ suffix = 'summary'; dimensions = @() }
    if ($null -ne $modelDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_model'; dimensions = @($modelDimension) }
    }
    if ($null -ne $modelDimension -and $null -ne $providerDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_model_provider'; dimensions = @($modelDimension, $providerDimension) }
    }
    if ($null -ne $keyDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_key'; dimensions = @($keyDimension) }
    }
    if ($null -ne $sessionDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_session'; dimensions = @($sessionDimension) }
    }
    if ($null -ne $generationDimension -and $null -ne $modelDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_generation_model'; dimensions = @($generationDimension, $modelDimension) }
    }
    elseif ($null -ne $generationDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_generation'; dimensions = @($generationDimension) }
    }
    if ($null -ne $appDimension) {
        $queries += [pscustomobject]@{ suffix = 'by_app'; dimensions = @($appDimension) }
    }

    foreach ($query in $queries) {
        $body = [ordered]@{}
        foreach ($entry in $base.GetEnumerator()) {
            $body[$entry.Key] = $entry.Value
        }
        if (@($query.dimensions).Count -gt 0) {
            $body['dimensions'] = @($query.dimensions)
        }
        if ($query.suffix -ne 'summary' -and $selectedMetrics -contains 'total_usage') {
            $body['order_by'] = [ordered]@{ field = 'total_usage'; direction = 'desc' }
        }
        elseif ($query.suffix -ne 'summary' -and $selectedMetrics -contains 'request_count') {
            $body['order_by'] = [ordered]@{ field = 'request_count'; direction = 'desc' }
        }

        $name = "run_$($window.run_id)_$($query.suffix)"
        $outputPath = Join-Path $downloadsDir ($name + '.json')
        $allResults += Invoke-AnalyticsQuery -Name $name -Body $body -OutputPath $outputPath
    }
}

$manifest = [ordered]@{
    schema = 'dcoir.openrouter_analytics_issue464.v1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    purpose = 'Read-only historical OpenRouter analytics evidence for GitHub issue 464.'
    inference_endpoints_called = $false
    meta_endpoint = '/api/v1/analytics/meta'
    query_endpoint = '/api/v1/analytics/query'
    metrics_available = $metricNames
    metrics_selected = $selectedMetrics
    dimensions_available = $dimensionNames
    dimensions_selected = [ordered]@{
        model = $modelDimension
        provider = $providerDimension
        api_key = $keyDimension
        session = $sessionDimension
        generation = $generationDimension
        app = $appDimension
    }
    windows = $windows
    queries = $allResults
}
Write-JsonFile -Path (Join-Path $downloadsDir 'openrouter_analytics_manifest.json') -Value $manifest

$successCount = @($allResults | Where-Object { $_.result -eq 'success' }).Count
$failureCount = @($allResults | Where-Object { $_.result -ne 'success' }).Count
Write-Output ("OpenRouter analytics collector completed: {0} successful query files, {1} failed query files, no inference endpoints called." -f $successCount, $failureCount)
