$ErrorActionPreference = 'Stop'

$requestId = 'exec-20260520-wbs06-field-rename-apply-batch1-001'
$expectedBaseId = 'appM4KSwnVf3G3OTK'

$renamePlan = @(
  [pscustomobject]@{
    table_name = 'Gemini Research Reference'
    table_id = 'tblfZnARJxcMJ0yHW'
    field_id = 'fldH0t18dHVNkfTrA'
    expected_current_names = @('legacy_research_batch__do_not_use','legacy_research_batch_review')
    new_name = 'legacy_research_batch_review'
    rationale = 'Normalize legacy research batch field to single-underscore WBS06 legacy review convention; replacement field is research_batch_select.'
  },
  [pscustomobject]@{
    table_name = 'GitHub Workflow Inventory'
    table_id = 'tblHTf5bLKGK1Yk11'
    field_id = 'fldNGAE9cbd9YSYzz'
    expected_current_names = @('do_not_use_when','avoid_when')
    new_name = 'avoid_when'
    rationale = 'Clarify current anti-routing guidance without falsely marking the field as legacy.'
  },
  [pscustomobject]@{
    table_name = 'Idea Inbox'
    table_id = 'tblWwBxwrjZF6JR3r'
    field_id = 'fldyhuC1RXb6TQBu3'
    expected_current_names = @('promoted_to_github','github_promotion_completed')
    new_name = 'github_promotion_completed'
    rationale = 'Clarify checkbox semantics as completed GitHub promotion rather than a vague promotion target.'
  }
)

function Get-RequiredEnvValue {
  param([Parameter(Mandatory=$true)][string]$Name)
  $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
  if ([string]::IsNullOrWhiteSpace($value)) { $value = [Environment]::GetEnvironmentVariable($Name, 'Machine') }
  if ([string]::IsNullOrWhiteSpace($value)) { throw "Missing required environment variable: $Name" }
  return $value.Trim()
}

function Write-Utf8NoBomText {
  param([Parameter(Mandatory=$true)][string]$Path, [AllowNull()][string]$Text)
  $parent = Split-Path -Parent $Path
  if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, [string]$Text, $enc)
}

function Write-JsonFile {
  param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)]$Object, [int]$Depth = 40)
  Write-Utf8NoBomText -Path $Path -Text ($Object | ConvertTo-Json -Depth $Depth)
}

function Invoke-AirtableJson {
  param(
    [Parameter(Mandatory=$true)][string]$Uri,
    [Parameter(Mandatory=$true)][hashtable]$Headers,
    [string]$Method = 'GET',
    [AllowNull()]$Body
  )
  $args = @{ Uri = $Uri; Headers = $Headers; Method = $Method; ErrorAction = 'Stop' }
  if ($null -ne $Body) {
    $args['Body'] = ($Body | ConvertTo-Json -Depth 20)
    $args['ContentType'] = 'application/json'
  }
  return Invoke-RestMethod @args
}

function Get-FieldState {
  param([Parameter(Mandatory=$true)]$Schema, [Parameter(Mandatory=$true)][string]$TableId, [Parameter(Mandatory=$true)][string]$FieldId)
  $table = @($Schema.tables) | Where-Object { $_.id -eq $TableId } | Select-Object -First 1
  if ($null -eq $table) { throw "Missing table in schema: $TableId" }
  $field = @($table.fields) | Where-Object { $_.id -eq $FieldId } | Select-Object -First 1
  if ($null -eq $field) { throw "Missing field in schema: $TableId/$FieldId" }
  return [pscustomobject]@{ table = $table; field = $field }
}

$repoRoot = Get-RequiredEnvValue -Name 'DCOIR_REPO_ROOT'
$downloadsDir = Get-RequiredEnvValue -Name 'DCOIR_DOWNLOADS_DIR'
$token = Get-RequiredEnvValue -Name 'DCOIR_AIRTABLE_TOKEN'
$baseId = Get-RequiredEnvValue -Name 'DCOIR_AIRTABLE_BASE_ID'
if ($baseId -ne $expectedBaseId) { throw "Unexpected DCOIR_AIRTABLE_BASE_ID. Expected $expectedBaseId but got $baseId" }

