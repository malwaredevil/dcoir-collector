$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot '../actions/run-duplicate-function-check/DuplicateFunctionCheck.Paths.ps1'
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw 'Missing production path helper' }
if (-not $IsWindows -or $PSVersionTable.PSVersion.Major -lt 7) { throw 'Windows pwsh 7 required' }
$start = (Get-Location).Path
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('dcoir-608-path-test-' + [guid]::NewGuid().ToString('N'))
$owned = $false
$links = [System.Collections.Generic.List[object]]::new()
$posCount = 0
$negCount = 0
$mdCount = 0
$prefix = 'project_sources/collector/'
$lf = [string][char]10
$cr = [string][char]13
$tab = [string][char]9
$del = [string][char]127
$nul = [string][char]0
$tick = [string][char]96
function New-OrdinaryDirectory([string]$Path) { $null = [IO.Directory]::CreateDirectory($Path) }
function Set-ProbeRoot([string]$Root) {
  Set-Location -LiteralPath $Root
  $script:repoRoot = [IO.Path]::GetFullPath((Get-Location).Path).TrimEnd([char]'\',[char]'/') + [IO.Path]::DirectorySeparatorChar
}
function New-OwnedAlias([string]$Kind,[string]$Link,[string]$Target) {
  $directory = $Kind -in @('Junction','DirectorySymbolicLink')
  $links.Add(@{ Path = $Link; Directory = $directory })
  switch ($Kind) {
    Junction { $null = New-Item -ItemType Junction -Path $Link -Target $Target -ErrorAction Stop }
    DirectorySymbolicLink { $null = [IO.Directory]::CreateSymbolicLink($Link,$Target) }
    FileSymbolicLink { $null = [IO.File]::CreateSymbolicLink($Link,$Target) }
    HardLink { $null = New-Item -ItemType HardLink -Path $Link -Target $Target -ErrorAction Stop }
    default { throw 'Unknown fixture kind' }
  }
  $attributes = [IO.File]::GetAttributes($Link)
  $item = Get-Item -LiteralPath $Link -Force -ErrorAction Stop
  if ($Kind -eq 'HardLink') {
    if ($item.LinkType -ne 'HardLink' -or (Get-Item -LiteralPath $Target -Force -ErrorAction Stop).LinkType -ne 'HardLink' -or ($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Hardlink fixture mismatch' }
    if ([IO.File]::ReadAllText($Link) -cne 'owned-sentinel') { throw 'Hardlink sentinel mismatch' }
  } else {
    $expected = if ($Kind -eq 'Junction') { 'Junction' } else { 'SymbolicLink' }
    if (($attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -or $item.LinkType -ne $expected -or [string](@($item.Target)[0]) -ne $Target) { throw "Alias fixture mismatch: $Kind" }
  }
}
function Assert-SafePath([object]$InputPath,[string]$Suffix,[string]$Relative,[string]$Root) {
  $actual = @(Resolve-CollectorReportPath $InputPath 'Test' $Suffix)
  $expected = [IO.Path]::Combine($Root,$Relative.Replace('/',[string][IO.Path]::DirectorySeparatorChar))
  if ($actual.Count -ne 1 -or $actual[0].RelativePath -cne $Relative -or $actual[0].FullPath -cne $expected) { throw "Positive path case failed: $Relative" }
}
function Assert-RejectedPath([object]$InputPath,[string]$Expected) {
  $failure = $null
  try { $null = Resolve-CollectorReportPath $InputPath 'Test' '.json' } catch { $failure = $_ }
  if ($null -eq $failure -or -not $failure.Exception.Message.Contains($Expected)) { throw "Expected path rejection not observed: $Expected (input=$InputPath; actual=$failure)" }
}
function Get-OrdinaryFixtureSnapshot([string]$Root) {
  $pending = [System.Collections.Generic.Queue[string]]::new()
  $pending.Enqueue($Root)
  $records = [System.Collections.Generic.List[string]]::new()
  while ($pending.Count -gt 0) {
    $directory = $pending.Dequeue()
    foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
      if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Unexpected alias in ordinary fixture' }
      if ($item.PSIsContainer) { $records.Add("directory|$($item.FullName)"); $pending.Enqueue($item.FullName) }
      else { $records.Add("file|$($item.FullName)|$((Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash)") }
    }
  }
  return ($records | Sort-Object) -join "`n"
}
try {
  if (Test-Path -LiteralPath $scratch) { throw 'Scratch path already exists' }
  New-Item -ItemType Directory -Path $scratch -ErrorAction Stop | Out-Null
  $owned = $true
  $repo = Join-Path $scratch 'ordinary'
  $collector = Join-Path $repo $prefix
  New-OrdinaryDirectory (Join-Path $collector 'existing')
  New-OrdinaryDirectory (Join-Path $collector 'literal [x]')
  $ordinary = [IO.Path]::GetFullPath((Join-Path $collector 'existing/report.json'))
  [IO.File]::WriteAllText($ordinary,'ordinary-sentinel')
  Set-ProbeRoot $repo
  $before = (Get-Location).Path
  $snapshot = Get-OrdinaryFixtureSnapshot $repo
  $loaded = @(. $helper)
  if ($loaded.Count -ne 0 -or (Get-Location).Path -cne $before) { throw 'Helper load had side effects' }
  $positive = @(
    @{ Input = $prefix+'powershell_duplicate_function_report.json'; Suffix = '.json'; Relative = $prefix+'powershell_duplicate_function_report.json' }
    @{ Input = 'project_sources\collector\powershell_duplicate_function_report.md'; Suffix = '.md'; Relative = $prefix+'powershell_duplicate_function_report.md' }
    @{ Input = 'project_sources\collector/nested\report.json'; Suffix = '.json'; Relative = $prefix+'nested/report.json' }
    @{ Input = '  '+$prefix+'report.json  '; Suffix = '.json'; Relative = $prefix+'report.json' }
    @{ Input = $prefix+'report.JSON'; Suffix = '.json'; Relative = $prefix+'report.JSON' }
    @{ Input = $prefix+'nested/report.md'; Suffix = '.md'; Relative = $prefix+'nested/report.md' }
    @{ Input = $prefix+'name..part.json'; Suffix = '.json'; Relative = $prefix+'name..part.json' }
    @{ Input = $prefix+'existing/report.json'; Suffix = '.json'; Relative = $prefix+'existing/report.json' }
    @{ Input = $prefix+'existing/new.json'; Suffix = '.json'; Relative = $prefix+'existing/new.json' }
    @{ Input = $prefix+'fresh/deep/report.json'; Suffix = '.json'; Relative = $prefix+'fresh/deep/report.json' }
    @{ Input = $prefix+'literal [x]/report name.json'; Suffix = '.json'; Relative = $prefix+'literal [x]/report name.json' }
    @{ Input = $prefix+'LPT10.json'; Suffix = '.json'; Relative = $prefix+'LPT10.json' }
  )
  $rejected = @(
    @{ Error = 'output path is required'; Inputs = @(
      (''),
      ($null),
      ('   ')
    ) }
    @{ Error = 'must be repo-relative'; Inputs = @(
      ('/tmp/report.json'),
      ('C:/tmp/report.json'),
      ('C:report.json')
    ) }
    @{ Error = 'must not contain traversal'; Inputs = @(
      ($prefix + '../collector/report.json'),
      ('project_sources\collector\..\collector\report.json')
    ) }
    @{ Error = 'must stay under project_sources/collector/'; Inputs = @(
      ('project_sources/validation/report.json'),
      ('project_sources/collector-other/report.json'),
      ('project_sources/Collector/report.json')
    ) }
    @{ Error = 'must end with .json'; Inputs = @(
      ($prefix + 'report.txt')
    ) }
    @{ Error = 'must not contain control characters'; Inputs = @(
      ($prefix + 'report.json' + $lf + 'extra'),
      ($prefix + 'report.json' + $del),
      ($cr + $prefix + 'report.json'),
      ($prefix + 'report.json' + $tab),
      ($prefix + 'a' + $nul + '.json'),
      ($prefix + 'a' + $cr + $lf + '.json')
    ) }
    @{ Error = 'must be repo-relative'; Inputs = @(
      ('\\server\share\report.json'),
      ('\\?\C:\report.json')
    ) }
    @{ Error = 'ambiguous path component'; Inputs = @(
      ($prefix + 'nested//report.json'),
      ($prefix + './report.json'),
      ($prefix + '.../report.json'),
      ($prefix + 'name./report.json'),
      ($prefix + 'name /report.json')
    ) }
    @{ Error = 'invalid Windows path character'; Inputs = @(
      ($prefix + 'report:stream.json'),
      ($prefix + 'name:part/report.json'),
      ($prefix + 'bad*/report.json'),
      ($prefix + 'bad?/report.json'),
      ($prefix + '<bad>/report.json'),
      ($prefix + 'bad"/report.json'),
      ($prefix + 'bad|/report.json')
    ) }
    @{ Error = 'reserved Windows device name'; Inputs = @(
      ($prefix + 'con.json'),
      ($prefix + 'NUL .json'),
      ($prefix + 'aux/report.json'),
      ($prefix + 'PRN.json'),
      ($prefix + 'COM1.json'),
      ($prefix + 'LPT9/report.json'),
      ($prefix + 'COM' + [char]0x00B9 + '.json'),
      ($prefix + 'LPT' + [char]0x00B3 + '.json'),
      ($prefix + 'CONIN$.json'),
      ($prefix + 'CONOUT$.json')
    ) }
  )
  $markdown = @(
    @{ Input = $null; Expected = '' }
    @{ Input = ''; Expected = '' }
    @{ Input = 'plain text'; Expected = 'plain text' }
    @{ Input = 'a' + $lf + 'b'; Expected = 'a b' }
    @{ Input = 'a' + $cr + $lf + 'b'; Expected = 'a b' }
    @{ Input = 'name' + $tick + 'with|table' + $lf + '<&>'; Expected = 'name&#96;with&#124;table &lt;&amp;&gt;' }
    @{ Input = '&amp;'; Expected = '&amp;amp;' }
    @{ Input = 42; Expected = '42' }
    @{ Input = 'a' + $cr + 'b'; Expected = 'a' + $cr + 'b' }
  )
  foreach ($case in $positive) {
    Assert-SafePath $case.Input $case.Suffix $case.Relative $repo
    $posCount++
  }
  foreach ($case in $rejected) {
    foreach ($value in $case.Inputs) {
      Assert-RejectedPath $value $case.Error
      $negCount++
    }
  }
  foreach ($case in $markdown) {
    $actual = @(ConvertTo-MarkdownTableCell $case.Input)
    if ($actual.Count -ne 1 -or $actual[0] -isnot [string] -or $actual[0] -cne $case.Expected) { throw 'Markdown escaping case failed' }
    $mdCount++
  }
  if ((Get-OrdinaryFixtureSnapshot $repo) -cne $snapshot) { throw 'Ordinary fixture changed during guard tests' }
  $physicalErrors = @('reparse point','reparse point','reparse point','reparse point','reparse point','reparse point','reparse point','hard-linked output','ancestor must be a directory','output must be a regular file','reparse point','Repository root mismatch')
  for ($i=1;$i -le 12;$i++) {
    $caseRoot = Join-Path $scratch "fixture-$i"
    $repo = Join-Path $caseRoot 'repo'
    $outside = Join-Path $caseRoot 'outside'
    $collector = Join-Path $repo $prefix
    New-OrdinaryDirectory $outside
    New-OrdinaryDirectory $collector
    $sentinel = Join-Path $outside 'sentinel.json'
    [IO.File]::WriteAllText($sentinel,'owned-sentinel')
    Set-ProbeRoot $repo
    Assert-SafePath ($prefix+'safe.json') '.json' ($prefix+'safe.json') $repo
    $relative = $prefix+'report.json'
    switch ($i) {
      1 {
        [IO.Directory]::Delete($collector,$false)
        [IO.Directory]::Delete((Join-Path $repo 'project_sources'),$false)
        New-OrdinaryDirectory (Join-Path $outside 'collector')
        New-OwnedAlias Junction (Join-Path $repo 'project_sources') $outside
      }
      2 { [IO.Directory]::Delete($collector,$false); New-OwnedAlias Junction ($collector.TrimEnd([char]'\',[char]'/')) $outside }
      3 { New-OwnedAlias Junction (Join-Path $collector 'link') $outside; $relative = $prefix+'link/report.json' }
      4 { $inside = Join-Path $collector 'inside'; New-OrdinaryDirectory $inside; New-OwnedAlias Junction (Join-Path $collector 'link') $inside; $relative = $prefix+'link/report.json' }
      5 { New-OwnedAlias DirectorySymbolicLink (Join-Path $collector 'link') $outside; $relative = $prefix+'link/report.json' }
      6 { New-OwnedAlias FileSymbolicLink (Join-Path $collector 'report.json') $sentinel }
      7 { New-OwnedAlias FileSymbolicLink (Join-Path $collector 'report.json') (Join-Path $outside 'missing.json') }
      8 { New-OwnedAlias HardLink (Join-Path $collector 'report.json') $sentinel }
      9 { [IO.File]::WriteAllText((Join-Path $collector 'block'),'owned-block'); $relative = $prefix+'block/report.json' }
      10 { New-OrdinaryDirectory (Join-Path $collector 'report.json') }
      11 { Set-Location -LiteralPath $caseRoot; $aliasRoot = Join-Path $caseRoot 'root-link'; New-OwnedAlias Junction $aliasRoot $repo; Set-ProbeRoot $aliasRoot; if ((Get-Location).Path -cne $aliasRoot) { throw 'Root junction not representable in cwd' } }
      12 { $script:repoRoot = [IO.Path]::GetFullPath($outside).TrimEnd([char]'\',[char]'/') + [IO.Path]::DirectorySeparatorChar }
    }
    Assert-RejectedPath $relative $physicalErrors[$i-1]
    if ([IO.File]::ReadAllText($sentinel) -cne 'owned-sentinel' -or [IO.File]::Exists((Join-Path $outside 'report.json')) -or [IO.File]::Exists((Join-Path $outside 'collector/report.json')) -or [IO.File]::Exists((Join-Path $outside 'missing.json'))) { throw "Outside fixture changed: $i" }
    $negCount++
    Set-Location -LiteralPath $scratch
  }
  Set-ProbeRoot (Join-Path $scratch 'ordinary')
  & {
    $originalMetadata = (Get-Command Get-DuplicateReportPathMetadata -CommandType Function -ErrorAction Stop).ScriptBlock
    function Get-DuplicateReportPathMetadata([string]$fullPath) {
      if ($fullPath -ceq $ordinary) { throw 'Synthetic metadata access failure' }
      & $originalMetadata $fullPath
    }
    Assert-RejectedPath ($prefix+'existing/report.json') 'Synthetic metadata access failure'
  }
  & {
    $originalMetadata = (Get-Command Get-DuplicateReportPathMetadata -CommandType Function -ErrorAction Stop).ScriptBlock
    function Get-DuplicateReportPathMetadata([string]$fullPath) {
      if ($fullPath -ceq $ordinary) { return [pscustomobject]@{ Attributes = [uint32][IO.FileAttributes]::Archive; NumberOfLinks = [uint32]0 } }
      & $originalMetadata $fullPath
    }
    Assert-RejectedPath ($prefix+'existing/report.json') 'hard-linked output'
  }
  Assert-SafePath ($prefix+'existing/report.json') '.json' ($prefix+'existing/report.json') (Get-Location).Path
  if ((Get-OrdinaryFixtureSnapshot (Get-Location).Path) -cne $snapshot) { throw 'Ordinary fixture changed during failure controls' }
} finally {
  Set-Location -LiteralPath $start
  if ($owned) {
    for ($index=$links.Count-1;$index -ge 0;$index--) {
      $entry = $links[$index]
      try { $attrs = [IO.File]::GetAttributes($entry.Path) }
      catch [IO.FileNotFoundException] { continue }
      catch [IO.DirectoryNotFoundException] { continue }
      if ($entry.Directory) {
        if (($attrs -band [IO.FileAttributes]::ReparsePoint) -eq 0) { throw 'Unverified directory alias; refusing recursive cleanup' }
        [IO.Directory]::Delete($entry.Path,$false)
      } else { [IO.File]::Delete($entry.Path) }
      try { $null = [IO.File]::GetAttributes($entry.Path); throw 'Alias cleanup failed' }
      catch [IO.FileNotFoundException] { }
      catch [IO.DirectoryNotFoundException] { }
    }
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction Stop
  }
}
if ($posCount -ne 12 -or $negCount -ne 54 -or $mdCount -ne 9) { throw 'Unexpected case counts' }
Write-Output "DCOIR_DUPLICATE_PATH_TEST_PASS positive=$posCount rejected=$negCount markdown=$mdCount"
