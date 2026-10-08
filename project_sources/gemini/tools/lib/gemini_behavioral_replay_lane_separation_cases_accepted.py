"""Responses that state real endpoint/local execution-lane separation: (response, label)."""
from __future__ import annotations

ACCEPTED_SEPARATION_CASES = (
    (
        'Endpoint response-action execution uses execute --command for remote actions. '
        'Local workstation PowerShell runs the collector directly. Keep these two lanes '
        'separate.',
        'response-scope referential separation',
    ),
    (
        'Keep endpoint response-action syntax separate from local workstation PowerShell.',
        'same-clause relational separation',
    ),
    (
        'This is an endpoint response action, not a local PowerShell command.',
        'direct endpoint-vs-local contrast',
    ),
    (
        'Use the Elastic response console only for endpoint actions. Use local workstation '
        'PowerShell only for package inspection, testing, or local harness validation. Do '
        'not paste Elastic execute syntax into local PowerShell, and do not paste bare '
        'PowerShell commands into the endpoint response console.',
        'mutually exclusive endpoint-local only-for lanes',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Do not mix these two lanes.',
        'response-scope no-mix relationship',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Do not combine these two lanes.',
        'response-scope no-combine relationship',
    ),
    (
        'Keep endpoint response-action commands in a different lane from local workstation '
        'PowerShell.',
        'different-lane evidence binds directly to the endpoint-local relation',
    ),
    (
        'Do not run endpoint response-action commands and local workstation PowerShell in '
        'the same shell.',
        'negated shared-shell relation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as local '
        'workstation PowerShell.',
        'trailing-lane shared-shell negation',
    ),
    (
        'Avoid using the same shell for endpoint response-action commands and local PowerShell.',
        'avoid-using shared-shell negation',
    ),
    (
        'Do not run local workstation PowerShell in the same shell as endpoint '
        'response-action commands.',
        'trailing-endpoint shared-shell negation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as your local '
        'PowerShell commands.',
        'possessive trailing-local shared-shell negation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as my local '
        'PowerShell commands.',
        'first-person possessive trailing-local shared-shell negation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as her local '
        'PowerShell commands.',
        'third-person possessive trailing-local shared-shell negation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as your own local '
        'PowerShell commands.',
        'possessive-intensifier trailing-local shared-shell negation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as another local '
        'PowerShell command.',
        'unlisted-determiner trailing-local shared-shell negation',
    ),
    (
        'Do not run local workstation PowerShell in the same shell as a dedicated endpoint '
        'response-action console.',
        'adjectival trailing-endpoint shared-shell negation',
    ),
    (
        'Do not run local workstation PowerShell in the same shell as an endpoint '
        'response-action console.',
        'article trailing-endpoint shared-shell negation',
    ),
    (
        'Do not run endpoint response-action commands in the same shell as local tooling '
        'and PowerShell commands.',
        'coordinated local target remains a bound lane relation',
    ),
    (
        'Do not use the same shell for endpoint response-action commands and local PowerShell.',
        'negated shared-shell object relation',
    ),
    (
        'Combine the log files, but keep endpoint response-action commands separate from '
        'local PowerShell.',
        'unrelated combine wording does not imply lane mixing',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Do not run them in the same shell. Keep these two '
        'lanes separate.',
        'negated pronominal shared-shell action does not create lane mixing',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Do not use the same shell for these two lanes.',
        'referential negated shared-shell relation',
    ),
    (
        'Do not run local workstation PowerShell in the same shell as the fully dedicated '
        'remote response action endpoint console.',
        'split response action head at the last scan-window slot',
    ),
    (
        'Although it is misleading to say these tools are interchangeable, do not mix '
        'endpoint response-action syntax and local workstation PowerShell.',
        'comma boundary preserves affirmative no-mix instruction',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Keep them in the same order in your report and '
        'never run them in the same shell. Keep these two lanes separate.',
        'nearer pronominal negation governs shared-context mix verdict',
    ),
    (
        'Although it is misleading to say these tools are interchangeable, keep endpoint '
        'response-action commands separate from local workstation PowerShell.',
        'comma boundary preserves affirmative separate instruction',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Keep these two lanes separate. It is wrong to mix '
        'these two lanes.',
        'repudiated direct mix does not trigger the mix veto',
    ),
    (
        'It is not wrong to say do not run endpoint response-action commands and local '
        'workstation PowerShell in the same shell.',
        'negated rejection preserves the shared-shell prohibition',
    ),
    (
        'It is wrong to say the endpoint response console and local PowerShell are '
        'interchangeable.',
        'rejected equivalence assertion preserves lane separation',
    ),
    (
        'It is wrong to say either the endpoint response console and local PowerShell are '
        'interchangeable, or the endpoint response console and local PowerShell are '
        'interchangeable.',
        'or-coordinated equivalence alternatives remain rejected',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix '
        'together.',
        'subject-position lane no-mix with trailing together remains accepted',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix at all.',
        'subject-position lane no-mix with trailing at-all modifier remains accepted',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix ever.',
        'subject-position lane no-mix accepts an irregular trailing adverb',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix '
        'permanently.',
        'subject-position lane no-mix accepts a morphological trailing adverb',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix '
        'under any circumstances.',
        'subject-position lane no-mix accepts a prepositional circumstance adjunct',
    ),
    (
        'Endpoint response-action syntax and local workstation PowerShell must not mix in '
        'the same session.',
        'subject-position lane no-mix accepts a prepositional session adjunct',
    ),
    (
        'Do not mix endpoint response-action syntax and local workstation PowerShell.',
        'direct endpoint-local no-mix relationship remains accepted',
    ),
    (
        'Endpoint response-action execution uses execute --command. Local workstation '
        'PowerShell runs the collector. Do not mix these two lanes.',
        'referential no-mix relationship remains accepted',
    ),
)
