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

function ConvertTo-MarkdownTableCell([object]$value) {
  if ($null -eq $value) {
    return ''
  }
  $text = [string]$value
  $text = $text -replace "`r?`n", ' '
  $text = $text.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
  $text = $text.Replace('|', '&#124;').Replace('`', '&#96;')
  return $text
}

function Resolve-CollectorReportPath([string]$pathValue, [string]$label, [string]$expectedSuffix) {
  if ([string]::IsNullOrWhiteSpace($pathValue)) {
    throw "$label output path is required."
  }
  $rawNormalized = $pathValue.Replace('\', '/')
  if ($rawNormalized -match '[\x00-\x1F\x7F]') {
    throw "$label output path must not contain control characters: $pathValue"
  }
  $normalized = $rawNormalized.Trim()
  if ($normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:') {
    throw "$label output path must be repo-relative: $pathValue"
  }
  if ($normalized -match '(^|/)\.\.($|/)') {
    throw "$label output path must not contain traversal: $pathValue"
  }
  if (-not $normalized.StartsWith('project_sources/collector/', [System.StringComparison]::Ordinal)) {
    throw "$label output path must stay under project_sources/collector/: $pathValue"
  }
  if (-not $normalized.EndsWith($expectedSuffix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$label output path must end with ${expectedSuffix}: $pathValue"
  }
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
}
