import pytest

pytest.importorskip("scipy")
pytest.importorskip("statsmodels")
pytest.importorskip("hypothesis")

import itertools
import json
import math
import random
import statistics
import subprocess
import sys
import time
from importlib.metadata import version

from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.stats import beta as reference_beta
from statsmodels.stats.proportion import proportion_confint

from hackproof.stats import (
    BernoulliSPRT,
    BetaPosterior,
    Decision,
    pass_at_k,
    wilson_interval,
)


@st.composite
def counts(draw):
    n = draw(st.integers(1, 10_000))
    return draw(st.integers(0, n)), n


@settings(max_examples=500, derandomize=True, deadline=None)
@given(counts())
def test_wilson_reference(pair):
    events, n = pair
    assert wilson_interval(events, n) == pytest.approx(
        proportion_confint(events, n, method="wilson"), abs=1e-9, rel=0
    )


@pytest.mark.parametrize("n", [1, 2, 10, 100, 10_000])
@pytest.mark.parametrize("all_events", [False, True])
def test_wilson_edges(n, all_events):
    events = n if all_events else 0
    assert wilson_interval(events, n) == pytest.approx(
        proportion_confint(events, n, method="wilson"), abs=1e-9, rel=0
    )


@settings(max_examples=300, derandomize=True, deadline=None)
@given(st.integers(1, 500), st.integers(1, 500), st.floats(0, 1))
def test_beta_cdf_reference(a, b, x):
    assert BetaPosterior(a, b).cdf(x) == pytest.approx(reference_beta.cdf(x, a, b), abs=1e-9, rel=0)


@settings(max_examples=150, derandomize=True, deadline=None)
@given(st.integers(1, 500), st.integers(1, 500), st.floats(1e-6, 1 - 1e-6))
def test_beta_quantile_reference(a, b, q):
    assert BetaPosterior(a, b).quantile(q) == pytest.approx(
        reference_beta.ppf(q, a, b), abs=2e-9, rel=0
    )


def test_pass_at_k_exhaustive():
    for n in range(1, 11):
        for c in range(n + 1):
            for k in range(1, n + 1):
                subsets = list(itertools.combinations(range(n), k))
                expected = sum(any(i < c for i in s) for s in subsets) / len(subsets)
                assert pass_at_k(n, c, k) == pytest.approx(expected, abs=1e-15, rel=0)


def simulate(p0, p1, truth, seed, repetitions=10_000):
    rng = random.Random(seed)
    sizes, errors = [], 0
    for _ in range(repetitions):
        trial = BernoulliSPRT(p0, p1)
        for _ in range(100_000):
            decision = trial.update(rng.random() < truth)
            if decision is not Decision.CONTINUE:
                break
        else:
            raise AssertionError("SPRT did not terminate; no censored sequences allowed")
        errors += decision is (Decision.ACCEPT_H1 if truth == p0 else Decision.ACCEPT_H0)
        sizes.append(trial.n)
    alpha, beta = 0.05, 0.05
    lower, upper = math.log(beta / (1 - alpha)), math.log((1 - beta) / alpha)
    drift = truth * math.log(p1 / p0) + (1 - truth) * math.log((1 - p1) / (1 - p0))
    wald = (
        ((1 - alpha) * lower + alpha * upper)
        if truth == p0
        else (beta * lower + (1 - beta) * upper)
    ) / drift
    return {
        "p0": p0,
        "p1": p1,
        "truth": truth,
        "seed": seed,
        "errors": errors,
        "repetitions": repetitions,
        "error_rate": errors / repetitions,
        "error_ci95": list(proportion_confint(errors, repetitions, method="wilson")),
        "asn": statistics.mean(sizes),
        "asn_se": statistics.stdev(sizes) / math.sqrt(repetitions),
        "wald_asn": wald,
        "max_n": max(sizes),
    }


@pytest.mark.parametrize("p0,p1", [(0.01, 0.1), (0.4, 0.6), (0.6, 0.4)])
@pytest.mark.parametrize("under_h1", [False, True])
def test_sprt_simulation(p0, p1, under_h1):
    result = simulate(p0, p1, p1 if under_h1 else p0, 6001 + int(under_h1))
    print("SPRT", json.dumps(result))
    # Monte Carlo allowance of four nominal standard errors; Wald bounds are approximate.
    assert result["error_rate"] <= 0.05 + 4 * math.sqrt(0.05 * 0.95 / 10_000)
    # Overshoot can materially increase ASN, especially for rare events.
    assert 0.75 < result["asn"] / result["wald_asn"] < 1.6


