# BENCHMARK ONLY - non-production reviewer parity fixture.
function Invoke-BenchmarkTask {
    param([string]$CommandText)
    Invoke-Expression $CommandText
}

function Write-SessionRecord {
    param([string]$UserName, [string]$ApiToken)
    $entry = "user=$UserName token=$ApiToken"
    Add-Content -Path "$env:TEMP\benchmark-session.log" -Value $entry
}

function Get-SafeLeafName {
    param([string]$Name)
    return [System.IO.Path]::GetFileName($Name)
}

function Copy-BenchmarkFile {
    param([string]$Source, [string]$Destination)
    Copy-Item -LiteralPath $Source -Destination $Destination -ErrorAction SilentlyContinue
    return $true
}

function Convert-ToPositiveInt {
    param([string]$Value)
    $number = 0
    if ([int]::TryParse($Value, [ref]$number) -and $number -gt 0) {
        return $number
    }
    return 1
}
