"""Statistics used by the checks.

Confidence intervals for rates, Bayesian pass-rate estimates, pass@k and
Wald's sequential probability ratio test (SPRT). Everything is plain Python
on purpose: each function is short enough to check by hand against the
formulas in the explainer document (sections 6 and 8).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

# Two-sided 95% normal quantile.
Z95 = 1.959963984540054


def _check_counts(events: int, n: int) -> None:
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if not 0 <= events <= n:
        raise ValueError(f"events must be in [0, n], got {events} of {n}")


def wilson_interval(events: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial rate.

    Solves |p_hat - p| <= z * sqrt(p(1 - p) / n) for p. Unlike the Wald
    interval it stays honest when events == 0 or events == n.
    """
    _check_counts(events, n)
    p_hat = events / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n)) / denom
    # At the edges the bound is exactly 0 or 1; floating point can leave a
    # tiny remainder that would turn "no failures" into "some failures".
    low = 0.0 if events == 0 else max(0.0, center - half)
    high = 1.0 if events == n else min(1.0, center + half)
    return low, high


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimate from n attempts with c successes.

    1 - C(n - c, k) / C(n, k): one minus the chance that k attempts drawn
    without replacement are all failures.
    """
    _check_counts(c, n)
    if not 1 <= k <= n:
        raise ValueError(f"k must be in [1, n], got {k} with n={n}")
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def _log_binom_pmf(m: int, j: int, x: float) -> float:
    return (
        math.lgamma(m + 1)
        - math.lgamma(j + 1)
        - math.lgamma(m - j + 1)
        + j * math.log(x)
        + (m - j) * math.log1p(-x)
    )


@dataclass(frozen=True)
class BetaPosterior:
    """Beta(alpha, beta) belief about a success rate, with integer parameters.

    With a uniform prior Beta(1, 1), observing c successes in n attempts
    gives Beta(1 + c, 1 + n - c). Integer parameters let the CDF be computed
    exactly through the binomial identity
    I_x(a, b) = P(Binomial(a + b - 1, x) >= a).
    """

    alpha: int
    beta: int

    def __post_init__(self) -> None:
        if self.alpha < 1 or self.beta < 1:
            raise ValueError("alpha and beta must be integers >= 1")

    @classmethod
    def from_counts(cls, successes: int, n: int, prior: tuple[int, int] = (1, 1)) -> BetaPosterior:
        _check_counts(successes, n)
        return cls(prior[0] + successes, prior[1] + n - successes)

    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def cdf(self, x: float) -> float:
        """P(p <= x) under this posterior."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        m = self.alpha + self.beta - 1
        total = 0.0
        for j in range(self.alpha, m + 1):
            total += math.exp(_log_binom_pmf(m, j, x))
        return min(1.0, total)

    def quantile(self, q: float, tol: float = 1e-10) -> float:
        """Smallest x with cdf(x) >= q, by bisection."""
        if not 0.0 <= q <= 1.0:
            raise ValueError(f"q must be in [0, 1], got {q}")
        lo, hi = 0.0, 1.0
        while hi - lo > tol:
            mid = (lo + hi) / 2
            if self.cdf(mid) < q:
                lo = mid
            else:
                hi = mid
        return hi

    def credible_interval(self, mass: float = 0.95) -> tuple[float, float]:
        """Equal-tailed credible interval holding `mass` of the posterior."""
        tail = (1.0 - mass) / 2
        return self.quantile(tail), self.quantile(1.0 - tail)


class Decision(StrEnum):
    CONTINUE = "continue"
    ACCEPT_H0 = "accept_h0"
    ACCEPT_H1 = "accept_h1"


@dataclass
class BernoulliSPRT:
    """Wald's sequential test between two rates of a yes/no event.

    H0: rate = p0, H1: rate = p1. Feed one observation at a time with
    update(); stop as soon as the decision is not CONTINUE. alpha is the
    chance of accepting H1 when H0 is true, beta the reverse.
    """

    p0: float
    p1: float
    alpha: float = 0.05
    beta: float = 0.05
    llr: float = 0.0
    n: int = 0
    events: int = 0

    def __post_init__(self) -> None:
        for name, value in (("p0", self.p0), ("p1", self.p1)):
            if not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be in (0, 1), got {value}")
        if self.p0 == self.p1:
            raise ValueError("p0 and p1 must differ")
        for name, value in (("alpha", self.alpha), ("beta", self.beta)):
            if not 0.0 < value < 0.5:
                raise ValueError(f"{name} must be in (0, 0.5), got {value}")

    @property
    def upper(self) -> float:
        return math.log((1 - self.beta) / self.alpha)

    @property
    def lower(self) -> float:
        return math.log(self.beta / (1 - self.alpha))

    @property
    def decision(self) -> Decision:
        if self.llr >= self.upper:
            return Decision.ACCEPT_H1
        if self.llr <= self.lower:
            return Decision.ACCEPT_H0
        return Decision.CONTINUE

    def update(self, event: bool) -> Decision:
        if event:
            self.llr += math.log(self.p1 / self.p0)
            self.events += 1
        else:
            self.llr += math.log((1 - self.p1) / (1 - self.p0))
        self.n += 1
        return self.decision


class FlakeVerdict(StrEnum):
    STABLE = "stable"
    FLAKY = "flaky"
    UNKNOWN = "unknown"


def flake_verdict(failures: int, n: int, threshold: float = 0.05) -> FlakeVerdict:
    """Classify a reference solution's failure count over n clean runs.

    FLAKY when the Wilson lower bound is above zero (any failure at all),
    STABLE when the upper bound is below `threshold`, UNKNOWN otherwise.
    """
    low, high = wilson_interval(failures, n)
    if low > 0.0:
        return FlakeVerdict.FLAKY
    if high < threshold:
        return FlakeVerdict.STABLE
    return FlakeVerdict.UNKNOWN
