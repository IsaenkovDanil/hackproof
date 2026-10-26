"""Checks: each verifies one property of a task and explains how to fix a failure."""

from hackproof.checks.base import CheckResult, Verdict, worst
from hackproof.checks.baselines import check_nop_baseline
from hackproof.checks.reference import check_reference_reliability

__all__ = [
    "CheckResult",
    "Verdict",
    "check_nop_baseline",
    "check_reference_reliability",
    "worst",
]
