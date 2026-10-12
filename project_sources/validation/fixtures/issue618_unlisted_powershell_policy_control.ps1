# ISSUE618 EVALUATION FIXTURE ONLY. DO NOT EXECUTE OR MERGE.
# This deliberately violates PSScriptAnalyzer policy to prove stale inventory
# can cause a false-green analysis when the Git source preflight is removed.
function Invoke-Issue618PolicyViolationExample {
    param([string]$LiteralCommand)
    Invoke-Expression $LiteralCommand
}
