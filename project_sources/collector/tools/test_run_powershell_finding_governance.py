#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from powershell_finding_governance_test_classification import FindingGovernanceClassificationTestsMixin
from powershell_finding_governance_test_sources import FindingGovernanceSourceTestsMixin
from powershell_finding_governance_test_support import (
    FindingGovernanceTestBase,
    baseline_record,
    finding,
    governance,
    suppression_record,
    write,
)


class PowerShellFindingGovernanceTests(
    FindingGovernanceSourceTestsMixin,
    FindingGovernanceClassificationTestsMixin,
    FindingGovernanceTestBase,
):
    pass


if __name__ == "__main__":
    raise SystemExit(unittest.main())
