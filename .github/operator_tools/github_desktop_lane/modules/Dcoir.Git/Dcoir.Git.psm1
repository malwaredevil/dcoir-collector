Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirGitVersion = '2026-05-01.2'

function Add-DcoirGitUtf8Line {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path, [AllowEmptyString()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($Path, ([string]$Text) + [Environment]::NewLine, $enc)
}

function Test-DcoirGitPlaceholderPath {
    [CmdletBinding()]
    param([AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $v = $Value.Trim()
    return ($v -match '^[A-Za-z]:\\path\\to(\\|$)' -or $v -match '^/path/to(/|$)' -or $v -match 'your[_ -]?folder[_ -]?name[_ -]?here' -or $v -match 'your[_ -]?repo')
}

function Get-DcoirGitSystemEnvValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [switch]$Required,
        [AllowNull()][string]$Default
    )
    $machine = [Environment]::GetEnvironmentVariable($Name, 'Machine')
    if (Test-DcoirGitPlaceholderPath -Value $machine) {
        throw "$Name is set to a placeholder path in Machine/System environment scope: $machine"
    }
    if (-not [string]::IsNullOrWhiteSpace($machine)) { return $machine.Trim() }
    if (-not [string]::IsNullOrWhiteSpace($Default)) { return $Default }
    if ($Required) { throw "$Name is not set in Machine/System environment scope. Set it as a System environment variable, then open a new terminal." }
    return $null
}

function ConvertTo-DcoirNativeArgumentString {
    [CmdletBinding()]
    param([AllowEmptyString()][string]$Argument)
    if ($null -eq $Argument) { return '""' }
    if ($Argument.Length -eq 0) { return '""' }
    if ($Argument -notmatch '[\s"]') { return $Argument }
    $escaped = $Argument -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Resolve-DcoirGitExe {
    [CmdletBinding()]
    param()
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $git) { $git = Get-Command git -ErrorAction SilentlyContinue }
    if (-not $git) { throw 'git executable was not found in PATH.' }
    return $git.Source
}

function Invoke-DcoirGitCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepoRoot,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [AllowNull()][string]$LogPath,
        [switch]$AllowFailure,
        [switch]$Quiet
    )
    if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) { throw "Repo root not found: $RepoRoot" }
    $repoFull = (Resolve-Path -LiteralPath $RepoRoot).Path
    $gitExe = Resolve-DcoirGitExe
    if (-not $Quiet) {
        $cmd = '>>> git ' + ($Arguments -join ' ')
        Write-Host $cmd
        if (-not [string]::IsNullOrWhiteSpace($LogPath)) { Add-DcoirGitUtf8Line -Path $LogPath -Text $cmd }
    }
    $argumentString = ($Arguments | ForEach-Object { ConvertTo-DcoirNativeArgumentString ([string]$_) }) -join ' '
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $gitExe
    $psi.Arguments = $argumentString
    $psi.WorkingDirectory = $repoFull
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($text in @($stdout, $stderr)) {
        if ($null -ne $text -and $text.Length -gt 0) {
            $normalized = $text -replace "`r`n", "`n"
            foreach ($line in ($normalized -split "`n")) {
                if ($line.Length -gt 0) {
                    $lines.Add([string]$line) | Out-Null
                    if (-not $Quiet) { Write-Host ([string]$line) }
                    if (-not [string]::IsNullOrWhiteSpace($LogPath)) { Add-DcoirGitUtf8Line -Path $LogPath -Text ([string]$line) }
                }
            }
        }
    }
    $result = [pscustomobject]@{
        ExitCode = [int]$process.ExitCode
        Lines = @($lines.ToArray())
        StdOut = $stdout
        StdErr = $stderr
        Arguments = @($Arguments)
        RepoRoot = $repoFull
    }
    if ($process.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "git $($Arguments -join ' ') failed with exit code $($process.ExitCode)"
    }
    return $result
}

function Invoke-DcoirGitLogged {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepoRoot,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [AllowNull()][string]$LogPath
    )
    $result = Invoke-DcoirGitCommand -RepoRoot $RepoRoot -Arguments $Arguments -LogPath $LogPath
    return @($result.Lines)
}

function Get-DcoirGitCurrentBranch {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [AllowNull()][string]$LogPath)
    $lines = @(Invoke-DcoirGitLogged -RepoRoot $RepoRoot -Arguments @('branch','--show-current') -LogPath $LogPath)
    return (($lines | Select-Object -Last 1) -as [string]).Trim()
}

function Assert-DcoirGitBranch {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [string]$ExpectedBranch = 'main', [AllowNull()][string]$LogPath)
    $current = Get-DcoirGitCurrentBranch -RepoRoot $RepoRoot -LogPath $LogPath
    if ($current -ne $ExpectedBranch) { throw "Expected branch '$ExpectedBranch' but found '$current'." }
    return $current
}

function Get-DcoirGitStatusPorcelain {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [AllowNull()][string]$LogPath)
    $result = Invoke-DcoirGitCommand -RepoRoot $RepoRoot -Arguments @('status','--porcelain') -LogPath $LogPath -Quiet
    return @($result.Lines)
}

function Assert-DcoirGitCleanTree {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [AllowNull()][string]$LogPath, [string]$Message = 'Working tree is not clean.')
    $dirty = @(Get-DcoirGitStatusPorcelain -RepoRoot $RepoRoot -LogPath $LogPath)
    if ($dirty.Count -gt 0) {
        foreach ($line in $dirty) {
            Write-Host "DIRTY: $line"
            if (-not [string]::IsNullOrWhiteSpace($LogPath)) { Add-DcoirGitUtf8Line -Path $LogPath -Text "DIRTY: $line" }
        }
        throw $Message
    }
}

function Invoke-DcoirGitFetch {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [string]$Remote = 'origin', [AllowNull()][string]$LogPath)
    Invoke-DcoirGitLogged -RepoRoot $RepoRoot -Arguments @('fetch', $Remote, '--prune') -LogPath $LogPath | Out-Null
}

function Invoke-DcoirGitFastForwardPull {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [string]$Remote = 'origin', [string]$Branch = 'main', [AllowNull()][string]$LogPath)
    Invoke-DcoirGitLogged -RepoRoot $RepoRoot -Arguments @('pull','--ff-only',$Remote,$Branch) -LogPath $LogPath | Out-Null
}

function Get-DcoirGitAheadBehind {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$RepoRoot, [string]$Left, [string]$Right, [AllowNull()][string]$LogPath)
    $spec = "$Left...$Right"
    $lines = @(Invoke-DcoirGitLogged -RepoRoot $RepoRoot -Arguments @('rev-list','--left-right','--count',$spec) -LogPath $LogPath)
    $last = (($lines | Select-Object -Last 1) -as [string]).Trim()
    $parts = $last -split '\s+'
    return [pscustomobject]@{ Left = [int]$parts[0]; Right = [int]$parts[1]; Raw = $last }
}

Export-ModuleMember -Function Add-DcoirGitUtf8Line,Test-DcoirGitPlaceholderPath,Get-DcoirGitSystemEnvValue,ConvertTo-DcoirNativeArgumentString,Resolve-DcoirGitExe,Invoke-DcoirGitCommand,Invoke-DcoirGitLogged,Get-DcoirGitCurrentBranch,Assert-DcoirGitBranch,Get-DcoirGitStatusPorcelain,Assert-DcoirGitCleanTree,Invoke-DcoirGitFetch,Invoke-DcoirGitFastForwardPull,Get-DcoirGitAheadBehind
