@{
    RootModule = 'Dcoir.Snapshot.psm1'
    ModuleVersion = '2026.5.1.1'
    GUID = '8fc42d53-969f-4f00-a30e-dc0110000301'
    Author = 'DCOIR'
    CompanyName = 'AFRICOM_SOC_IR'
    Copyright = '(c) DCOIR'
    Description = 'Reusable DCOIR snapshot helpers for repo-relative path safety, text-file filtering, staging, and UTF-8 logging.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @('Add-DcoirSnapshotUtf8Line','ConvertTo-DcoirSnapshotSafeName','Assert-DcoirRepoRelativePath','Test-DcoirPathUnderRoot','Get-DcoirRepoRelativePath','Test-DcoirLikelyBinaryFile','Copy-DcoirSnapshotRepoPath','Get-DcoirTextSnapshotFiles')
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}
