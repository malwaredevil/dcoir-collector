Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirPackagingVersion = '2026-05-01.2'

$moduleRoot = Split-Path -Parent $PSScriptRoot
$commonPath = Join-Path $moduleRoot 'Dcoir.Common\Dcoir.Common.psd1'
if (-not (Test-Path -LiteralPath $commonPath -PathType Leaf)) { $commonPath = Join-Path $moduleRoot 'Dcoir.Common\Dcoir.Common.psm1' }
Import-Module -Name $commonPath -Force -ErrorAction Stop

function Invoke-DcoirChatGPTFriendlyZip {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$SourceFolder,
        [Parameter(Mandatory=$true)][string]$OutputZip,
        [Parameter(Mandatory=$true)][string]$RepoRoot,
        [switch]$NormalizeTextEncoding
    )
    $zipScript = Join-Path $RepoRoot 'operator_tools\github_desktop_lane\scripts\New-DcoirChatGPTFriendlyZip.ps1'
    if (-not (Test-Path -LiteralPath $zipScript -PathType Leaf)) { throw "ChatGPT-friendly ZIP helper not found: $zipScript" }
    $zipParams = @{
        SourceFolder = $SourceFolder
        OutputZip = $OutputZip
    }
    if ($NormalizeTextEncoding) { $zipParams.NormalizeTextEncoding = $true }
    & $zipScript @zipParams | Out-Null
    if (-not (Test-Path -LiteralPath $OutputZip -PathType Leaf)) { throw "ZIP helper completed but ZIP not found: $OutputZip" }
    return $OutputZip
}

Export-ModuleMember -Function Invoke-DcoirChatGPTFriendlyZip
