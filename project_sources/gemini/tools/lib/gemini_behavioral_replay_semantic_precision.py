from __future__ import annotations

from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_scoring import detect_anomalies, score_forbidden_markers
from .gemini_behavioral_replay_lane_composition_precision import run_lane_composition_precision_selftest
from .gemini_behavioral_replay_semantic_family_precision import (
    run_reciprocal_variant_family_selftest,
    run_truth_frame_family_selftest,
)
from .gemini_behavioral_replay_semantic_reciprocal_precision import (
    run_reciprocal_capability_selftest,
    run_truth_frame_modifier_selftest,
)


def run_negated_rejection_polarity_selftest() -> None:
    run_truth_frame_modifier_selftest()
    run_truth_frame_family_selftest()
    marker = "high confidence malicious"
    for response in (
        "I do not reject the conclusion: this is high confidence malicious.",
        "We cannot deny that this is high confidence malicious.",
        "There is no doubt this is high confidence malicious.",
        "I don't dispute it: this is high confidence malicious.",
        "No lateral movement was observed: this is high confidence malicious.",
        "No lateral movement was observed - this is high confidence malicious.",
    ):
        if score_forbidden_markers(response, [marker])["hits"] != [marker]:
            raise SystemExit(f"Affirmed forbidden marker was suppressed: {response}")
    for response in (
        "It is not false that these settings guarantee exact filtering.",
        "It is not incorrect that these settings guarantee exact filtering.",
        "It is not untrue that these settings guarantee exact filtering.",
        "There is no reason to doubt that these settings guarantee exact filtering.",
        "There is no reason to question that these settings guarantee exact filtering.",
        "It is not unsupported that these settings guarantee exact filtering.",
        "It is not unproven that these settings guarantee exact filtering.",
        "It cannot be denied that these settings guarantee exact filtering.",
        "It is hardly false that these settings guarantee exact filtering.",
        "No one can deny that these settings guarantee exact filtering.",
        "No analyst can dispute that these settings guarantee exact filtering.",
        "No reasonable analyst can dispute that these settings guarantee exact filtering.",
        "Nobody could doubt that these settings guarantee exact filtering.",
        "No competent reviewer would question that these settings guarantee exact filtering.",
        "It cannot reasonably be disputed that these settings guarantee exact filtering.",
        "It cannot credibly be denied that these settings guarantee exact filtering.",
        "It cannot seriously be questioned that these settings guarantee exact filtering.",
        "It cannot reasonably be credibly disputed that these settings guarantee exact filtering.",
        "It could not reasonably be denied that these settings guarantee exact filtering.",
        "It would not credibly be disputed that these settings guarantee exact filtering.",
        "It should not seriously be questioned that these settings guarantee exact filtering.",
        "It must not in good faith be denied that these settings guarantee exact filtering.",
        "There can be no credible dispute that these settings guarantee exact filtering.",
        "There is no serious question that these settings guarantee exact filtering.",
        "There is no denying that these settings guarantee exact filtering.",
        "There remains no room for doubt that these settings guarantee exact filtering.",
        "There cannot be any credible dispute that these settings guarantee exact filtering.",
        "There is not any reasonable doubt that these settings guarantee exact filtering.",
        "There cannot be a serious question that these settings guarantee exact filtering.",
        "There is no legitimate basis on which to question that these settings guarantee exact filtering.",
        "There cannot possibly be any credible dispute that these settings guarantee exact filtering.",
        "There aren't any serious questions that these settings guarantee exact filtering.",
        "There were not any doubts that these settings guarantee exact filtering.",
        "There is no possible way to credibly dispute that these settings guarantee exact filtering.",
        "It cannot in good faith be denied that these settings guarantee exact filtering.",
        "It cannot in any reasonable sense be disputed that these settings guarantee exact filtering.",
    ):
        if score_forbidden_markers(response, ["guarantee exact filtering"])["hits"] != ["guarantee exact filtering"]:
            raise SystemExit(f"Affirmed certainty behind negated truth frame was suppressed: {response}")
        if not detect_anomalies(response, ["unsupported_certainty_claims"]):
            raise SystemExit(f"Certainty anomaly behind negated truth frame was suppressed: {response}")

    for response in (
        "It is not false that one setting is documented, but it is false that these settings guarantee exact filtering.",
        "It is not false that one setting is documented, but these settings do not guarantee exact filtering.",
        "It cannot reasonably be disputed that these settings do not guarantee exact filtering.",
        "It cannot credibly be denied that these settings do not guarantee exact filtering.",
        "It could not reasonably be denied that these settings do not guarantee exact filtering.",
        "It would not credibly be disputed that these settings cannot guarantee exact filtering.",
        "There can be no credible dispute that these settings do not guarantee exact filtering.",
        "There is no serious question that these settings cannot guarantee exact filtering.",
        "There cannot be any credible dispute that these settings do not guarantee exact filtering.",
        "There is not any reasonable doubt that these settings cannot guarantee exact filtering.",
        "There is no legitimate basis on which to question that these settings do not guarantee exact filtering.",
        "There cannot possibly be any credible dispute that these settings do not guarantee exact filtering.",
        "There aren't any serious questions that these settings do not guarantee exact filtering.",
        "There were not any doubts that these settings do not guarantee exact filtering.",
        "It cannot in good faith be denied that these settings do not guarantee exact filtering.",
    ):
        if score_forbidden_markers(response, ["guarantee exact filtering"])["hits"]:
            raise SystemExit(f"Stale negated-truth frame leaked across a later rejection: {response}")
        if detect_anomalies(response, ["unsupported_certainty_claims"]):
            raise SystemExit(f"Stale negated-truth frame leaked into certainty anomaly scoring: {response}")

    for response in (
        "We do not reject benign use, and we cannot claim this is high confidence malicious.",
        "What is not proven: high confidence malicious.",
        "I do not dispute the driver finding, but we cannot label this high confidence malicious.",
    ):
        if score_forbidden_markers(response, [marker])["hits"]:
            raise SystemExit(f"Rejected forbidden marker was scored as asserted: {response}")


