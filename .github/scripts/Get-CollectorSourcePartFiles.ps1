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
    $directory = $root
    foreach ($segment in @('project_sources', 'collector', 'source', 'parts')) {
        $directory = Join-Path $directory $segment
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            throw "Collector source directory is missing: $directory"
        }
        $directoryItem = Get-Item -LiteralPath $directory -Force
        if (($directoryItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Collector source directory must not be a reparse point: $directory"
        }
    }

    $canonicalWrapper = Join-Path $sourceRoot 'DCOIR_Collector.ps1'
    $wrapper = if ([string]::IsNullOrWhiteSpace($WrapperPath)) { $canonicalWrapper } else { $WrapperPath }
    $wrapperFull = [IO.Path]::GetFullPath($wrapper)
    $rootPrefix = $root + [IO.Path]::DirectorySeparatorChar
    if (-not $wrapperFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Collector wrapper path is outside repository root: $wrapper"
    }
    $wrapperPath = $root
    $wrapperSegments = $wrapperFull.Substring($rootPrefix.Length).Split(
        [char[]]@('\', '/'), [StringSplitOptions]::RemoveEmptyEntries
    )
    for ($index = 0; $index -lt $wrapperSegments.Length; $index++) {
        $wrapperPath = Join-Path $wrapperPath $wrapperSegments[$index]
        $isLeaf = $index -eq ($wrapperSegments.Length - 1)
        $pathExists = if ($isLeaf) {
            Test-Path -LiteralPath $wrapperPath -PathType Leaf
        } else {
            Test-Path -LiteralPath $wrapperPath -PathType Container
        }
        if (-not $pathExists) {
            throw "Collector wrapper path is missing or invalid: $wrapperPath"
        }
        $wrapperItem = Get-Item -LiteralPath $wrapperPath -Force
        if (($wrapperItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Collector wrapper path must not contain a reparse point: $wrapperPath"
        }
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
    $collectorPartFileAssignments = @($ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        @($node.Left.FindAll({
            param($leftNode)
            $leftNode -is [System.Management.Automation.Language.VariableExpressionAst] -and
            $leftNode.VariablePath.UserPath -ieq 'collectorPartFiles'
        }, $true)).Count -gt 0
    }, $true))
    $assignments = @($collectorPartFileAssignments | Where-Object {
        $_.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $_.Left.VariablePath.UserPath -ieq 'collectorPartFiles' -and
        [string]::IsNullOrEmpty($_.Left.VariablePath.Scope)
    })
    if ($collectorPartFileAssignments.Count -ne 1 -or $assignments.Count -ne 1 -or
        $assignments[0].Parent -ne $ast.EndBlock -or
        $assignments[0].Operator -ne [System.Management.Automation.Language.TokenKind]::Equals) {
        throw "Expected exactly one top-level simple assignment to unscoped collectorPartFiles; found $($assignments.Count)."
    }

    $right = $assignments[0].Right
    if ($right -is [System.Management.Automation.Language.CommandExpressionAst]) {
        $expression = $right.Expression
    } elseif ($right -is [System.Management.Automation.Language.PipelineAst] -and
              @($right.PipelineElements).Count -eq 1 -and
              $right.PipelineElements[0] -is [System.Management.Automation.Language.CommandExpressionAst]) {
        $expression = $right.PipelineElements[0].Expression
    } else {
        throw "collectorPartFiles must be a literal PowerShell array expression; received $($right.GetType().Name)."
    }
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
    $actual = [Collections.Generic.List[object]]::new()
    $directories = [Collections.Generic.Queue[string]]::new()
    $directories.Enqueue($partsRoot)
    while ($directories.Count -gt 0) {
        $currentDirectory = $directories.Dequeue()
        foreach ($item in @(Get-ChildItem -LiteralPath $currentDirectory -Force)) {
            $isPowerShellFile = -not $item.PSIsContainer -and
                [IO.Path]::GetExtension($item.Name) -ieq '.ps1'
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -and
                ($item.PSIsContainer -or $isPowerShellFile)) {
                throw "Collector source tree may not contain a reparse point: $($item.FullName)"
            }
            if ($item.PSIsContainer) {
                $directories.Enqueue($item.FullName)
                continue
            }
            if (-not $isPowerShellFile) {
                continue
            }
            if ([IO.Path]::GetFullPath($item.DirectoryName).TrimEnd([char]'\', [char]'/') -ine
                [IO.Path]::GetFullPath($partsRoot).TrimEnd([char]'\', [char]'/')) {
                throw "Unexpected nested collector source part: $($item.FullName)"
            }
            if (-not $expected.Contains($item.Name)) {
                throw "Unexpected unlisted collector source part: $($item.Name)"
            }
            $actual.Add($item)
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
