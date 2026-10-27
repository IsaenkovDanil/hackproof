"""P5: the reference solution must pass every time.

Runs the oracle agent sequentially and feeds each graded outcome to Wald's SPRT
(H0: failure rate 1%, H1: failure rate 10%, alpha = beta = 5%), stopping as soon as the
evidence is decisive. A broken reference therefore costs about two runs, a healthy one 31.

The reported interval for the failure rate is exact for this stopping rule
(`stats.sequential_interval`); a fixed-n interval would overstate its coverage after an early
stop. Runs that produce no valid grade are kept out of the failure count but always reported,
and they keep the verdict from being OK: a verifier that crashes on the reference solution is
itself a reliability problem. The interval assumes such runs are unrelated to the outcome.
"""

from __future__ import annotations

from hackproof.checks.base import CheckResult, Verdict, run_record
from hackproof.model import Task
from hackproof.runners.base import ORACLE, Runner
from hackproof.stats import BernoulliSPRT, Decision, SequentialDesign, sequential_interval

CHECK_ID = "reference.reliability"
P0, P1 = 0.01, 0.10
# Give up when the environment itself keeps failing; more runs would not grade anything.
MAX_INVALID_BEFORE_FIRST_GRADE = 3
CI_METHOD = "exact for the SPRT stopping rule (Clopper-Pearson-type inversion, rate ordering)"


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
    results = []
    for attempt in range(max_runs):
        result = runner.run(task, ORACLE, attempt=attempt)
        results.append(result)
        if not result.counted:
            if sprt.n == 0 and len(results) >= MAX_INVALID_BEFORE_FIRST_GRADE:
                break
            continue
        if sprt.update(result.reward < 1.0) is not Decision.CONTINUE:
            break

    rewards = [r.reward for r in results if r.counted]
    errors = [r.error for r in results if not r.counted]
    graded, failures, invalid = sprt.n, sprt.events, len(errors)
    evidence = {
        "max_runs": max_runs,
        "attempts": len(results),
        "graded_runs": graded,
        "invalid_runs": invalid,
        "failures": failures,
        "rewards": rewards,
        "errors": errors,
        "runs": [run_record(r) for r in results],
        "sprt": {
            "p0": P0,
            "p1": P1,
            "alpha": sprt.alpha,
            "beta": sprt.beta,
            "decision": sprt.decision.value,
        },
    }

    if graded == 0:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.UNKNOWN,
            summary=f"no reference run produced a valid reward ({invalid} errors)",
            evidence=evidence,
            fix="Make the environment build and the verifier run before auditing further.",
            incomplete=True,
        )

    # Invalid attempts used up part of the budget, so the design could grade at most this many.
    graded_budget = max_runs - invalid
    low, high = sequential_interval(SequentialDesign(sprt, graded_budget), graded, failures)
    evidence["failure_rate_ci95"] = [round(low, 4), round(high, 4)]
    evidence["ci_method"] = CI_METHOD
    counts = f"{graded} graded" + (f", {invalid} without a valid grade" if invalid else "")

    if failures == graded:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.FAIL,
            summary=f"the reference solution failed in all graded runs ({counts})",
            evidence=evidence,
            fix=(
                "Fix the reference solution or its environment. Pin dependency versions so "
                "the reference keeps passing as upstream packages change."
            ),
        )
    if failures:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.WARN,
            summary=(
                f"the reference solution is flaky: failed {failures} of {graded} graded runs, "
                f"failure rate 95% CI {low:.1%}–{high:.1%} ({counts})"
            ),
            evidence=evidence,
            fix=(
                "Find the source of nondeterminism: tight timeouts, unseeded randomness, "
                "network calls, test ordering or wall-clock time."
            ),
        )
    if invalid:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.WARN,
            summary=(
                f"the reference solution passed every graded run, but {invalid} of "
                f"{len(results)} attempts produced no valid grade ({counts})"
            ),
            evidence=evidence,
            fix=(
                "A verifier that errors, times out or writes no reward on the reference "
                "solution makes rewards unreliable. Check the errors listed in the evidence."
            ),
        )
    if sprt.decision is Decision.ACCEPT_H0:
        return CheckResult(
            id=CHECK_ID,
            property="P5",
            verdict=Verdict.OK,
            summary=(
                f"the reference solution passed all {graded} runs; SPRT rules out a failure "
                f"rate of {P1:.0%} or more (alpha = beta = 5%), 95% CI 0–{high:.1%}"
            ),
            evidence=evidence,
        )
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
