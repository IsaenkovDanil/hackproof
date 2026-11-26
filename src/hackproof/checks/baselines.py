"""P1: a trivial baseline agent must earn zero reward."""

from __future__ import annotations

from hackproof.checks.base import CheckResult, Verdict, run_record
from hackproof.model import Task
from hackproof.runners.base import NOP, Runner

CHECK_ID = "baseline.nop"


def check_nop_baseline(task: Task, runner: Runner, *, runs: int = 2) -> CheckResult:
    """Run the do-nothing agent `runs` times; any reward above zero fails the check."""
    if runs < 1:
        raise ValueError("runs must be >= 1")
    results = [runner.run(task, NOP, attempt=i) for i in range(runs)]
    counted = [r for r in results if r.counted]
    errors = [r.error for r in results if not r.counted]
    evidence = {
        "runs": [run_record(r) for r in results],
        "rewards": [r.reward for r in counted],
        "errors": errors,
    }

    paying = [r for r in counted if r.reward > 0]
    if paying:
        return CheckResult(
            id=CHECK_ID,
            property="P1",
            verdict=Verdict.FAIL,
            summary=(
                f"a no-op agent earned reward {max(r.reward for r in paying):g} "
                f"in {len(paying)} of {len(counted)} graded runs"
            ),
            evidence=evidence,
            fix=(
                "The grader rewards a state the task already starts in. Make it check the "
                "substance of the result, and add a negative example that must score 0."
            ),
        )
    if not counted:
        return CheckResult(
            id=CHECK_ID,
            property="P1",
            verdict=Verdict.UNKNOWN,
            summary=f"no no-op run produced a valid reward ({len(errors)} errors)",
            evidence=evidence,
            incomplete=True,
        )
    if errors:
        return CheckResult(
            id=CHECK_ID,
            property="P1",
            verdict=Verdict.WARN,
            summary=(
                f"no-op runs scored 0, but the verifier errored in {len(errors)} of {runs} runs"
            ),
            evidence=evidence,
            fix="A grader should return 0 for missing or empty output instead of failing.",
        )
    return CheckResult(
        id=CHECK_ID,
        property="P1",
        verdict=Verdict.OK,
        summary=f"a no-op agent scored 0 in all {runs} runs",
        evidence=evidence,
    )
