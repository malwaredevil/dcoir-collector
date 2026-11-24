# Issue #608 Slice 7 implementation plan: native test appendix

Companion to 2026-11-24-issue608-slice7-shipped-path-guard-implementation.md. These are proposed test and driver code, not shipped or executed code. The main plan's baseline containment stop gate and separate execution approval apply first. Source preservation takes precedence: if the baseline demonstrates different legitimate behavior, stop and reconcile the approved spec rather than changing production to fit an assumption.

## A. Native test-first script

Create .github/scripts/Test-DuplicateFunctionCheckPaths.ps1 with these assertions. Test against the missing helper first; then extract the existing functions verbatim. The scratch root is uniquely owned, contains no links, and no case creates a report. The separate pre-implementation junction/alias probe is performed only in a disposable baseline fixture as defined in the main plan. This script uses the exact shipped helper, not an AST-derived or copied implementation.

~~~powershell
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot '../actions/run-duplicate-function-check/DuplicateFunctionCheck.Paths.ps1'
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw 'Missing production path helper' }
$start = (Get-Location).Path
$scratch = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString('N'))
$prefix = 'project_sources/collector/'
$lf = [string][char]10
$cr = [string][char]13
$tab = [string][char]9
$del = [string][char]127
$nul = [string][char]0
$tick = [string][char]96
$positive = @(
    @{ Input = $prefix + 'powershell_duplicate_function_report.json'; Suffix = '.json'; Relative = $prefix + 'powershell_duplicate_function_report.json' }
    @{ Input = 'project_sources\collector\powershell_duplicate_function_report.md'; Suffix = '.md'; Relative = $prefix + 'powershell_duplicate_function_report.md' }
    @{ Input = 'project_sources\collector/nested\report.json'; Suffix = '.json'; Relative = $prefix + 'nested/report.json' }
    @{ Input = '  ' + $prefix + 'report.json  '; Suffix = '.json'; Relative = $prefix + 'report.json' }
    @{ Input = $prefix + 'report.JSON'; Suffix = '.json'; Relative = $prefix + 'report.JSON' }
    @{ Input = $prefix + 'nested/report.md'; Suffix = '.md'; Relative = $prefix + 'nested/report.md' }
    @{ Input = $prefix + 'name..part.json'; Suffix = '.json'; Relative = $prefix + 'name..part.json' }
)
$rejected = @(
    @{ Input = ''; Error = 'output path is required' }
    @{ Input = $null; Error = 'output path is required' }
    @{ Input = '   '; Error = 'output path is required' }
    @{ Input = '/tmp/report.json'; Error = 'must be repo-relative' }
    @{ Input = 'C:/tmp/report.json'; Error = 'must be repo-relative' }
    @{ Input = 'C:report.json'; Error = 'must be repo-relative' }
    @{ Input = $prefix + '../collector/report.json'; Error = 'must not contain traversal' }
    @{ Input = 'project_sources\collector\..\collector\report.json'; Error = 'must not contain traversal' }
    @{ Input = 'project_sources/validation/report.json'; Error = 'must stay under project_sources/collector/' }
    @{ Input = 'project_sources/collector-other/report.json'; Error = 'must stay under project_sources/collector/' }
    @{ Input = 'project_sources/Collector/report.json'; Error = 'must stay under project_sources/collector/' }
    @{ Input = $prefix + 'report.txt'; Error = 'must end with .json' }
    @{ Input = $prefix + 'report.json' + $lf + 'extra'; Error = 'must not contain control characters' }
    @{ Input = $prefix + 'report.json' + $del; Error = 'must not contain control characters' }
    @{ Input = $cr + $prefix + 'report.json'; Error = 'must not contain control characters' }
    @{ Input = $prefix + 'report.json' + $tab; Error = 'must not contain control characters' }
    @{ Input = $prefix + 'a' + $nul + '.json'; Error = 'must not contain control characters' }
    @{ Input = $prefix + 'a' + $cr + $lf + '.json'; Error = 'must not contain control characters' }
    @{ Input = '\\server\share\report.json'; Error = 'must be repo-relative' }
    @{ Input = '\\?\C:\report.json'; Error = 'must be repo-relative' }
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
$posCount = 0
$negCount = 0
$mdCount = 0
$owned = $false
try {
    if (Test-Path -LiteralPath $scratch) { throw 'Scratch path already exists' }
    New-Item -ItemType Directory -Path $scratch -ErrorAction Stop | Out-Null
    $owned = $true
    New-Item -ItemType Directory -Path (Join-Path $scratch $prefix) -Force | Out-Null
    Set-Location -LiteralPath $scratch
    $repoRoot = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd([char]'\', [char]'/') + [System.IO.Path]::DirectorySeparatorChar
    $before = (Get-Location).Path
    $loaded = @(. $helper)
    if ($loaded.Count -ne 0 -or (Get-Location).Path -cne $before) { throw 'Helper load had side effects' }
    foreach ($case in $positive) {
        $actual = @(Resolve-CollectorReportPath $case.Input 'Test' $case.Suffix)
        $expectedFull = [IO.Path]::Combine($before, $case.Relative.Replace('/', [string][IO.Path]::DirectorySeparatorChar))
        if ($actual.Count -ne 1 -or $actual[0].RelativePath -cne $case.Relative -or $actual[0].FullPath -cne $expectedFull) {
            throw "Positive path case failed: $($case.Relative)"
        }
        $posCount++
    }
    foreach ($case in $rejected) {
        $failure = $null
        try { $null = Resolve-CollectorReportPath $case.Input 'Test' '.json' }
        catch { $failure = $_ }
        if ($null -eq $failure -or -not $failure.Exception.Message.Contains($case.Error)) {
            throw "Expected path rejection not observed: $($case.Error)"
        }
        $negCount++
    }
    foreach ($case in $markdown) {
        $actual = @(ConvertTo-MarkdownTableCell $case.Input)
        if ($actual.Count -ne 1 -or $actual[0] -isnot [string] -or $actual[0] -cne $case.Expected) {
            throw 'Markdown escaping case failed'
        }
        $mdCount++
    }
    if (@(Get-ChildItem -LiteralPath (Join-Path $scratch $prefix) -Force).Count -ne 0) { throw 'Guard tests created report artifacts' }
} finally {
    Set-Location -LiteralPath $start
    if ($owned) { Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction Stop }
}
if ($posCount -ne 7 -or $negCount -ne 20 -or $mdCount -ne 9) { throw 'Unexpected case counts' }
Write-Output "DCOIR_DUPLICATE_PATH_TEST_PASS positive=$posCount rejected=$negCount markdown=$mdCount"
~~~

The counts are deliberately exact: changing the table requires changing its asserted counts and the driver record in one reviewed change. RED must fail because the helper is missing, not because a shell executable or unrelated dependency is absent. GREEN must execute real functions and emit the exact record. On Windows compare normal default JSON and Markdown results separately; their different suffixes and path values remain unchanged. Assertion failures are outside the try/catch that tests a hostile input.

## B. Python driver tests and production invocation

Extend the existing .github/github_actions/tools/test_duplicate_function_action_contract.py. Preserve the current REPO_ROOT, SCRIPT_PATH, ACTION_PATH, TEST_PATH and workflow constants. Add imports shutil, subprocess, sys, tempfile and unittest.mock.patch; keep re only if remaining structural checks use it. Create these new driver tests before the implementation below, demonstrate their RED result, then implement the driver. These mocked driver tests are not native Windows evidence.

~~~python
class NativeDriverContractTests(unittest.TestCase):
    def test_missing_surface(self):
        with tempfile.TemporaryDirectory() as directory:
            absent = Path(directory) / "missing.ps1"
            for field in ("HELPER_PATH", "NATIVE_TEST"):
                with self.subTest(field=field), patch(f"__main__.{field}", absent):
                    with self.assertRaisesRegex(AssertionError, "Missing native contract surface"):
                        run_native_contract()

    def test_missing_executable(self):
        with patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(AssertionError, "pwsh is required"):
                run_native_contract()

    def test_native_result_contract(self):
        for code, output in (
            (1, PASS_RECORD),
            (0, ""),
            (0, PASS_RECORD.replace("positive=7", "positive=0")),
            (0, PASS_RECORD + "\n" + PASS_RECORD),
        ):
            with self.subTest(code=code, output=output):
                result = subprocess.CompletedProcess([], code, output, "")
                with patch("shutil.which", return_value="pwsh"), patch("subprocess.run", return_value=result):
                    with self.assertRaises(AssertionError):
                        run_native_contract()

    def test_native_timeout_is_failure(self):
        with patch("shutil.which", return_value="pwsh"), patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pwsh", 120)):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_native_contract()

    def test_exact_child_invocation(self):
        result = subprocess.CompletedProcess([], 0, PASS_RECORD + "\n", "")
        with patch("shutil.which", return_value="pwsh"), patch("subprocess.run", return_value=result) as child:
            self.assertEqual(run_native_contract(), PASS_RECORD + "\n")
            child.assert_called_once_with(
                ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(NATIVE_TEST)],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120, check=False,
            )
~~~

Use patch.object(sys.modules[__name__], field, absent) instead of patching __main__ if test discovery imports the module. Both existing test entry points invoke the file as a script, but the module-safe spelling is preferred. The missing-surface and mocked executable tests assume the real helper/test are already present from Task 2; distinguish this dependency from the intended driver RED.

~~~python
NATIVE_TEST = REPO_ROOT / ".github/scripts/Test-DuplicateFunctionCheckPaths.ps1"
HELPER_PATH = SCRIPT_PATH.with_name("DuplicateFunctionCheck.Paths.ps1")
PASS_RECORD = "DCOIR_DUPLICATE_PATH_TEST_PASS positive=7 rejected=20 markdown=9"

def run_native_contract() -> str:
    for path in (HELPER_PATH, NATIVE_TEST):
        if not path.is_file():
            raise AssertionError(f"Missing native contract surface: {path}")
    exe = shutil.which("pwsh")
    if not exe:
        raise AssertionError("pwsh is required for Windows native contract tests")
    result = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-File", str(NATIVE_TEST)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
    )
    if result.returncode:
        raise AssertionError(f"Native contract failed ({result.returncode}): {result.stdout}\n{result.stderr}")
    records = [line for line in result.stdout.splitlines()
               if line.startswith("DCOIR_DUPLICATE_PATH_TEST_PASS")]
    if records != [PASS_RECORD]:
        raise AssertionError(f"Missing or invalid native evidence: {result.stdout}\n{result.stderr}")
    return result.stdout

class NativeWindowsBehaviorTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows native behavior not executed on this platform")
    def test_shipped_powershell_behavior(self):
        print(run_native_contract(), end="", flush=True)
~~~

Keep existing static tests for defaults, shared discovery, report schema, action dispatch and workflow ordering. Remove normalize_report_path and markdown_table_cell and their behavioral assertions. Adapt structural function checks to the new helper and prove the production dot-source happens before first invocation. Do not reintroduce a behavioral mirror in Python. This test code may be tightened to satisfy actual analyzer findings without changing its intended coverage; record every case change and matching count explicitly. No new dependency and no environment-controlled Windows skip.
