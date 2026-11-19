<#
.SYNOPSIS
Return the authoritative collector part list without executing collector code.
.DESCRIPTION
The runtime part list comes from the literal collectorPartFiles array assignment
inside the collector wrapper's PowerShell AST. The optional validation set adds
exactly one non-runtime compatibility marker to preserve historical scanners.
Reject unsafe, missing or unlisted parts before returning any paths.
#>

function Get-CollectorSourcePartFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot,
        [string]$WrapperPath,
        [switch]$ForValidation
    )

    $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([char]'\', [char]'/')
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw "Collector repository root is missing: $root"
    }
    $sourceRoot = Join-Path $root 'project_sources/collector/source'
    $partsRoot = Join-Path $sourceRoot 'parts'
    if (-not (Test-Path -LiteralPath $partsRoot -PathType Container)) {
        throw "Collector source parts directory is missing: $partsRoot"
    }
    $partDirectoryItem = Get-Item -LiteralPath $partsRoot -Force
    if (($partDirectoryItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Collector source parts directory must not be a reparse point: $partsRoot"
    }

    $canonicalWrapper = Join-Path $sourceRoot 'DCOIR_Collector.ps1'
    $wrapper = if ([string]::IsNullOrWhiteSpace($WrapperPath)) { $canonicalWrapper } else { $WrapperPath }
    $wrapperFull = [IO.Path]::GetFullPath($wrapper)
    $rootPrefix = $root + [IO.Path]::DirectorySeparatorChar
    if (-not $wrapperFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Collector wrapper path is outside repository root: $wrapper"
    }
    if (-not (Test-Path -LiteralPath $wrapperFull -PathType Leaf)) {
        throw "Collector wrapper is missing: $wrapperFull"
    }
    $wrapperItem = Get-Item -LiteralPath $wrapperFull -Force
    if (($wrapperItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Collector wrapper must not be a reparse point: $wrapperFull"
    }

    $tokens = $null
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $wrapperFull, [ref]$tokens, [ref]$parseErrors
    )
    if (@($parseErrors).Count -gt 0) {
        throw "Collector wrapper contains PowerShell parser errors: $wrapperFull"
    }
    if ($null -eq $ast.EndBlock) {
        throw "Collector wrapper has no executable statement block: $wrapperFull"
    }
    $assignments = @($ast.EndBlock.Statements | Where-Object {
        $_ -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $_.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $_.Left.VariablePath.UserPath -ieq 'collectorPartFiles'
    })
    if ($assignments.Count -ne 1) {
        throw "Expected exactly one top-level collectorPartFiles assignment; found $($assignments.Count)."
    }

    $right = $assignments[0].Right
    if ($right -isnot [System.Management.Automation.Language.PipelineAst] -or
        @($right.PipelineElements).Count -ne 1 -or
        $right.PipelineElements[0] -isnot [System.Management.Automation.Language.CommandExpressionAst]) {
        throw 'collectorPartFiles must be a literal PowerShell array expression.'
    }
    $expression = $right.PipelineElements[0].Expression
    if ($expression -isnot [System.Management.Automation.Language.ArrayExpressionAst]) {
        throw 'collectorPartFiles must use a literal @() array.'
    }

    $names = [Collections.Generic.List[string]]::new()
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($statement in @($expression.SubExpression.Statements)) {
        if ($statement -isnot [System.Management.Automation.Language.PipelineAst] -or
            @($statement.PipelineElements).Count -ne 1 -or
            $statement.PipelineElements[0] -isnot [System.Management.Automation.Language.CommandExpressionAst]) {
            throw 'collectorPartFiles contains a nonliteral statement.'
        }
        $entryAst = $statement.PipelineElements[0].Expression
        $values = if ($entryAst -is [System.Management.Automation.Language.ArrayLiteralAst]) {
            @($entryAst.Elements)
        } else {
            @($entryAst)
        }
        foreach ($valueAst in $values) {
            if ($valueAst -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) {
                throw 'collectorPartFiles must contain only static string literals.'
            }
            $name = [string]$valueAst.Value
            if ([string]::IsNullOrWhiteSpace($name) -or
                $name.Trim() -cne $name -or
                $name -match '[\\/:*?"<>|]' -or
                $name -match '[\x00-\x1F\x7F]' -or
                $name.Contains('..') -or
                $name -notmatch '^[^\\/]+\.ps1$') {
                throw "Invalid collector part filename in load list: $name"
            }
            if (-not $seen.Add($name)) {
                throw "Duplicate collector part filename in load list: $name"
            }
            $names.Add($name)
        }
    }
    if ($names.Count -eq 0) {
        throw 'collectorPartFiles array must not be empty.'
    }

    $markerName = 'DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1'
    if ($seen.Contains($markerName)) {
        throw 'Validation-only compatibility marker must not be in the runtime load list.'
    }

    $partsPrefix = [IO.Path]::GetFullPath($partsRoot).TrimEnd([char]'\', [char]'/') + [IO.Path]::DirectorySeparatorChar
    $runtimePaths = [Collections.Generic.List[string]]::new()
    foreach ($name in $names) {
        $full = [IO.Path]::GetFullPath((Join-Path $partsRoot $name))
        if (-not $full.StartsWith($partsPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Collector part escapes the source parts directory: $name"
        }
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
            throw "Required collector source part is missing: $name"
        }
        $item = Get-Item -LiteralPath $full -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Collector source part may not be a symlink: $name"
        }
        $runtimePaths.Add($full)
    }

    $markerFull = Join-Path $partsRoot $markerName
    if (-not (Test-Path -LiteralPath $markerFull -PathType Leaf)) {
        throw "Validation-only collector compatibility marker is missing: $markerName"
    }
    $markerItem = Get-Item -LiteralPath $markerFull -Force
    if (($markerItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Validation-only collector compatibility marker must not be a symlink.'
    }

    $expected = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $names) { [void]$expected.Add($name) }
    [void]$expected.Add($markerName)
    $actual = @(Get-ChildItem -LiteralPath $partsRoot -Recurse -File -Filter '*.ps1' -Force)
    foreach ($part in $actual) {
        if ([IO.Path]::GetFullPath($part.DirectoryName).TrimEnd([char]'\', [char]'/') -ine
            [IO.Path]::GetFullPath($partsRoot).TrimEnd([char]'\', [char]'/')) {
            throw "Unexpected nested collector source part: $($part.FullName)"
        }
        if (-not $expected.Contains($part.Name)) {
            throw "Unexpected unlisted collector source part: $($part.Name)"
        }
        if (($part.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Collector source part may not be a symlink: $($part.Name)"
        }
    }
    if ($actual.Count -ne $expected.Count) {
        throw "Collector part set mismatch; expected $($expected.Count), found $($actual.Count)."
    }
    if ($ForValidation) {
        $all = @($runtimePaths.ToArray()) + @([IO.Path]::GetFullPath($markerFull))
        return @($all | Sort-Object { [IO.Path]::GetFileName($_) })
    }
    return @($runtimePaths.ToArray())
}
