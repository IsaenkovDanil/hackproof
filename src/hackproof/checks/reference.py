"""P5: the reference solution must pass every time.

Runs the oracle agent sequentially and feeds each outcome to Wald's SPRT
(H0: failure rate 1%, H1: failure rate 10%, alpha = beta = 5%), stopping as soon as the
evidence is decisive. A broken reference therefore costs about two runs, a healthy one 31.
"""

from __future__ import annotations

from hackproof.checks.base import CheckResult, Verdict
from hackproof.model import Task
from hackproof.runners.base import ORACLE, Runner
from hackproof.stats import BernoulliSPRT, Decision, wilson_interval

CHECK_ID = "reference.reliability"
P0, P1 = 0.01, 0.10
# Give up when the environment itself keeps failing; more runs would not grade anything.
MAX_INVALID_BEFORE_FIRST_GRADE = 3


def check_reference_reliability(task: Task, runner: Runner, *, max_runs: int = 31) -> CheckResult:
    if max_runs < 1:
        raise ValueError("max_runs must be >= 1")
    if not task.has_solution:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.UNKNOWN,
            summary="the task has no reference solution to run",
            fix="Ship a reference solution so the task can be shown to be solvable.",
        )

    sprt = BernoulliSPRT(p0=P0, p1=P1)
    rewards: list[float] = []
    errors: list[str | None] = []
    for attempt in range(max_runs):
        result = runner.run(task, ORACLE, attempt=attempt)
        if not result.counted:
            errors.append(result.error)
            if not rewards and len(errors) >= MAX_INVALID_BEFORE_FIRST_GRADE:
                break
            continue
        rewards.append(result.reward)
        if sprt.update(result.reward < 1.0) is not Decision.CONTINUE:
            break

    graded = len(rewards)
    failures = sum(r < 1.0 for r in rewards)
    evidence = {
        "max_runs": max_runs,
        "graded_runs": graded,
        "failures": failures,
        "rewards": rewards,
        "errors": errors,
        "sprt": {
            "p0": P0,
            "p1": P1,
            "alpha": sprt.alpha,
            "beta": sprt.beta,
            "decision": sprt.decision.value,
        },
    }
    if graded:
        low, high = wilson_interval(failures, graded)
        evidence["failure_rate_ci95"] = [round(low, 4), round(high, 4)]

    if graded == 0:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.UNKNOWN,
            summary=f"no reference run produced a valid reward ({len(errors)} errors)",
            evidence=evidence,
            fix="Make the environment build and the verifier run before auditing further.",
        )
    if failures == graded:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.FAIL,
            summary=f"the reference solution failed in all {graded} graded runs",
            evidence=evidence,
            fix=(
                "Fix the reference solution or its environment. Pin dependency versions so "
                "the reference keeps passing as upstream packages change."
            ),
        )
    if failures:
        low, high = evidence["failure_rate_ci95"]
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.WARN,
            summary=(
                f"the reference solution is flaky: failed {failures} of {graded} runs "
                f"(failure rate 95% CI {low:.1%}–{high:.1%})"
            ),
            evidence=evidence,
            fix=(
                "Find the source of nondeterminism: tight timeouts, unseeded randomness, "
                "network calls, test ordering or wall-clock time."
            ),
        )
    if sprt.decision is Decision.ACCEPT_H0:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.OK,
            summary=(
                f"the reference solution passed all {graded} runs; SPRT rules out a failure "
                f"rate of {P1:.0%} or more (alpha = beta = 5%)"
            ),
            evidence=evidence,
        )
    _, high = evidence["failure_rate_ci95"]
    return CheckResult(
        id=CHECK_ID,
        property="P5",
        verdict=Verdict.UNKNOWN,
        summary=(
            f"the reference solution passed all {graded} runs, too few to bound its failure "
            f"rate (95% upper bound {high:.1%}); 31 clean runs give a decision"
        ),
        evidence=evidence,
    )
