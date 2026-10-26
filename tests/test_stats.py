import math

import pytest

from hackproof.stats import (
    BernoulliSPRT,
    BetaPosterior,
    Decision,
    FlakeVerdict,
    flake_verdict,
    pass_at_k,
    wilson_interval,
)


# Rows of the table in section 6 of the explainer.
@pytest.mark.parametrize(
    ("events", "n", "low", "high"),
    [(0, 20, 0.0, 0.1611), (0, 50, 0.0, 0.0713), (2, 20, 0.0279, 0.3010)],
)
def test_wilson_matches_explainer_table(events, n, low, high):
    lo, hi = wilson_interval(events, n)
    assert lo == pytest.approx(low, abs=5e-4)
    assert hi == pytest.approx(high, abs=5e-4)


def test_wilson_is_symmetric_around_half():
    lo, hi = wilson_interval(3, 10)
    lo2, hi2 = wilson_interval(7, 10)
    assert lo == pytest.approx(1 - hi2)
    assert hi == pytest.approx(1 - lo2)


@pytest.mark.parametrize(("events", "n"), [(-1, 10), (11, 10), (0, 0)])
def test_wilson_rejects_bad_counts(events, n):
    with pytest.raises(ValueError):
        wilson_interval(events, n)


@pytest.mark.parametrize(
    ("n", "c", "k", "expected"),
    [
        (10, 3, 5, 1 - 21 / 252),
        (5, 1, 1, 0.2),
        (10, 0, 3, 0.0),
        (10, 10, 1, 1.0),
        (4, 2, 3, 1.0),
    ],
)
def test_pass_at_k(n, c, k, expected):
    assert pass_at_k(n, c, k) == pytest.approx(expected)


def test_pass_at_1_is_the_success_rate():
    assert pass_at_k(40, 13, 1) == pytest.approx(13 / 40)


def test_beta_cdf_matches_binomial_identity():
    # I_0.5(2, 3) = P(Binomial(4, 0.5) >= 2) = 11/16
    assert BetaPosterior(2, 3).cdf(0.5) == pytest.approx(11 / 16)


# Rows of the table in section 8 of the explainer: zero successes in n tries.
@pytest.mark.parametrize(("n", "rounded"), [(10, 0.20), (50, 0.64), (150, 0.95)])
def test_too_hard_probability_after_zero_successes(n, rounded):
    post = BetaPosterior.from_counts(0, n)
    p = post.cdf(0.02)
    assert p == pytest.approx(1 - 0.98 ** (n + 1))
    assert round(p, 2) == rounded


def test_beta_quantile_inverts_cdf():
    post = BetaPosterior(1, 9)
    # For Beta(1, b): cdf(x) = 1 - (1 - x)^b, so the quantile has a closed form.
    assert post.quantile(0.5) == pytest.approx(1 - 0.5 ** (1 / 9), abs=1e-8)
    assert BetaPosterior(1, 1).quantile(0.3) == pytest.approx(0.3, abs=1e-8)


def test_beta_sf_complements_cdf():
    # Beta(2, 3) at 0.5: cdf = 11/16, so sf = 5/16.
    post = BetaPosterior(2, 3)
    assert post.sf(0.5) == pytest.approx(5 / 16)
    assert post.cdf(0.3) + post.sf(0.3) == pytest.approx(1.0)


def test_beta_upper_tail_quantile_uses_survival_function():
    # Beta(b, 1) has cdf x^b, so the q-quantile is q^(1/b) exactly.
    post = BetaPosterior(5, 1)
    q = 1 - 1e-12
    assert post.quantile(q) == pytest.approx(q ** (1 / 5), abs=1e-9)
    assert post.quantile(0.999) == pytest.approx(0.999 ** (1 / 5), abs=1e-9)


@pytest.mark.parametrize(("q", "expected"), [(0.0, 0.0), (1.0, 1.0)])
def test_beta_quantile_endpoints_are_exact(q, expected):
    assert BetaPosterior(1, 500).quantile(q) == expected


@pytest.mark.parametrize("tol", [0, -1, math.inf, math.nan])
def test_beta_quantile_rejects_bad_tolerance(tol):
    with pytest.raises(ValueError, match="tol"):
        BetaPosterior(2, 3).quantile(0.5, tol=tol)


def test_beta_quantile_terminates_for_sub_ulp_tolerance():
    assert BetaPosterior(2, 3).quantile(0.5, tol=1e-30) == pytest.approx(
        BetaPosterior(2, 3).quantile(0.5), abs=1e-9
    )


@pytest.mark.parametrize("value", [1.5, math.nan, math.inf, True])
def test_beta_rejects_non_integer_parameters(value):
    with pytest.raises(TypeError):
        BetaPosterior(value, 2)


@pytest.mark.parametrize("z", [0, -1.96, math.inf, math.nan])
def test_wilson_rejects_bad_z(z):
    with pytest.raises(ValueError, match="z"):
        wilson_interval(5, 10, z=z)


def test_beta_posterior_mean_and_interval():
    post = BetaPosterior.from_counts(3, 10)
    assert (post.alpha, post.beta) == (4, 8)
    assert post.mean() == pytest.approx(4 / 12)
    low, high = post.credible_interval()
    assert 0 < low < post.mean() < high < 1


def test_sprt_boundaries():
    test = BernoulliSPRT(p0=0.01, p1=0.10)
    assert test.upper == pytest.approx(math.log(19))
    assert test.lower == pytest.approx(-math.log(19))


def test_sprt_accepts_stable_after_31_clean_runs():
    # Section 8: each clean run adds ln(0.90 / 0.99), about -0.0953.
    test = BernoulliSPRT(p0=0.01, p1=0.10)
    decisions = [test.update(False) for _ in range(31)]
    assert decisions[29] is Decision.CONTINUE
    assert decisions[30] is Decision.ACCEPT_H0
    assert test.n == 31


def test_sprt_flags_two_failures_in_ten_runs():
    # Section 8: 2 * 2.303 - 8 * 0.0953 is about 3.84, above ln(19).
    test = BernoulliSPRT(p0=0.01, p1=0.10)
    for _ in range(8):
        assert test.update(False) is Decision.CONTINUE
    assert test.update(True) is Decision.CONTINUE
    assert test.update(True) is Decision.ACCEPT_H1
    assert test.llr == pytest.approx(3.843, abs=1e-3)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"p0": 0.0, "p1": 0.1}, "p0"),
        ({"p0": 0.1, "p1": 0.1}, "differ"),
        ({"p0": 0.01, "p1": 0.1, "alpha": 0.7}, "alpha"),
    ],
)
def test_sprt_validates_parameters(kwargs, message):
    with pytest.raises(ValueError, match=message):
        BernoulliSPRT(**kwargs)


@pytest.mark.parametrize(
    ("failures", "n", "verdict"),
    [
        (0, 20, FlakeVerdict.UNKNOWN),
        (0, 100, FlakeVerdict.STABLE),
        (1, 50, FlakeVerdict.FLAKY),
    ],
)
def test_flake_verdict(failures, n, verdict):
    assert flake_verdict(failures, n) is verdict
