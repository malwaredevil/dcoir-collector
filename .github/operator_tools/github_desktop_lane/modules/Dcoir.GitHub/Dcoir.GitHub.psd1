@{
    RootModule = 'Dcoir.GitHub.psm1'
    ModuleVersion = '2026.5.1.2'
    GUID = '4fc42d53-969f-4f00-a30e-dc0110000201'
    Author = 'DCOIR'
    CompanyName = 'AFRICOM_SOC_IR'
    Copyright = '(c) DCOIR'
    Description = 'Reusable DCOIR GitHub CLI and Actions API helpers.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @('Set-DcoirGitHubContext','Invoke-DcoirGhText','Invoke-DcoirGhJson','Test-DcoirGhAvailable','Get-DcoirWorkflowRuns','Get-DcoirRunById','Get-DcoirRunJobs')
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
}
