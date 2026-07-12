function New-DcoirActionsExecSafeName {
    param([Parameter(Mandatory=$true)][string]$Value)
    if ($Value -notmatch '^[A-Za-z0-9._-]+$') {
        throw "Unsafe identifier: $Value"
    }
    return $Value
}

function Get-DcoirActionsExecSha256Text {
    param([Parameter(Mandatory=$true)][string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        $hash = $sha.ComputeHash($bytes)
        return ([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Add-DcoirActionsExecMask {
    param([AllowNull()][string]$Value)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        Write-Host "::add-mask::$Value"
    }
}

function ConvertTo-DcoirActionsExecSanitizedText {
    param(
        [AllowNull()][string]$Text,
        [hashtable]$SecretValuesByName
    )
    if ($null -eq $Text) { return '' }
    $out = [string]$Text
    if ($SecretValuesByName) {
        foreach ($key in $SecretValuesByName.Keys) {
            $value = [string]$SecretValuesByName[$key]
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $out = $out.Replace($value, "[REDACTED:$key]")
            }
        }
    }
    return $out
}

function Get-DcoirActionsExecSecretMap {
    param([string[]]$SecretEnvNames)
    $secretValues = @{}
    foreach ($name in $SecretEnvNames) {
        if ([string]::IsNullOrWhiteSpace($name)) { continue }
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Add-DcoirActionsExecMask -Value $value
            $secretValues[$name] = $value
        }
    }
    return $secretValues
}
function Set-DcoirActionsExecEnvironmentBridge {
    param(
        [Parameter(Mandatory=$true)][hashtable]$GeneratedValues,
        [string[]]$SecretEnvNames = @()
    )
    $secretValues = Get-DcoirActionsExecSecretMap -SecretEnvNames $SecretEnvNames

    foreach ($name in $SecretEnvNames) {
        if ([string]::IsNullOrWhiteSpace($name)) { continue }
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            [Environment]::SetEnvironmentVariable($name, $value, 'Machine')
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }

    foreach ($name in $GeneratedValues.Keys) {
        $value = [string]$GeneratedValues[$name]
        if ([string]::IsNullOrWhiteSpace($value)) { continue }
        [Environment]::SetEnvironmentVariable($name, $value, 'Machine')
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }

    return $secretValues
}
