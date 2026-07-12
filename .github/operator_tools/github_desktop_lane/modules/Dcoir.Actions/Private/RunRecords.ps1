function New-DcoirRunRecord {
    param([string]$Label, [string]$WorkflowFile, [string]$RefName, $Inputs, $Capture)
    return [ordered]@{
        label = $Label; workflow = $WorkflowFile; ref = $RefName; inputs = $Inputs; capture = $Capture
        state = 'planned'; run_id = $null; url = $null; status = $null; conclusion = $null
        created_at = $null; updated_at = $null; error = $null; dispatch_started_at = $null; skipped_reason = $null
    }
}

function Test-DcoirRunRecordSuccess {
    param($Record)
    return ($Record.state -eq 'terminal' -and $Record.status -eq 'completed' -and $Record.conclusion -eq 'success' -and [string]::IsNullOrWhiteSpace([string]$Record.error))
}

function Test-DcoirRunRecordNonSuccess {
    param($Record)
    if (-not $Record) { return $false }
    if (-not [string]::IsNullOrWhiteSpace([string]$Record.error)) { return $true }
    if ($Record.state -eq 'skipped') { return $true }
    if ($Record.state -eq 'timed_out') { return $true }
    if ($Record.state -eq 'terminal' -and $Record.status -eq 'completed' -and $Record.conclusion -ne 'success') { return $true }
    return $false
}
