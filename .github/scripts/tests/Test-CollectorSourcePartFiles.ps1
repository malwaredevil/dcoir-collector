<#
.SYNOPSIS
Test the shipped collector source-part discovery helper against real and hostile inputs.
.DESCRIPTION
A standalone Windows PowerShell 5.1 / pwsh executable regression suite.
The temporary test wrapper contains an unconditional throw to prove AST inspection
never runs the collector. Failure must be nonzero for GitHub Actions.
#>
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$helperPath = Join-Path $repoRoot '.github/scripts/Get-CollectorSourcePartFiles.ps1'
if (-not (Test-Path -LiteralPath $helperPath -PathType Leaf)) {
    throw "Shared collector discovery helper is missing: $helperPath"
}
. $helperPath
if (-not (Get-Command Get-CollectorSourcePartFiles -CommandType Function -ErrorAction SilentlyContinue)) {
    throw 'Get-CollectorSourcePartFiles function was not exported.'
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Assert-Throws {
    param([scriptblock]$Action, [string]$Label)
    $didThrow = $false
    try { & $Action | Out-Null } catch { $didThrow = $true }
    if (-not $didThrow) { throw "Expected fail-closed rejection: $Label" }
}

$runtime = @(Get-CollectorSourcePartFiles -RepositoryRoot $repoRoot)
$scan = @(Get-CollectorSourcePartFiles -RepositoryRoot $repoRoot -ForValidation)
Assert-True ($runtime.Count -eq 43) "Expected exactly 43 runtime parts, received $($runtime.Count)"
Assert-True ($scan.Count -eq 44) "Expected exactly 44 validation parts, received $($scan.Count)"
$markerName = 'DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1'
Assert-True (@($scan | Where-Object { [IO.Path]::GetFileName($_) -ceq $markerName }).Count -eq 1) 'Validation-only compatibility marker must be scanned once.'
Assert-True (@($runtime | Where-Object { [IO.Path]::GetFileName($_) -ceq $markerName }).Count -eq 0) 'Compatibility marker must not be runtime-loaded.'
foreach ($file in $runtime) {
    Assert-True (Test-Path -LiteralPath $file -PathType Leaf) "Missing real runtime file: $file"
}
Assert-True (@($runtime | Select-Object -Unique).Count -eq $runtime.Count) 'Runtime path list contains duplicates.'
Assert-True (@($scan | Select-Object -Unique).Count -eq $scan.Count) 'Validation part list contains duplicates.'

$tempBase = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$fixtureRoots = [Collections.Generic.List[string]]::new()
function Invoke-TestFixtureCreate {
    $root = Join-Path $tempBase ('dcoir-discovery-' + [guid]::NewGuid().ToString('N'))
    $parts = Join-Path $root 'project_sources/collector/source/parts'
    [void](New-Item -ItemType Directory -Path $parts -Force)
    $wrapper = Join-Path $root 'project_sources/collector/source/DCOIR_Collector.ps1'
    foreach ($name in @('PartA.ps1','PartB.ps1',$markerName)) {
        Set-Content -LiteralPath (Join-Path $parts $name) -Value '# test fixture' -Encoding UTF8
    }
    $fixtureRoots.Add($root)
    return [pscustomobject]@{ Root = $root; Parts = $parts; Wrapper = $wrapper }
}
function Invoke-TestWrapperWrite {
    param([object]$Fixture, [string]$Assignment)
    $body = $Assignment + [Environment]::NewLine + "throw 'COLLECTOR_RUNTIME_MUST_NOT_EXECUTE'"
    Set-Content -LiteralPath $Fixture.Wrapper -Value $body -Encoding UTF8
}
$validAssignment = @'
$collectorPartFiles = @(
    'PartA.ps1',
    'PartB.ps1'
)
'@
try {
    $good = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $good $validAssignment
    $goodRuntime = @(Get-CollectorSourcePartFiles -RepositoryRoot $good.Root)
    $goodScan = @(Get-CollectorSourcePartFiles -RepositoryRoot $good.Root -ForValidation)
    Assert-True ($goodRuntime.Count -eq 2) 'Synthetic runtime must select exactly the two literal parts.'
    Assert-True ($goodScan.Count -eq 3) 'Synthetic scan must also select compatibility marker.'
    Assert-True ([IO.Path]::GetFileName($goodRuntime[0]) -ceq 'PartA.ps1') 'Runtime AST file order changed.'
    Assert-True ([IO.Path]::GetFileName($goodRuntime[1]) -ceq 'PartB.ps1') 'Runtime AST file order changed.'

    $missing = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $missing $validAssignment
    Remove-Item -LiteralPath (Join-Path $missing.Parts 'PartB.ps1') -Force
    Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $missing.Root } 'missing runtime part'

    $missingMarker = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $missingMarker $validAssignment
    Remove-Item -LiteralPath (Join-Path $missingMarker.Parts $markerName) -Force
    Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $missingMarker.Root -ForValidation } 'missing compatibility marker'

    $extra = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $extra $validAssignment
    Set-Content -LiteralPath (Join-Path $extra.Parts 'Unexpected.ps1') -Value '# unlisted' -Encoding UTF8
    Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $extra.Root } 'unlisted direct child'

    $nested = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $nested $validAssignment
    $nestedDir = Join-Path $nested.Parts 'nested'
    [void](New-Item -ItemType Directory -Path $nestedDir -Force)
    Set-Content -LiteralPath (Join-Path $nestedDir 'Unexpected.ps1') -Value '# hidden extra' -Encoding UTF8
    Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $nested.Root } 'unlisted nested part'

    $cases = @(
        @{ Label='case-insensitive duplicate'; Assign='$collectorPartFiles = @(''PartA.ps1'', ''parta.PS1'')' },
        @{ Label='traversal'; Assign='$collectorPartFiles = @(''../outside.ps1'')' },
        @{ Label='drive-qualified name'; Assign='$collectorPartFiles = @(''C:\temp\outside.ps1'')' },
        @{ Label='absolute path'; Assign='$collectorPartFiles = @(''/etc/passwd.ps1'')' },
        @{ Label='wrong extension'; Assign='$collectorPartFiles = @(''PartA.txt'')' },
        @{ Label='nonliteral command'; Assign='$collectorPartFiles = @(''PartA.ps1'', (Get-Date))' },
        @{ Label='nonliteral interpolation'; Assign='$collectorPartFiles = @("PartA$env:USERNAME.ps1")' },
        @{ Label='missing assignment'; Assign='$notTheCollectorList = @(''PartA.ps1'', ''PartB.ps1'')' },
        @{ Label='scoped assignment'; Assign='$env:collectorPartFiles = @(''PartA.ps1'', ''PartB.ps1'')' },
        @{ Label='compound assignment'; Assign='$collectorPartFiles += @(''PartA.ps1'')' },
        @{ Label='top-level indexed assignment'; Assign='$collectorPartFiles[0] = ''PartB.ps1''' },
        @{ Label='top-level member assignment'; Assign='$object.collectorPartFiles = @(''PartA.ps1'', ''PartB.ps1'')' },
        @{ Label='duplicate assignment'; Assign='$collectorPartFiles = @(''PartA.ps1'')' + [Environment]::NewLine + '$collectorPartFiles = @(''PartB.ps1'')' },
        @{ Label='nested reassignment'; Assign=$validAssignment + [Environment]::NewLine + 'if ($false) { $collectorPartFiles = @(''PartB.ps1'') }' },
        @{ Label='nested indexed reassignment'; Assign=$validAssignment + [Environment]::NewLine + 'if ($false) { $collectorPartFiles[0] = ''PartB.ps1'' }' },
        @{ Label='invalid wrapper syntax'; Assign='$collectorPartFiles = @(' }
    )
    foreach ($case in $cases) {
        $fixture = Invoke-TestFixtureCreate
        Invoke-TestWrapperWrite $fixture $case.Assign
        $fixtureRoot = $fixture.Root
        Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $fixtureRoot } $case.Label
    }

    $outside = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $outside $validAssignment
    $outsidePath = Join-Path $tempBase ('external-collector-' + [guid]::NewGuid().ToString('N') + '.ps1')
    try {
        Set-Content -LiteralPath $outsidePath -Value $validAssignment -Encoding UTF8
        Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $outside.Root -WrapperPath $outsidePath } 'wrapper outside repo root'
    } finally {
        Remove-Item -LiteralPath $outsidePath -Force -ErrorAction SilentlyContinue
    }

    foreach ($ancestor in @('project_sources', 'project_sources/collector', 'project_sources/collector/source')) {
        $ancestorLink = Invoke-TestFixtureCreate
        $ancestorTarget = Invoke-TestFixtureCreate
        Invoke-TestWrapperWrite $ancestorTarget $validAssignment
        $linkPath = Join-Path $ancestorLink.Root $ancestor
        $targetPath = Join-Path $ancestorTarget.Root $ancestor
        Remove-Item -LiteralPath $linkPath -Force -Recurse
        $linkCreated = $false
        try {
            [void](New-Item -ItemType SymbolicLink -Path $linkPath -Target $targetPath -ErrorAction Stop)
            $linkCreated = $true
        } catch {
            Write-Output "ANCESTOR_SYMLINK_CASE_SKIPPED=$ancestor"
        }
        if ($linkCreated) {
            try {
                Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $ancestorLink.Root } "reparse ancestor $ancestor"
            } finally {
                [IO.Directory]::Delete($linkPath)
            }
        }
    }

    $link = Invoke-TestFixtureCreate
    Invoke-TestWrapperWrite $link $validAssignment
    Remove-Item -LiteralPath (Join-Path $link.Parts 'PartB.ps1') -Force
    $outsideTarget = Join-Path $tempBase ('external-target-' + [guid]::NewGuid().ToString('N') + '.ps1')
    try {
        Set-Content -LiteralPath $outsideTarget -Value '# outside file' -Encoding UTF8
        try {
            [void](New-Item -ItemType SymbolicLink -Path (Join-Path $link.Parts 'PartB.ps1') -Target $outsideTarget -ErrorAction Stop)
            Assert-Throws { Get-CollectorSourcePartFiles -RepositoryRoot $link.Root } 'reparse link escaping repo'
        } catch [System.UnauthorizedAccessException] {
            Write-Output 'SYMLINK_CASE_SKIPPED=permission_not_granted'
        }
    } finally {
        Remove-Item -LiteralPath $outsideTarget -Force -ErrorAction SilentlyContinue
    }
    Write-Output 'COLLECTOR_PART_DISCOVERY_TESTS=PASS'
} finally {
    foreach ($root in $fixtureRoots) {
        Remove-Item -LiteralPath $root -Force -Recurse -ErrorAction SilentlyContinue
    }
}
