@{
    RootModule = 'Dcoir.RepoPatch.psm1'
    ModuleVersion = '2026.5.1.2'
    GUID = '8fc42d53-969f-4f00-a30e-dc0110000401'
    Author = 'DCOIR'
    CompanyName = 'AFRICOM_SOC_IR'
    Copyright = '(c) DCOIR'
    Description = 'Reusable DCOIR repo patch helpers for safe paths, payload-root resolution, allowed roots, hashing, and UTF-8 logging.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @('Add-DcoirRepoPatchUtf8Line','Test-DcoirRepoPatchRelativePathSafe','ConvertTo-DcoirRepoPatchRelativePath','Get-DcoirRepoPatchTrimmedRoot','Resolve-DcoirRepoPatchUnderRoot','Get-DcoirRepoPatchFileSha256','Test-DcoirRepoPatchAllowedTargetRoot','Find-DcoirRepoPatchPayloadBase')
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}
