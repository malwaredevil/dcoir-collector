# Issue #608 Slice 7: proposed hardened resolver and write boundary

Approved design: ../specs/2026-11-24-issue608-slice7-path-containment-amendment.md. Companion native test appendix: 2026-11-24-issue608-slice7-containment-native-appendix.md. Proposed implementation only; do not modify executable files before plan execution approval. Preserve the original two public signatures and verbatim Markdown body.

## Native metadata design

The two existing action callers are in windows-latest jobs in reusable-validate-on-pr.yml and reusable-validate-on-push.yml. The Ubuntu Draft job runs only the Python structural/mocked tests. Windows pwsh 7 is the mandatory supported behavioral runtime; explicitly fail closed if native metadata is unavailable. Linux static checks are not a behavioral pass. Before implementation, verify all live callers; if a production non-Windows caller exists, stop for design reconciliation. No new installed package, privileged utility, permission change or external process. The Windows API is lazy-loaded with Add-Type inside a private helper; dot-sourcing definitions does not compile or touch files. The API requests a zero-access metadata handle to the named entry, not a handle for reading/writing report contents, with OPEN_REPARSE_POINT and BACKUP_SEMANTICS. Query link count and attributes using GetFileInformationByHandle. Microsoft references:

- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information
- https://learn.microsoft.com/en-us/windows/win32/fileio/hard-links-and-junctions

Do not use fsutil (administrative requirement) or treat an empty PowerShell LinkType as proof of a single link. Require actual native evidence for ordinary and missing files/directories, dangling links, junctions and hardlink count before relying on this code. Metadata errors terminate; do not catch and silently treat them as absence. The local checkout root is trusted; this is not concurrent-race-proof containment.