$statusRoot = Join-Path $repoRoot ("chatgpt_staging\status_reports\chatgpt-exec\{0}\wbs06_field_rename_apply_batch1" -f $requestId)
if (Test-Path -LiteralPath $statusRoot) { Remove-Item -LiteralPath $statusRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $statusRoot | Out-Null

$headers = @{ Authorization = "Bearer $token" }
$schemaUri = "https://api.airtable.com/v0/meta/bases/$baseId/tables"
$preSchema = Invoke-AirtableJson -Uri $schemaUri -Headers $headers
Write-JsonFile -Path (Join-Path $statusRoot 'pre_schema_snapshot.json') -Object $preSchema -Depth 80
Write-JsonFile -Path (Join-Path $statusRoot 'requested_rename_plan.json') -Object $renamePlan -Depth 20

$precheck = New-Object System.Collections.Generic.List[object]
$errors = New-Object System.Collections.Generic.List[string]
foreach ($item in $renamePlan) {
  $state = Get-FieldState -Schema $preSchema -TableId $item.table_id -FieldId $item.field_id
  $currentName = [string]$state.field.name
  $tableFieldNames = @($state.table.fields | ForEach-Object { [string]$_.name })
  $duplicateNewName = @($state.table.fields | Where-Object { $_.id -ne $item.field_id -and $_.name -ieq $item.new_name }).Count -gt 0
  $expectedOk = @($item.expected_current_names) -contains $currentName
  if (-not $expectedOk) { $errors.Add("Schema drift for $($item.table_name)/$($item.field_id): expected one of [$($item.expected_current_names -join ', ')] but found [$currentName]") | Out-Null }
  if ($duplicateNewName) { $errors.Add("Duplicate target field name [$($item.new_name)] already exists in table $($item.table_name).") | Out-Null }
  $precheck.Add([pscustomobject]@{
    table_name = $item.table_name
    table_id = $item.table_id
    field_id = $item.field_id
    current_name = $currentName
    new_name = $item.new_name
    expected_current_names = @($item.expected_current_names)
    expected_ok = [bool]$expectedOk
    duplicate_new_name = [bool]$duplicateNewName
    field_type = [string]$state.field.type
    rationale = $item.rationale
  }) | Out-Null
}
Write-JsonFile -Path (Join-Path $statusRoot 'precheck.json') -Object @($precheck.ToArray()) -Depth 20

if ($errors.Count -gt 0) {
  $summary = [ordered]@{
    schema = 'dcoir.wbs06.field_rename_apply.v1'
    request_id = $requestId
    result = 'blocked_precheck'
    airtable_writes_attempted = 0
    airtable_writes_succeeded = 0
    errors = @($errors.ToArray())
  }
  Write-JsonFile -Path (Join-Path $statusRoot 'field_rename_apply_summary.json') -Object $summary -Depth 20
  throw (($errors.ToArray()) -join '; ')
}

$results = New-Object System.Collections.Generic.List[object]
foreach ($item in $renamePlan) {
  $state = Get-FieldState -Schema $preSchema -TableId $item.table_id -FieldId $item.field_id
  $currentName = [string]$state.field.name
  if ($currentName -eq $item.new_name) {
    $results.Add([pscustomobject]@{
      table_name = $item.table_name
      table_id = $item.table_id
      field_id = $item.field_id
      old_name = $currentName
      new_name = $item.new_name
      status = 'no_op_already_current'
      rationale = $item.rationale
    }) | Out-Null
    continue
  }
  $fieldUri = "https://api.airtable.com/v0/meta/bases/$baseId/tables/$($item.table_id)/fields/$($item.field_id)"
  $body = @{ name = $item.new_name }
  Invoke-AirtableJson -Uri $fieldUri -Headers $headers -Method 'PATCH' -Body $body | Out-Null
  $results.Add([pscustomobject]@{
    table_name = $item.table_name
    table_id = $item.table_id
    field_id = $item.field_id
    old_name = $currentName
    new_name = $item.new_name
    status = 'rename_patch_sent'
    rationale = $item.rationale
  }) | Out-Null
}

$postSchema = Invoke-AirtableJson -Uri $schemaUri -Headers $headers
Write-JsonFile -Path (Join-Path $statusRoot 'post_schema_snapshot.json') -Object $postSchema -Depth 80

$verified = New-Object System.Collections.Generic.List[object]
$verifyErrors = New-Object System.Collections.Generic.List[string]
foreach ($item in $renamePlan) {
  $state = Get-FieldState -Schema $postSchema -TableId $item.table_id -FieldId $item.field_id
  $actualName = [string]$state.field.name
  $ok = ($actualName -eq $item.new_name)
  if (-not $ok) { $verifyErrors.Add("Verification failed for $($item.table_name)/$($item.field_id): expected [$($item.new_name)] but found [$actualName]") | Out-Null }
  $verified.Add([pscustomobject]@{
    table_name = $item.table_name
    table_id = $item.table_id
    field_id = $item.field_id
    verified_name = $actualName
    expected_name = $item.new_name
    verified = [bool]$ok
  }) | Out-Null
}

$resultArray = @($results.ToArray())
$changedCount = @($resultArray | Where-Object { $_.status -eq 'rename_patch_sent' }).Count
$noopCount = @($resultArray | Where-Object { $_.status -eq 'no_op_already_current' }).Count
$summaryResult = if ($verifyErrors.Count -eq 0) { 'success' } else { 'verification_failed' }
$summary = [ordered]@{
  schema = 'dcoir.wbs06.field_rename_apply.v1'
  request_id = $requestId
  result = $summaryResult
  base_id = $baseId
  safety = [ordered]@{
    field_renames_requested = @($renamePlan).Count
    field_renames_changed = $changedCount
    field_renames_noop = $noopCount
    record_updates = 0
    field_deletes = 0
    type_conversions = 0
    delete_queue_rows = 0
  }
  results = $resultArray
  verification = @($verified.ToArray())
  errors = @($verifyErrors.ToArray())
  created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
Write-JsonFile -Path (Join-Path $statusRoot 'field_rename_apply_results.json') -Object $resultArray -Depth 20
Write-JsonFile -Path (Join-Path $statusRoot 'field_rename_apply_verification.json') -Object @($verified.ToArray()) -Depth 20
Write-JsonFile -Path (Join-Path $statusRoot 'field_rename_apply_summary.json') -Object $summary -Depth 30

$md = New-Object System.Collections.Generic.List[string]
$md.Add('# WBS06 field rename apply batch 1')
$md.Add('')
$md.Add("- request_id: $requestId")
$md.Add("- result: $summaryResult")
$md.Add("- field renames changed: $changedCount")
$md.Add("- field renames already current/no-op: $noopCount")
$md.Add('- safety: no record updates, no field deletion, no type conversion, no Delete Queue rows')
$md.Add('')
$md.Add('| Table | Field ID | Old/current before | New verified name | Status |')
$md.Add('|---|---|---|---|---|')
foreach ($r in $resultArray) {
  $v = @($verified.ToArray()) | Where-Object { $_.field_id -eq $r.field_id } | Select-Object -First 1
  $md.Add("| $($r.table_name) | $($r.field_id) | $($r.old_name) | $($v.verified_name) | $($r.status) |")
}
if ($verifyErrors.Count -gt 0) {
  $md.Add('')
  $md.Add('## Verification errors')
  foreach ($e in $verifyErrors) { $md.Add("- $e") }
}
$md | Set-Content -LiteralPath (Join-Path $statusRoot 'field_rename_apply_report.md') -Encoding UTF8

if ($verifyErrors.Count -gt 0) { throw (($verifyErrors.ToArray()) -join '; ') }
Write-Output ($summary | ConvertTo-Json -Depth 30)
