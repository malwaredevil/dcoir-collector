$ErrorActionPreference = 'Stop'
$requestId = 'exec-20260603-issue197-label-cleanup-001'
$repo = 'DCOIR-Collector/dcoir-collector'
$repoApi = '/repos/DCOIR-Collector/dcoir-collector'
$finalLabels = @(
  'area:collector',
  'area:docs',
  'area:gemini-agent',
  'area:github-repo',
  'area:knowledge-docs',
  'area:operator-tooling',
  'area:project-tracking',
  'area:repo-governance',
  'area:supabase-ircore',
  'area:validation',
  'area:workflows',
  'type:accidental',
  'type:bug',
  'type:cleanup',
  'type:decision',
  'type:enhancement',
  'type:idea',
  'type:maintenance',
  'type:meta',
  'type:planning',
  'type:refactor',
  'type:research'
)
$renamePlan = [ordered]@{
  'area:airtable-ircore' = 'area:supabase-ircore'
  'area:gemini' = 'area:gemini-agent'
}
$labelColors = @{
  area = '0e8a16'
  type = '1d76db'
}
$token = $env:DCOIR_GITHUB_FG_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) { $token = $env:DCOIR_GITHUB_CL_TOKEN }
if ([string]::IsNullOrWhiteSpace($token)) { throw 'Missing DCOIR_GITHUB_FG_TOKEN and DCOIR_GITHUB_CL_TOKEN.' }
$headers = @{
  Authorization = "Bearer $token"
  Accept = 'application/vnd.github+json'
  'X-GitHub-Api-Version' = '2022-11-28'
}
function ConvertTo-UrlLabelName {
  param([Parameter(Mandatory=$true)][string]$Name)
  return [System.Uri]::EscapeDataString($Name)
}
function Invoke-GitHubJson {
  param(
    [Parameter(Mandatory=$true)][string]$Method,
    [Parameter(Mandatory=$true)][string]$Path,
    [AllowNull()]$Body = $null
  )
  $uri = 'https://api.github.com' + $Path
  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
  }
  $json = $Body | ConvertTo-Json -Depth 10
  return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $json -ContentType 'application/json'
}
function Get-RepoLabels {
  $all = @()
  $page = 1
  while ($true) {
    $batch = Invoke-GitHubJson -Method GET -Path "$repoApi/labels?per_page=100&page=$page"
    if ($null -eq $batch -or $batch.Count -eq 0) { break }
    $all += @($batch)
    if ($batch.Count -lt 100) { break }
    $page += 1
  }
  return @($all)
}
function Test-LabelExists {
  param([object[]]$Labels, [string]$Name)
  return @($Labels | Where-Object { $_.name -eq $Name }).Count -gt 0
}
function Get-LabelDescription {
  param([string]$Name)
  if ($Name.StartsWith('area:')) { return 'DCOIR governed area taxonomy label.' }
  if ($Name.StartsWith('type:')) { return 'DCOIR governed work type taxonomy label.' }
  return 'DCOIR governed taxonomy label.'
}
function Get-LabelColor {
  param([string]$Name)
  if ($Name.StartsWith('area:')) { return $labelColors.area }
  if ($Name.StartsWith('type:')) { return $labelColors.type }
  return 'ededed'
}
$reportDir = Join-Path $env:DCOIR_REPO_ROOT (Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $requestId)
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$before = Get-RepoLabels
$created = New-Object System.Collections.Generic.List[string]
$renamed = New-Object System.Collections.Generic.List[string]
$deleted = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]
$errors = New-Object System.Collections.Generic.List[string]
foreach ($oldName in $renamePlan.Keys) {
  $targetName = [string]$renamePlan[$oldName]
  $current = Get-RepoLabels
  $oldExists = Test-LabelExists -Labels $current -Name $oldName
  $targetExists = Test-LabelExists -Labels $current -Name $targetName
  if (-not $oldExists) {
    $skipped.Add("rename source not present: $oldName")
    continue
  }
  try {
    if ($targetExists) {
      Invoke-GitHubJson -Method DELETE -Path "$repoApi/labels/$(ConvertTo-UrlLabelName $oldName)" | Out-Null
      $deleted.Add($oldName)
    } else {
      Invoke-GitHubJson -Method PATCH -Path "$repoApi/labels/$(ConvertTo-UrlLabelName $oldName)" -Body @{
        new_name = $targetName
        color = (Get-LabelColor $targetName)
        description = (Get-LabelDescription $targetName)
      } | Out-Null
      $renamed.Add("$oldName -> $targetName")
    }
  } catch {
    $errors.Add("rename/delete source failed for $oldName -> $targetName :: $($_.Exception.Message)")
  }
}
$current = Get-RepoLabels
foreach ($name in $finalLabels) {
  if (Test-LabelExists -Labels $current -Name $name) { continue }
  try {
    Invoke-GitHubJson -Method POST -Path "$repoApi/labels" -Body @{
      name = $name
      color = (Get-LabelColor $name)
      description = (Get-LabelDescription $name)
    } | Out-Null
    $created.Add($name)
  } catch {
    $errors.Add("create failed for $name :: $($_.Exception.Message)")
  }
  $current = Get-RepoLabels
}
$current = Get-RepoLabels
$finalSet = @{}
foreach ($name in $finalLabels) { $finalSet[$name] = $true }
foreach ($label in $current) {
  $name = [string]$label.name
  if ($finalSet.ContainsKey($name)) { continue }
  try {
    Invoke-GitHubJson -Method DELETE -Path "$repoApi/labels/$(ConvertTo-UrlLabelName $name)" | Out-Null
    $deleted.Add($name)
  } catch {
    $errors.Add("delete failed for $name :: $($_.Exception.Message)")
  }
}
$after = Get-RepoLabels
$afterNames = @($after | ForEach-Object { [string]$_.name } | Sort-Object)
$missingFinal = @($finalLabels | Where-Object { $afterNames -notcontains $_ } | Sort-Object)
$unexpected = @($afterNames | Where-Object { -not $finalSet.ContainsKey($_) } | Sort-Object)
if ($missingFinal.Count -gt 0) { $errors.Add('missing final labels: ' + ($missingFinal -join ', ')) }
if ($unexpected.Count -gt 0) { $errors.Add('unexpected remaining labels: ' + ($unexpected -join ', ')) }
$result = if ($errors.Count -eq 0) { 'success' } else { 'failure' }
$summary = [ordered]@{
  schema = 'dcoir.issue197.label_cleanup_mutation.v1'
  repo = $repo
  request_id = $requestId
  collected_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  result = $result
  mode = 'mutation-label-api'
  before_label_count = @($before).Count
  after_label_count = @($after).Count
  final_label_count = $finalLabels.Count
  created_labels = @($created)
  renamed_labels = @($renamed)
  deleted_labels = @($deleted)
  skipped_actions = @($skipped)
  final_labels = @($afterNames)
  missing_final_labels = @($missingFinal)
  unexpected_remaining_labels = @($unexpected)
  errors = @($errors)
  safety_note = 'GitHub label deletion removes label associations from issues and PRs but does not delete or close issues or PRs.'
}
$summaryPath = Join-Path $reportDir 'label_cleanup_mutation.json'
$summary | ConvertTo-Json -Depth 10 | Out-File -FilePath $summaryPath -Encoding utf8
$md = New-Object System.Collections.Generic.List[string]
$md.Add('# Issue #197 Label Cleanup Mutation')
$md.Add('')
$md.Add("- repo: $repo")
$md.Add("- result: $result")
$md.Add("- mode: mutation-label-api")
$md.Add("- before_label_count: $(@($before).Count)")
$md.Add("- after_label_count: $(@($after).Count)")
$md.Add("- final_label_count: $($finalLabels.Count)")
$md.Add("- created_count: $($created.Count)")
$md.Add("- renamed_count: $($renamed.Count)")
$md.Add("- deleted_count: $($deleted.Count)")
$md.Add("- error_count: $($errors.Count)")
$md.Add('')
$md.Add('## Safety note')
$md.Add('')
$md.Add('GitHub label deletion removes label associations from issues and PRs but does not delete or close issues or PRs.')
$md.Add('')
$md.Add('## Final labels')
$md.Add('')
foreach ($name in $afterNames) { $md.Add("- $name") }
$md.Add('')
$md.Add('## Created labels')
$md.Add('')
if ($created.Count -eq 0) { $md.Add('- none') } else { foreach ($name in $created) { $md.Add("- $name") } }
$md.Add('')
$md.Add('## Renamed labels')
$md.Add('')
if ($renamed.Count -eq 0) { $md.Add('- none') } else { foreach ($name in $renamed) { $md.Add("- $name") } }
$md.Add('')
$md.Add('## Deleted labels')
$md.Add('')
if ($deleted.Count -eq 0) { $md.Add('- none') } else { foreach ($name in ($deleted | Sort-Object)) { $md.Add("- $name") } }
$md.Add('')
$md.Add('## Skipped actions')
$md.Add('')
if ($skipped.Count -eq 0) { $md.Add('- none') } else { foreach ($name in $skipped) { $md.Add("- $name") } }
$md.Add('')
$md.Add('## Errors')
$md.Add('')
if ($errors.Count -eq 0) { $md.Add('- none') } else { foreach ($name in $errors) { $md.Add("- $name") } }
$md -join "`n" | Out-File -FilePath (Join-Path $reportDir 'label_cleanup_mutation.md') -Encoding utf8
$summary | ConvertTo-Json -Depth 10 | Write-Output
if ($errors.Count -gt 0) { exit 1 }
exit 0
