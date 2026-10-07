"""Responses that mix, negate or only appear to separate the execution lanes: (response, label)."""
from __future__ import annotations

REJECTED_SEPARATION_CASES = (
    (
        'It is wrong to say this is an endpoint response action, not a local PowerShell '
        'command.',
        'rejected direct endpoint-vs-local contrast',
    ),
    (
        'It is wrong to say the Elastic response console is only for endpoint actions. It '
        'is also wrong to say local workstation PowerShell is only for package inspection.',
        'rejected only-for lane wording',
    ),
    (
        'Use a separate log folder, but run endpoint response-action commands and local '
        'PowerShell in the same shell.',
        'unrelated separate wording with explicit lane mixing',
    ),
    (
        'Keep package staging separate from evidence retrieval. Endpoint response-action '
        'execution uses execute --command. Local workstation PowerShell runs the collector.',
        'unrelated separation wording',
    ),
    (
        'Use a different lane for log uploads while endpoint response-action commands use '
        'execute --command and local workstation PowerShell runs the collector.',
        'unrelated different-lane wording cannot satisfy execution-lane separation',
    ),
    (
        'Use a distinct lane for log uploads while endpoint response-action commands use '
        'execute --command and local workstation PowerShell runs the collector.',
        'unrelated distinct-lane wording cannot satisfy execution-lane separation',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. "Keep these two lanes separate."',
        'quoted separation assertion',
    ),
    (
        'It is wrong to say do not mix endpoint response-action syntax and local '
        'workstation PowerShell.',
        'rejected no-mix assertion',
    ),
    (
        'It is wrong to say endpoint response-action commands are separate from local '
        'workstation PowerShell.',
        'rejected separation assertion',
    ),
    (
        'It would be misleading to say endpoint response-action commands are separate from '
        'local workstation PowerShell.',
        'misleading separation assertion',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as anything except '
        'local PowerShell commands.',
        'exclusion operator cannot be skipped before local lane head',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as anything other '
        'than local PowerShell commands.',
        'other-than exclusion cannot be skipped before local lane head',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as anything besides '
        'local PowerShell commands.',
        'besides exclusion cannot be skipped before local lane head',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as anything aside '
        'from local PowerShell commands.',
        'aside-from exclusion cannot be skipped before local lane head',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as anything near '
        'local PowerShell commands.',
        'preposition cannot be skipped before local lane head',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as anything barring '
        'local PowerShell commands.',
        'barring exclusion cannot be skipped before local lane head',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as my local '
        'response-action tooling and PowerShell commands.',
        'possessive target cannot hide endpoint contamination',
    ),
    (
        'Do not run endpoint response-action commands in the same shell, and local '
        'workstation PowerShell runs the collector directly.',
        'unbound trailing lane does not imply separation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as usual, and local '
        'workstation PowerShell runs the collector directly.',
        'coordinated clause cannot satisfy trailing lane relation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as usual and local '
        'workstation PowerShell runs the collector directly.',
        'non-lane immediate target cannot borrow a later lane',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as local '
        'response-action tooling and PowerShell commands.',
        'local target cannot borrow a later endpoint marker',
    ),
    (
        'Do not delete logs, but run endpoint response-action commands and local PowerShell '
        'in the same shell. Keep these two lanes separate.',
        'unrelated negation cannot hide explicit lane mixing',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Keep these two lanes separate. Then mix these two '
        'lanes.',
        'referential lane-mix contradiction',
    ),
    (
        'Use a separate log folder, but combine endpoint response-action commands with '
        'local PowerShell.',
        'direct targeted lane mixing',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Run these two lanes in the same shell, but keep the '
        'log folders separate.',
        'referential shared-shell mix cannot be masked by unrelated separation',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Run them in the same shell. Keep these two lanes '
        'separate.',
        'pronominal shared-shell mix after lane establishment',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. These two lanes use dedicated identifiers and the '
        'log folders are separate.',
        'unrelated referential separation wording',
    ),
    (
        'It is misleading to say do not mix endpoint response-action syntax and local '
        'workstation PowerShell.',
        'misleading no-mix rejection',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Do not run them separately, run them in the same '
        'shell. Keep these two lanes separate.',
        'nearest pronominal action governs shared-context mix verdict',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Keep these two lanes separate. It is not wrong to '
        'mix these two lanes.',
        'negated repudiation still exposes an asserted lane mix',
    ),
    (
        'It is wrong to say do not run endpoint response-action commands and local '
        'workstation PowerShell in the same shell.',
        'rejected shared-shell prohibition',
    ),
    (
        'Do not mix the log files while endpoint response-action commands use execute '
        '--command and local workstation PowerShell runs the collector.',
        'unrelated no-mix target cannot borrow later lane context',
    ),
    (
        'Do not mix endpoint log files with archive files while endpoint response-action '
        'commands use execute --command and local workstation PowerShell runs the '
        'collector.',
        'one-sided endpoint no-mix target cannot borrow later local context',
    ),
    (
        'Use execute --command for endpoint response actions and run the local collector in '
        'Windows PowerShell and do not mix log formats.',
        'stated trailing no-mix object governs over unrelated leading lane context',
    ),
    (
        'Use execute --command for endpoint response actions and run the local collector in '
        'Windows PowerShell and do not mix log formats at all.',
        'stated trailing object remains authoritative even with a trailing adverbial',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix with '
        'archive files.',
        'with-object complement cannot borrow the leading lane relationship',
    ),
)