~~~powershell
function Get-DuplicateReportPathMetadata([string]$fullPath) {
    if (-not $IsWindows) { throw 'Windows native path metadata is required' }
    if (-not ('Dcoir.DuplicateReportPathNativeV1' -as [type])) {
        Add-Type -ErrorAction Stop -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Dcoir {
    public sealed class DuplicateReportPathMetadataV1 {
        public uint Attributes { get; set; }
        public uint NumberOfLinks { get; set; }
    }
    public static class DuplicateReportPathNativeV1 {
        [StructLayout(LayoutKind.Sequential)]
        private struct FileInformation {
            public uint Attributes;
            public uint CreationLow, CreationHigh;
            public uint AccessLow, AccessHigh;
            public uint WriteLow, WriteHigh;
            public uint VolumeSerial, SizeHigh, SizeLow;
            public uint NumberOfLinks, IndexHigh, IndexLow;
        }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true, ExactSpelling=true)]
        private static extern SafeFileHandle CreateFileW(string name, uint access,
            uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
        [DllImport("kernel32.dll", SetLastError=true, ExactSpelling=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool GetFileInformationByHandle(SafeFileHandle handle, out FileInformation info);
        public static DuplicateReportPathMetadataV1 Read(string path) {
            // 0 = metadata-only access; 7 = all sharing modes;
            // 3 = OPEN_EXISTING; 0x02200000 = open reparse point + backup semantics.
            using (SafeFileHandle handle = CreateFileW(path, 0, 7, IntPtr.Zero,
                       3, 0x02200000, IntPtr.Zero)) {
                if (handle.IsInvalid) {
                    int error = Marshal.GetLastWin32Error();
                    if (error == 2) return null;
                    throw new Win32Exception(error);
                }
                FileInformation info;
                if (!GetFileInformationByHandle(handle, out info))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return new DuplicateReportPathMetadataV1 {
                    Attributes = info.Attributes, NumberOfLinks = info.NumberOfLinks
                };
            }
        }
    }
}
'@
    }
    return [Dcoir.DuplicateReportPathNativeV1]::Read($fullPath)
}
~~~

Only ERROR_FILE_NOT_FOUND (2) returns null. ERROR_PATH_NOT_FOUND (3) or any other error throws; a disappearing previously verified parent is not proof of a safe missing leaf. Parent-to-child inspection stops at first genuinely absent immediate child beneath a verified normal directory. If Windows metadata actually returns error 3 for an ordinary legitimate immediate missing child, record exact positive and negative controls and stop for a bounded design correction; do not indiscriminately swallow error 3 or access failures. Never traverse past a detected linked parent. No data read/write or link-target resolution in the guard. The zero-access metadata handle still names an inside-checkout entry, including when it is a hardlink; it does not open an outside pathname or read the file contents. Do not advertise stronger security.

## Hardened resolver

In the new definitions-only helper retain the original Resolve-CollectorReportPath signature and lexical checks in order through expected suffix validation. Replace its original GetFullPath/repository-prefix/return block with the following, and keep the Markdown escaping function verbatim. Retain original case-sensitive lexical prefix, whole-value whitespace trim and suffix-case handling. The exact collector directory and checkout root must already exist. Literal directory components below that may be absent and created later.

~~~powershell
  $components = @($normalized.Split([char]'/'))
  foreach ($component in $components) {
    if ($component.Length -eq 0 -or $component.EndsWith(' ') -or $component.EndsWith('.')) {
      throw "$label output path contains an ambiguous path component: $pathValue"
    }
    if ($component -match '[:<>"|?*]') {
      throw "$label output path contains an invalid Windows path character: $pathValue"
    }
    $device = $component.Split([char]'.')[0].TrimEnd([char]' ')
    if ($device -match '^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9\u00B9\u00B2\u00B3]|LPT[1-9\u00B9\u00B2\u00B3])$') {
      throw "$label output path contains a reserved Windows device name: $pathValue"
    }
  }
  $location = Get-Location
  if ($location.Provider.Name -ne 'FileSystem') { throw 'Repository root must be a FileSystem provider path.' }
  $separator = [IO.Path]::DirectorySeparatorChar
  $anchor = [IO.Path]::GetFullPath($location.ProviderPath)
  $prefix = $anchor.TrimEnd([char]'\',[char]'/') + $separator
  $comparison = [StringComparison]::Ordinal
  if ($IsWindows) { $comparison = [StringComparison]::OrdinalIgnoreCase }
  if (-not $prefix.Equals($repoRoot, $comparison)) { throw 'Repository root mismatch.' }
  $collectorRoot = [IO.Path]::GetFullPath([IO.Path]::Combine($anchor,'project_sources','collector'))
  $collectorPrefix = $collectorRoot.TrimEnd([char]'\',[char]'/') + $separator
  $resolved = [IO.Path]::GetFullPath([IO.Path]::Combine($anchor,$normalized.Replace('/',[string]$separator)))
  if (-not $resolved.StartsWith($collectorPrefix,$comparison) -or -not $resolved.StartsWith($prefix,$comparison)) {
    throw "$label output path resolves outside the collector directory: $pathValue"
  }
  $current = $anchor
  for ($index = -1; $index -lt $components.Count; $index++) {
    if ($index -ge 0) { $current = [IO.Path]::Combine($current,$components[$index]) }
    $metadata = Get-DuplicateReportPathMetadata $current
    if ($null -eq $metadata) {
      if ($index -lt 2) { throw 'Repository and collector root directories must exist.' }
      break
    }
    $attributes = [IO.FileAttributes]$metadata.Attributes
    if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "$label output path contains a reparse point: $current"
    }
    $directory = ($attributes -band [IO.FileAttributes]::Directory) -ne 0
    if ($index -lt ($components.Count - 1)) {
      if (-not $directory) { throw "$label output path ancestor must be a directory: $current" }
    } else {
      if ($directory -or (($attributes -band [IO.FileAttributes]::Device) -ne 0)) {
        throw "$label output must be a regular file: $current"
      }
      if ($metadata.NumberOfLinks -ne 1) { throw "$label output path contains a hard-linked output or unverified link count: $current" }
    }
  }
  return [pscustomobject]@{ FullPath = $resolved; RelativePath = $normalized }
~~~

Source-review the proposed C# struct/flags and PowerShell enum comparisons with actual native results. Keep the helper definitions-only, not a generic filesystem API. Verify exact error categories against test appendix; do not alter existing lexical errors. Under Windows the resolved prefix uses OrdinalIgnoreCase, while input subtree remains Ordinal. Check the root and every existing component in order; a directory leaf and non-directory ancestor are rejected. The only permitted missing components are below the existing checked collector root. Require one link, not merely a nonzero count. Reject any reparse point, including links with in-tree destinations. Never follow a report leaf to inspect its target. If native evidence or analysis disproves an assumption, stop and disposition rather than weakening the tests.

## Write boundary

Keep both original preflight resolver calls and distinct-output check before scanning. At the original JSON directory/write boundary replace the old Split-Path/Test-Path/New-Item block with:

~~~powershell
$jsonOutput = Resolve-CollectorReportPath $env:DUPLICATE_FUNCTION_OUTPUT_JSON 'JSON' '.json'
$null = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($jsonOutput.FullPath))
$jsonOutput = Resolve-CollectorReportPath $env:DUPLICATE_FUNCTION_OUTPUT_JSON 'JSON' '.json'
~~~

Keep the original following ConvertTo-Json/Set-Content -LiteralPath pipeline exactly. At the original Markdown write boundary use:

~~~powershell
$markdownOutput = Resolve-CollectorReportPath $env:DUPLICATE_FUNCTION_OUTPUT_MARKDOWN 'Markdown' '.md'
$null = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($markdownOutput.FullPath))
$markdownOutput = Resolve-CollectorReportPath $env:DUPLICATE_FUNCTION_OUTPUT_MARKDOWN 'Markdown' '.md'
~~~

Keep original Set-Content -LiteralPath, encoding and normal order; preserve original report relative paths, data, exit policy and all scan behavior. Both outputs must pass initial validation before any output or directory is written. Rechecks immediately before and after directory creation narrow but do not eliminate TOCTOU. Caller-owned environment and isolated checkout are trusted; do not add a global filesystem sandbox. Do not use New-Item -Path for report directories containing literal brackets. Test action-level hostile/valid pairs before any write plus existing ordinary output and literal bracket directories in an isolated fixture.

The proposed code must pass native Windows, Windows PowerShell 5.1 parsing, existing analyzer policy and size limit; no suppression expansion or weakening of policy. Revisit if the standard runtime cannot compile the native metadata bridge. Document this runtime choice in the action README. All source code remains pending separate operator approval, test-first execution and review.
