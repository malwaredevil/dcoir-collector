# Issue #608 Slice 7: hardened native test appendix

Approved design: ../specs/2026-11-24-issue608-slice7-path-containment-amendment.md (2800009d42a5356a3e8449f96ff2f9940592e07a). Reuse the original native test appendix (36e3a0092f72d40fcd262df71a589a845599f953) for its exact seven safe / twenty rejected / nine Markdown cases and Python subprocess tests. This appendix replaces its extraction-only acceptance, fixture setup/cleanup, counts, and marker. Companion: 2026-11-24-issue608-slice7-containment-metadata-appendix.md. The amended plan governs authorization and ordering. This is proposed, unexecuted test code.

## A. Counted lexical and Markdown cases

Keep the original three tables unchanged. Append these five positive and twenty-two rejected rows; each uses the original assertion loop. Preserve all original rejection message fragments and valid FullPath/RelativePath checks.

~~~powershell
$positive += @(
    @{ Input = $prefix + 'existing/report.json'; Suffix = '.json'; Relative = $prefix + 'existing/report.json' }
    @{ Input = $prefix + 'existing/new.json'; Suffix = '.json'; Relative = $prefix + 'existing/new.json' }
    @{ Input = $prefix + 'fresh/deep/report.json'; Suffix = '.json'; Relative = $prefix + 'fresh/deep/report.json' }
    @{ Input = $prefix + 'literal [x]/report name.json'; Suffix = '.json'; Relative = $prefix + 'literal [x]/report name.json' }
    @{ Input = $prefix + 'LPT10.json'; Suffix = '.json'; Relative = $prefix + 'LPT10.json' }
)
$rejected += @(
    @{ Input = $prefix + 'nested//report.json'; Error = 'ambiguous path component' }
    @{ Input = $prefix + './report.json'; Error = 'ambiguous path component' }
    @{ Input = $prefix + '.../report.json'; Error = 'ambiguous path component' }
    @{ Input = $prefix + 'name./report.json'; Error = 'ambiguous path component' }
    @{ Input = $prefix + 'name /report.json'; Error = 'ambiguous path component' }
    @{ Input = $prefix + 'report:stream.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + 'name:part/report.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + 'bad*/report.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + 'bad?/report.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + '<bad>/report.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + 'bad"/report.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + 'bad|/report.json'; Error = 'invalid Windows path character' }
    @{ Input = $prefix + 'con.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'NUL .json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'aux/report.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'PRN.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'COM1.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'LPT9/report.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'COM' + [char]0x00B9 + '.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'LPT' + [char]0x00B3 + '.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'CONIN$.json'; Error = 'reserved Windows device name' }
    @{ Input = $prefix + 'CONOUT$.json'; Error = 'reserved Windows device name' }
)
~~~

Keep the original missing-helper check first, then require Windows pwsh 7. Create a GUID-owned parent containing ordinary repo and outside sibling directories. Initialize cwd and repoRoot exactly as production. Before positive loop create existing/report.json with fixed sentinel bytes, existing directory and literal [x] directory via [IO.Directory]::CreateDirectory; keep fresh/deep nonexistent. Snapshot ordinary fixture before and after guard calls (paths/types and hashes of regular files; never recurse through links). Verify unchanged sentinel and no new report files. Keep original Markdown loop. No output or cwd changes from loading definitions.

## B. Twelve physical/anchor rejection cases

Use separate, uniquely owned sibling test repositories per row. Every fixture has the same collector prefix. Verify setup before calling the public resolver: ordinary parent type, actual reparse attributes or hardlink metadata, and expected target when applicable. Never use the candidate resolver to establish fixture correctness. The exact case inputs and error fragments:

| # | Fixture under owned parent | Relative input | Expected error fragment |
|---|---|---|---|
| 1 | project_sources junction to outside folder with collector child | project_sources/collector/report.json | reparse point |
| 2 | collector junction to outside directory | project_sources/collector/report.json | reparse point |
| 3 | nested junction to outside directory | project_sources/collector/link/report.json | reparse point |
| 4 | nested junction to ordinary in-tree directory | project_sources/collector/link/report.json | reparse point |
| 5 | nested directory symbolic link to outside directory | project_sources/collector/link/report.json | reparse point |
| 6 | file symbolic link to owned outside sentinel | project_sources/collector/report.json | reparse point |
| 7 | dangling file symbolic link to nonexistent owned outside leaf | project_sources/collector/report.json | reparse point |
| 8 | hard-linked leaf to owned outside sentinel on same volume | project_sources/collector/report.json | hard-linked output |
| 9 | intermediate regular file named block | project_sources/collector/block/report.json | ancestor must be a directory |
| 10 | existing directory named report.json | project_sources/collector/report.json | output must be a regular file |
| 11 | checkout root is junction to owned normal repo | project_sources/collector/report.json | reparse point |
| 12 | ordinary repo but repoRoot set to different owned sibling | project_sources/collector/report.json | Repository root mismatch |

For each fixture use [IO.Directory]::CreateDirectory for normal dirs and [IO.File]::WriteAllText for sentinel files. Exercise an ordinary safe path before adding each link (uncounted control). Use these creation operations on known safe literal fixture paths, never on a hostile report input:

~~~powershell
# Register intended link path and kind before creation.
$links.Add(@{ Path = $link; Directory = $true })
$null = New-Item -ItemType Junction -Path $link -Target $target -ErrorAction Stop
$item = Get-Item -LiteralPath $link -Force -ErrorAction Stop
if ($item.LinkType -ne 'Junction' -or [string](@($item.Target)[0]) -ne $target) {
    throw 'Junction fixture mismatch'
}
# For symbolic directory and file fixtures (including dangling target):
$null = [IO.Directory]::CreateSymbolicLink($link,$target)
$null = [IO.File]::CreateSymbolicLink($link,$target)
# Only use the appropriate one of the above calls for the current row.
# For the hardlink fixture use this instead, with Directory=false registration:
$null = New-Item -ItemType HardLink -Path $link -Target $target -ErrorAction Stop
if ((Get-Item -LiteralPath $link -Force -ErrorAction Stop).LinkType -ne 'HardLink' -or
    (Get-Item -LiteralPath $target -Force -ErrorAction Stop).LinkType -ne 'HardLink') {
    throw 'Hardlink fixture mismatch'
}
~~~

Validate link type/target and reparse attributes before testing. For hardlink verify sentinel bytes identical on both names before call. Use File.GetAttributes and Get-Item -LiteralPath -Force; for dangling file symlink verify target missing under the owned ordinary outside directory. Do not elevate privileges or change Windows settings. For #11 verify cwd still names junction rather than silently canonicalizing to target. If not representable, stop for design review. For #12 set exact production root expression from other owned directory while cwd remains actual fixture root. Restore after each row. Fixtures must exist and be independently verified; a capability error is a failure, not a skip.

~~~powershell
function Assert-DuplicatePathFixtureRejected {
    param([string]$Relative, [string]$Expected)
    $failure = $null
    try { $null = Resolve-CollectorReportPath $Relative 'Test' '.json' }
    catch { $failure = $_ }
    if ($null -eq $failure -or -not $failure.Exception.Message.Contains($Expected)) {
        throw "Expected fixture rejection not observed: $Expected"
    }
}
~~~

Call once per row; increment $negCount only after assertion and sentinel/absence check. Check outside fixture sentinels unchanged; do not write through any alias. Cleanup: restore cwd first; remove registered link paths in reverse order. Use Directory.Delete(path,false) for directory links and File.Delete(path) for file links/hardlinks; never delete the target. Use literal attributes to verify link absence, accepting only genuine FileNotFoundException/DirectoryNotFoundException under known ordinary parent. If a link cannot safely be unlinked and verified, throw and retain owned scratch rather than recursive cleanup. Only recursively remove the unique parent after verifying every registered link absent; no recursive traversal of links. Register intended links before creation to catch partial failure.

An uncounted scratch test must inject a terminating metadata-read error at a verified existing child (temporarily override Get-DuplicateReportPathMetadata in a scratch helper/session; never commit or override production) and assert the public resolver fails rather than treating it as missing. Restore actual definition and run green. A successful lookup with NumberOfLinks 0 must also fail, not count as an ordinary leaf. These are supplemental failure-path checks, not substitutes for native fixtures.

## C. Marker and Python driver

Native completion assertion replaces old assertion:

~~~powershell
if ($posCount -ne 12 -or $negCount -ne 54 -or $mdCount -ne 9) { throw 'Unexpected case counts' }
Write-Output "DCOIR_DUPLICATE_PATH_TEST_PASS positive=$posCount rejected=$negCount markdown=$mdCount"
~~~

54 = original 20 + 22 syntax + 12 filesystem/anchor; 12 = original 7 + 5 safe; Markdown 9 unchanged. Fixture checks and supplemental controls must execute. Require direct Windows red/green, not mocks. First the exact native script fails with Missing production path helper on the baseline. Then extract the original bodies into the helper in a scratch copy; run each newly prohibited input separately against the exact original resolver, preserving baseline results (accepted vs intended/unrelated rejection). The confirmed junction red evidence already exists. Do not call the original entrypoint with unsafe output values. Do not require legacy acceptance for cases already rejected by the legacy runtime. Do not change safe behavior to fit an assertion.

Use original appendix B's subprocess driver and tests, changing patch(f"__main__.{field}", absent) to patch.object(sys.modules[__name__], field, absent) and replacing its marker with:

~~~python
PASS_RECORD = "DCOIR_DUPLICATE_PATH_TEST_PASS positive=12 rejected=54 markdown=9"
~~~

Update the zero-case mock to replace positive=12 with positive=0; add wrong rejected count, wrong Markdown count, malformed/extra marker and correct-marker cases. The native process must have exit 0 and exactly one exact marker; missing helper/test/pwsh, nonzero/timeout, absent/zero/wrong/duplicate marker fail. On Linux explicit native test skip only, not a security pass. Preserve structural tests for action dispatch/defaults, report schema, shared scan and workflow ordering; replace mirror/naive function_block tests with definition-owner and dot-source ordering checks, including both initial resolver calls before any report writes. A private helper may exist inside the same definitions-only file; there must be exactly one owner per public function. No YAML changes.

Mutation checks only in scratch copies: remove reparse check, ambiguous component check, hardlink-count check, original control-character check, and escaping replacement separately; require relevant direct assertions fail, restore and rerun green. No committed negative mutation. If native metadata is unavailable or a safe control fails, stop and resolve the design rather than relaxing security assertions.