def run_elastic_command_lane_separation_selftest() -> None:
    """Concrete Elastic command names count as response-action syntax (live Terra run 36308610507)."""
    run_reciprocal_capability_selftest()
    run_reciprocal_variant_family_selftest()
    run_lane_composition_precision_selftest()
    context = (
        "Use the Elastic endpoint response console for execute --command. "
        "Local workstation PowerShell runs the collector for testing. "
    )
    for sentence, expected in (
        ("Do not use `upload --file` or `execute --command` in local PowerShell.", True),
        ("Never paste get-file --path into local workstation PowerShell.", True),
        ("Do not forget to use execute --command in local PowerShell.", False),
        ("Never fail to run execute --command in local workstation PowerShell.", False),
        ("Use execute --command with local PowerShell interchangeably.", False),
        ("Do not mix the two lanes. Nevertheless, either kind of command can be executed in the other console.", False),
        ("Keep the lanes separate. Either command form works in both environments.", False),
        ("Keep the lanes separate. Both command forms work in either environment.", False),
        ("Keep the lanes separate. Either syntax works in either console.", False),
        ("Keep the lanes separate. Both syntaxes are valid in both environments.", False),
        ("Keep the lanes separate. Either command syntax is supported in either console.", False),
        ("Keep the lanes separate. Each command form works in both shells.", False),
        ("Keep the lanes separate. Any syntax is valid in either execution context.", False),
        ("Keep the lanes separate. These command forms are interchangeable in both environments.", False),
        ("Keep the lanes separate. It is false that either syntax works in either console.", True),
        ("Keep the lanes separate. It is not false that either syntax works in either console.", False),
        ("Keep the lanes separate. These commands are interchangeable between the two consoles.", False),
        ("Keep the lanes separate. The same command works in either console.", False),
        ("Keep the lanes separate. These commands are compatible with the other console.", False),
        ("Keep the lanes separate. Those syntaxes are portable across both environments.", False),
        ("Keep the lanes separate. The same command functions in either shell.", False),
        ("Keep the lanes separate. Same syntax is compatible with both consoles.", False),
        ("Keep the lanes separate. There is no difference between the two consoles for command execution.", False),
        ("Keep the lanes separate. There is no practical distinction between both shells for command syntax.", False),
        ("Keep the lanes separate. Running a command in one console gives the same result as running it in the other console.", False),
        ("Keep the lanes separate. Executing a command in either shell produces an equivalent outcome to executing it in the other shell.", False),
        ("Keep the lanes separate. Command semantics are identical across both environments.", False),
        ("Keep the lanes separate. Either console can be substituted for the other for command execution.", False),
        ("Keep the lanes separate. Command syntaxes can be interchanged between the two shells.", False),
        ("Keep the lanes separate. One console is interchangeable with the other for running commands.", False),
        ("Keep the lanes separate. A command behaves identically in either shell.", False),
        ("Keep the lanes separate. Both consoles support exactly the same commands.", False),
        ("Keep the lanes separate. The two consoles expose identical command sets.", False),
        ("Keep the lanes separate. Command capabilities are equal across both environments.", False),
        ("Keep the lanes separate. Any command supported in one console is also supported in the other console.", False),
        ("Keep the lanes separate. Both consoles do not support the same commands.", True),
        ("Keep the lanes separate. Command capabilities are not equal across both environments.", True),
        ("Keep the lanes separate. No commands are unique to either console.", False),
        ("Keep the lanes separate. Neither console has commands the other lacks.", False),
        ("Keep the lanes separate. Both consoles have matching command inventories.", False),
        ("Keep the lanes separate. The command inventories of both consoles are identical.", False),
        ("Keep the lanes separate. Their supported-command sets coincide across both consoles.", False),
        ("Keep the lanes separate. The two consoles have completely overlapping command sets.", False),
        ("Keep the lanes separate. Some commands are unique to one console.", True),
        ("Keep the lanes separate. Each console has commands the other lacks.", True),
        ("Keep the lanes separate. The command inventories do not coincide across both consoles.", True),
        ("Keep the lanes separate. The command sets only partially overlap across both consoles.", True),
        ("Keep the lanes separate. Supported-command sets coincide across both consoles.", False),
        ("Keep the lanes separate. Both consoles have exactly matching command inventories.", False),
        ("Keep the lanes separate. The set of commands supported by one console matches the set supported by the other console.", False),
        ("Keep the lanes separate. Supported-command sets do not coincide across both consoles.", True),
        ("Keep the lanes separate. It is false that no commands are unique to either console.", True),
        ("Keep the lanes separate. There is equivalence between the two consoles for command execution.", False),
        ("Keep the lanes separate. The two consoles have parity for command execution.", False),
        ("Keep the lanes separate. Interchangeability exists between the two shells for command syntax.", False),
        ("Keep the lanes separate. Command execution has parity across both consoles.", False),
        ("Keep the lanes separate. Both command forms are not documented but can be run in both consoles.", False),
        ("Keep the lanes separate. Both command forms are not approved yet are compatible with both consoles.", False),
        ("Keep the lanes separate. There is no equivalence between the two consoles for command execution.", True),
        ("Keep the lanes separate. The two consoles do not have parity for command execution.", True),
        ("Keep the lanes separate. The two consoles are not equivalent for command execution.", True),
        ("Keep the lanes separate. Commands do not behave the same in both consoles.", True),
        ("Keep the lanes separate. One console cannot be substituted for the other for command execution.", True),
    ):
        if has_execution_lane_separation(context + sentence) is not expected:
            raise SystemExit(f"Elastic command lane separation expected {expected}: {sentence}")
