from __future__ import annotations

SCENARIOS = {
    'GeminiCollectorArtifactInterpretation': {
        'description': 'The stored Gemini source should explicitly acknowledge collector artifact interpretation, upload summary driven review, and narrower artifact-first upload behavior.',
        'all_markers': ['collector artifact', 'upload summary'],
        'any_marker_groups': [
            ['attachment budget manifest', 'collection scope', 'targeted collection plan', 'representative final_artifacts'],
        ],
    },
    'GeminiConclusionStageReportOffer': {
        'description': 'The stored Gemini source should offer conclusion-stage report exports only after a supported final conclusion, preserve the executive-summary report option, and keep the compact export plain-text and optional.',
        'all_markers': [
            'offer report output only after the conclusion is supported',
            'executive-summary style final report',
            'compact plain-text conclusion summary',
            'do not auto-generate either export unless the analyst asks for it',
        ],
        'any_marker_groups': [
            ['attachment or printing', 'operator-facing reuse'],
            ['concluded benign, malicious, or unresolved final conclusion', 'singular next-query lane is still active', 'investigation is still active'],
        ],
    },
    'GeminiEvidenceDecodingSupport': {
        'description': 'The stored Gemini source should support bounded decoding of relevant encoded alert content while preserving provenance and distinguishing transformed context from execution proof.',
        'all_markers': [
            'relevant base64 or similar encoded content',
            'preserve the original value',
            'label the decoded content as a transformed view',
            'do not auto-decode when the content is ambiguous',
            'treat decoded content as additional context, not proof',
        ],
        'any_marker_groups': [
            ['decode it', 'decoding fails or is incomplete'],
            ['ask first', 'require non-obvious transformation choices', 'materially widen scope'],
            ['base64-decoded command line', 'decoded script fragment', 'decoded configuration block'],
        ],
    },
    'GeminiIOCEnrichmentTrigger': {
        'description': 'The stored Gemini source should make mixed-format IOC intake and downstream tool routing explicit.',
        'all_markers': ['ioc', 'csv', 'pdf', 'docx'],
        'any_marker_groups': [
            ['kql', 'es/ql', 'osquery', 'response action', 'collector action'],
        ],
    },
    'GeminiOutputContractConsistency': {
        'description': 'The stored Gemini source should preserve the singular triage command contract and avoid vague filler or non-contract drift.',
        'all_markers': ['singular triage command'],
        'any_marker_groups': [
            ['starter prompt 1', 'starter prompt 2', 'starter prompt 3'],
            ['operator', 'analyst'],
        ],
    },
    'GeminiCollectorCommandContractGrounding': {
        'description': 'The stored Gemini source should anchor collector command guidance to governed source evidence, preserve the canonical runtime filename, and block fabricated wrappers, switches, and overclaimed targeted semantics.',
        'all_markers': [
            'anchor exact script name, quick alias, switch set, and parameter model to governed collector source or governed collector knowledge',
            'canonical runtime filename dcoir_collector.ps1',
            'do not invent wrappers such as invoke-dcoir',
            'do not invent unsupported switches such as -artifacts',
            'do not claim that -targeted or windowstart/windowend guarantee exact filtering semantics',
        ],
        'any_marker_groups': [
            ['endpoint response-console syntax versus local powershell syntax', 'do not mix endpoint and local command lanes'],
            ['if the current repo evidence for the collector contract has not been read back', 'if exact collector contract support is uncertain, return the source-readback gap'],
        ],
    },
    'GeminiCollectorOperatorGuidanceStateFirst': {
        'description': 'The stored Gemini source should keep collector and recovery guidance state-first, lane-correct, and evidence-bounded during failed runs, local follow-up, and large-artifact recovery.',
        'all_markers': [
            'anchor the next move to observed workflow state before recommending wait, kill, rerun, restage, cleanup, or upload instructions',
            'do not guess cmdlet parameters, recursion flags, or object pipelines from memory',
            'do not treat uniqueness, a vulnerable version, or missing log hits as proof of malicious staging or active exploitation by themselves',
        ],
        'any_marker_groups': [
            ['state that state gap instead of guessing', 'return that state gap instead of guessing'],
            ['explicit completion marker such as chunks complete', 'chunks complete'],
            ['do not request another chunk unless the operator explicitly says more chunks remain', 'ask for the smallest recovery artifact instead of pretending the workflow continued intact'],
            ['retention', 'filter scope', 'collector scope', 'log rollover', 'extraction limits'],
        ],
    },
    'GeminiOutputLeakageAndDuplicateSuppression': {
        'description': 'The stored Gemini source should explicitly block malformed preamble text, internal state leakage, duplicate final sections, and alternate draft spillover.',
        'all_markers': [
            'malformed preamble',
            'duplicate final sections',
            'routing state',
            'exactly one final analyst-facing draft',
        ],
        'any_marker_groups': [
            ['planner payloads', 'hidden diagnostics', 'yaml', 'json'],
            ['alternate drafts', 'repeated near-identical section pairs', 'single clean final response'],
        ],
    },
    'GeminiStagedExecutionAndGroundedBoundary': {
        'description': 'The stored Gemini source should preserve decide-then-execute-then-narrate behavior and bounded grounded-source-family wording.',
        'all_markers': [
            'decide then execute then narrate',
            'progress or planner wording is not proof of execution',
            'uploaded files, connector-backed enterprise retrieval, public web grounding, custom search, or returned runtime tool results',
            'not verified from configured sources',
        ],
        'any_marker_groups': [
            ['requested action', 'planned action', 'executed action', 'returned result'],
            ['connector and indexing limits', 'searchable-text extraction limits', 'file-size or indexing ceilings'],
        ],
    },
    'GeminiNegativeResultEvidenceBounded': {
        'description': 'The stored Gemini source should keep negative-result reasoning evidence-bounded, preserve lane and coverage limits, and block maliciousness escalation from absent corroboration alone.',
        'all_markers': [
            'no result in the reviewed lane',
            'not verified from configured sources',
            'do not convert a miss into proof of stealth, benignity, or maliciousness by itself',
            'do not force benign or malicious from a search miss',
        ],
        'any_marker_groups': [
            ['query shape', 'time range', 'fields', 'source scope', 'limitation'],
            ['field mismatch', 'index pattern mismatch', 'connector and indexing limits', 'searchable-text extraction limits'],
            ['smallest broadening step', 'what additional result would move the case toward benign or malicious'],
        ],
    },
    'GeminiUniqueValueKqlMissBroadening': {
        'description': 'The stored Gemini source should repair exact unique-value KQL misses with one controlled broadening step while preserving bounded zero-result conclusions.',
        'all_markers': [
            'exact unique-value kql',
            'preserve the exact unique value',
            'field-agnostic exact-value kql',
            'one controlled repair step',
            'does not prove absence',
        ],
        'any_marker_groups': [
            ['field mismatch', 'keyword/text mismatch', 'escaping or quoting', 'secondary filter'],
            ['do not infer stealth', 'do not infer absence', 'do not infer benignity', 'do not infer maliciousness'],
            ['broad search spam', 'all-index/all-time search dumps'],
        ],
    },
    'GeminiSecurityProductNegativeControl': {
        'description': 'The stored Gemini source should preserve false-positive-aware handling for benign or dual-use security-product behavior.',
        'all_markers': ['false-positive-aware', 'security product'],
        'any_marker_groups': [
            ['benign', 'false positive', 'uncertainty', 'known benign'],
        ],
    },
    'GeminiRepeatedSessionConsistency': {
        'description': 'The stored Gemini source should preserve session-state awareness and repeatable behavior across repeated runs.',
        'all_markers': ['session', 'operator', 'analyst'],
        'any_marker_groups': [
            ['state', 'current', 'resume', 'repeatable', 'continuity'],
        ],
    },
    'GeminiUSBViolationsReportComposer': {
        'description': 'The stored Gemini source should preserve the weekly USB violations report workflow, conservative parsing, Stuttgart date-window handling, SNOW-prefix classification, and NIPR/SIPR split output rules.',
        'all_markers': ['usb violations', 'stuttgart', 'last friday', 'this friday', 'snow ticket', 'incn', 'incs', 'nipr', 'sipr', 'on-site', 'off-site/vpn', 'plaintext'],
        'any_marker_groups': [
            ['last week', "last week's"],
            ['weekly usb violations', 'recipient', 'message draft'],
        ],
    },
}
