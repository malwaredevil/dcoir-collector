@{
    RootModule = 'Dcoir.Common.psm1'
    ModuleVersion = '2026.5.1.1'
    GUID = '4fc42d53-969f-4f00-a30e-dc0110000101'
    Author = 'DCOIR'
    CompanyName = 'AFRICOM_SOC_IR'
    Copyright = '(c) DCOIR'
    Description = 'Reusable DCOIR common helpers for paths, environment, JSON, logging, filesystem, timestamps, and formatting.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @('Set-DcoirToolContext','Get-DcoirToolContext','Get-DcoirContextValue','Set-DcoirContextValue','Test-DcoirPlaceholderPath','Get-DcoirSystemEnvValue','Resolve-DcoirPathText','ConvertTo-DcoirHashtable','Get-DcoirConfigValue','ConvertTo-DcoirSafeName','Write-DcoirUtf8Text','Add-DcoirUtf8Line','Save-DcoirJson','Write-DcoirConsoleStep','Write-DcoirStatus','Write-DcoirPhase','Format-DcoirInputMap')
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}
