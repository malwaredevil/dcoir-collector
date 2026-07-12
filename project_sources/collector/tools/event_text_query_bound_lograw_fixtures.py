#!/usr/bin/env python3
"""LogRaw metadata-truth fixture cases for runtime validation."""
from __future__ import annotations

negative_param_fixture_source = '''
function Export-FilteredEvtx {
  [CmdletBinding()]
  param(
    [string]$LogChannel,
    [int]$MaxEvents
  )
}
'''

target_detail_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -Take 500',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -Take $Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -MaxEvents $Limit',
]
target_detail_multiline_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId `\n  -Take $Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId `\r\n  -MaxEvents $Limit',
]
target_detail_parameter_prefix_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -T 500',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -Ta 500',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -Max $Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -MaxE $Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId `\n  -Ta $Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId `\r\n  -Max $Limit',
]
target_detail_colon_parameter_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Take:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -T:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Ta:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -tAkE:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -MaxEvents:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -M:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Ma:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Max:$Limit',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -MaxE:$Limit',
]
target_detail_implicit_continuation_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails -LogName $LogName -Ids @(\n  $EventId\n) -Take $Limit',
    'Get-CollectorEventWindowTargetDetails -LogName (\n  $LogName\n) -MaxEvents $Limit',
    'Get-CollectorEventWindowTargetDetails -Metadata @{\n  LogName = $LogName\n} -Ta $Limit',
]
target_detail_implicit_continuation_benign_fixtures = [
    'Get-CollectorEventWindowTargetDetails -Ids @(\n  $EventId\n) -Note "-Take @TargetDetailArgs"',
    'Get-CollectorEventWindowTargetDetails -Metadata @{\n  LogName = $LogName # -MaxEvents @script:TargetDetailArgs\n} -Hours $Hours',
]
target_detail_splat_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails @TargetDetailArgs',
    'Get-CollectorEventWindowTargetDetails -LogName $LogName `\n  @TargetDetailArgs',
]
target_detail_implicit_continuation_splat_negative_fixtures = [
    'Get-CollectorEventWindowTargetDetails -Ids @(\n  $EventId\n) @TargetDetailArgs',
    'Get-CollectorEventWindowTargetDetails -Metadata @{\n  LogName = $LogName\n} @script:TargetDetailArgs',
]
export_splat_negative_fixtures = [
    'Export-FilteredEvtx @ExportArgs',
    'Export-FilteredEvtx -LogChannel $LogName `\n  @ExportArgs',
]
export_implicit_continuation_negative_fixtures = [
    'Export-FilteredEvtx -LogChannel $LogName -Ids @(\n  $EventId\n) -MaxEvents $MaxEvents',
    'Export-FilteredEvtx -LogChannel (\n  $LogName\n) -Max $MaxEvents',
    'Export-FilteredEvtx -Options @{\n  LogName = $LogName\n} -Ta $Limit',
]
export_colon_parameter_negative_fixtures = [
    'Export-FilteredEvtx -LogChannel $LogName -Take:$Limit',
    'Export-FilteredEvtx -LogChannel $LogName -T:$Limit',
    'Export-FilteredEvtx -LogChannel $LogName -Ta:$Limit',
    'Export-FilteredEvtx -LogChannel $LogName -tAkE:$Limit',
    'Export-FilteredEvtx -LogChannel $LogName -MaxEvents:$MaxEvents',
    'Export-FilteredEvtx -LogChannel $LogName -M:$MaxEvents',
    'Export-FilteredEvtx -LogChannel $LogName -Ma:$MaxEvents',
    'Export-FilteredEvtx -LogChannel $LogName -Max:$MaxEvents',
    'Export-FilteredEvtx -LogChannel $LogName -mAxE:$MaxEvents',
]
export_implicit_continuation_benign_fixtures = [
    'Export-FilteredEvtx -Ids @(\n  $EventId\n) -Note "-MaxEvents @ExportArgs"',
    'Export-FilteredEvtx -Options @{\n  LogName = $LogName # -Take @script:ExportArgs\n} -OutPath $Path',
]
export_implicit_continuation_splat_negative_fixtures = [
    'Export-FilteredEvtx -Ids @(\n  $EventId\n) @ExportArgs',
    'Export-FilteredEvtx -Options @{\n  LogName = $LogName\n} @script:ExportArgs',
]
command_anchor_benign_fixtures = [
    ('# Export-FilteredEvtx -MaxEvents $MaxEvents @ExportArgs\n', 'Export-FilteredEvtx'),
    ('$note = "Export-FilteredEvtx -MaxEvents $MaxEvents @ExportArgs"\n', 'Export-FilteredEvtx'),
    ("Write-Output 'Get-CollectorEventWindowTargetDetails -Take 500 @TargetDetailArgs'\n", 'Get-CollectorEventWindowTargetDetails'),
    ('<#\nExport-FilteredEvtx -MaxEvents $MaxEvents @ExportArgs\n#>\n', 'Export-FilteredEvtx'),
    ('<#\nGet-CollectorEventWindowTargetDetails -Take 500 @TargetDetailArgs\n#>\n', 'Get-CollectorEventWindowTargetDetails'),
    ('$note = @"\nExport-FilteredEvtx -MaxEvents $MaxEvents @ExportArgs\n"@\n', 'Export-FilteredEvtx'),
    ("$note = @'\nGet-CollectorEventWindowTargetDetails -Take 500 @TargetDetailArgs\n'@\n", 'Get-CollectorEventWindowTargetDetails'),
]
command_separator_benign_fixtures = [
    ('Get-CollectorEventWindowTargetDetails -LogName $LogName; Write-Output -MaxEvents 5 @Args\n', 'Get-CollectorEventWindowTargetDetails'),
    ('Get-CollectorEventWindowTargetDetails -LogName $LogName | Select-Object -First 1 -MaxEvents 5 @Args\n', 'Get-CollectorEventWindowTargetDetails'),
    ('Export-FilteredEvtx -LogChannel $LogName; Write-Output -MaxEvents $MaxEvents @ExportArgs\n', 'Export-FilteredEvtx'),
    ('Export-FilteredEvtx -LogChannel $LogName | Select-Object -First 1 -MaxEvents $MaxEvents @ExportArgs\n', 'Export-FilteredEvtx'),
]
command_case_negative_fixtures = [
    ('export-filteredevtx -maxevents:$MaxEvents', 'Export-FilteredEvtx'),
    ('GET-COLLECTOREVENTWINDOWTARGETDETAILS -tAkE:$Limit', 'Get-CollectorEventWindowTargetDetails'),
]
