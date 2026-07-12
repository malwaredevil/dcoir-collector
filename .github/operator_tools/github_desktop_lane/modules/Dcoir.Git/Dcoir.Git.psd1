@{
    RootModule = 'Dcoir.Git.psm1'
    ModuleVersion = '2026.5.1.2'
    GUID = '8fc42d53-969f-4f00-a30e-dc0110000201'
    Author = 'DCOIR'
    CompanyName = 'AFRICOM_SOC_IR'
    Copyright = '(c) DCOIR'
    Description = 'Reusable DCOIR git process and repository state helpers.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @('Add-DcoirGitUtf8Line','Test-DcoirGitPlaceholderPath','Get-DcoirGitSystemEnvValue','ConvertTo-DcoirNativeArgumentString','Resolve-DcoirGitExe','Invoke-DcoirGitCommand','Invoke-DcoirGitLogged','Get-DcoirGitCurrentBranch','Assert-DcoirGitBranch','Get-DcoirGitStatusPorcelain','Assert-DcoirGitCleanTree','Invoke-DcoirGitFetch','Invoke-DcoirGitFastForwardPull','Get-DcoirGitAheadBehind')
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}
