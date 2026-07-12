<#
.SYNOPSIS
Compatibility marker for the split DCOIR collector baseline collection and reporting part.

.DESCRIPTION
The former monolithic DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1 source was split into DCOIR_Collector.02A through 02D for connector-sized maintenance. Runtime assembly is owned by DCOIR_Collector.ps1 and Collector_Runtime_Package_Manifest.json, which load the 02A, 02B, 02C, and 02D parts in order.

.FILE NAME
DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1
#>
# Compatibility locator only. Do not load this file in the collector runtime package.
# Runtime order:
# - DCOIR_Collector.02A_Baseline_Collection_And_Reports.ps1
# - DCOIR_Collector.02B_Baseline_Collection_And_Reports.ps1
# - DCOIR_Collector.02C_Baseline_Collection_And_Reports.ps1
# - DCOIR_Collector.02D_Baseline_Collection_And_Reports.ps1