def test_beta_quantile_one():
    assert BetaPosterior(1, 500).quantile(1) == 1.0


@pytest.mark.parametrize("a,b", [(1.5, 2), (math.nan, 2), (math.inf, 2)])
def test_beta_rejects_fractional_parameters(a, b):
    with pytest.raises((ValueError, TypeError)):
        BetaPosterior(a, b)


def test_wilson_rejects_negative_z():
    with pytest.raises(ValueError):
        wilson_interval(5, 10, z=-1)


def test_quantile_rejects_infinite_tolerance():
    with pytest.raises(ValueError):
        BetaPosterior(1, 1).quantile(0.5, tol=math.inf)


def test_beta_extreme_upper_tail():
    assert BetaPosterior(500, 500).quantile(1 - 1e-12) == pytest.approx(
        reference_beta.ppf(1 - 1e-12, 500, 500), abs=2e-9, rel=0
    )


def test_beta_quantile_grid_worst_case():
    assert BetaPosterior(429, 425).quantile(0.999999) == pytest.approx(
        reference_beta.ppf(0.999999, 429, 425), abs=2e-9, rel=0
    )


@pytest.mark.parametrize("tol", [0, -1, 1e-30])
def test_quantile_tolerance_terminates(tol):
    code = (
        "from hackproof.stats import BetaPosterior\n"
        "try:\n"
        f"    BetaPosterior(2, 3).quantile(0.5, tol={tol!r})\n"
        "except ValueError:\n"
        "    pass\n"
    )
    # A valid small tolerance may return; invalid tolerances should raise ValueError.
    # The subprocess bounds the runtime even while the implementation is broken.
    subprocess.run([sys.executable, "-c", code], timeout=2, check=True, capture_output=True)


def diagnostics():
    """Run this file as a script for the deterministic grid and timing report."""
    rng = random.Random(606)
    shapes = [(a, b) for a in [1, 2, 10, 50, 100, 250, 500] for b in [1, 2, 10, 50, 100, 250, 500]]
    shapes += [(rng.randint(1, 500), rng.randint(1, 500)) for _ in range(100)]
    worst_cdf, worst_ppf = (0, None), (0, None)
    cdf_count = ppf_count = 0
    for a, b in shapes:
        post = BetaPosterior(a, b)
        for x in [
            0,
            1e-12,
            1e-6,
            0.001,
            0.01,
            0.1,
            0.5,
            0.9,
            0.99,
            1 - 1e-12,
            1,
            a / (a + b),
            rng.random(),
        ]:
            error = abs(post.cdf(x) - reference_beta.cdf(x, a, b))
            worst_cdf = max(worst_cdf, (error, (a, b, x)), key=lambda row: row[0])
            cdf_count += 1
        for q in [0, 1e-12, 1e-9, 1e-6, 0.001, 0.025, 0.5, 0.975, 0.999, 1 - 1e-6]:
            error = abs(post.quantile(q) - reference_beta.ppf(q, a, b))
            worst_ppf = max(worst_ppf, (error, (a, b, q)), key=lambda row: row[0])
            ppf_count += 1
    tail = []
    for a, b in [(1, 500), (500, 500), (500, 1)]:
        for q in [1 - 1e-9, 1 - 1e-12, 1]:
            actual = BetaPosterior(a, b).quantile(q)
            expected = float(reference_beta.ppf(q, a, b))
            tail.append([a, b, q, actual, expected, abs(actual - expected)])
    timings = []
    for a, b in [(1, 1), (1, 500), (500, 1), (500, 500), (1, 5000)]:
        post = BetaPosterior(a, b)
        row = {"a": a, "b": b}
        for label, fn in [
            ("cdf", lambda post=post: post.cdf(post.mean())),
            ("quantile", lambda post=post: post.quantile(0.5)),
        ]:
            values = []
            for _ in range(5):
                start = time.perf_counter()
                fn()
                values.append(time.perf_counter() - start)
            row[label + "_ms"] = 1000 * statistics.median(values)
        timings.append(row)
    return {
        "versions": {p: version(p) for p in ["scipy", "statsmodels", "hypothesis"]},
        "cdf_count": cdf_count,
        "ppf_count": ppf_count,
        "worst_cdf": worst_cdf,
        "worst_ppf": worst_ppf,
        "upper_tail": tail,
        "timings": timings,
        "sprt": [
            simulate(p0, p1, truth, 6001 + i)
            for p0, p1 in [(0.01, 0.1), (0.4, 0.6), (0.6, 0.4)]
            for i, truth in enumerate([p0, p1])
        ],
    }


if __name__ == "__main__":
    print(json.dumps(diagnostics(), indent=2))
