# Independent statistics cross-check

Run/access date: 2026-10-26. Local source: `src/hackproof/stats.py`, repository HEAD
`9ae84d813840cb20517dd28109731a2058e9e45e`. No implementation or dependency files changed.
All numerical results below are measurements from the companion test file, not published results.
Environment: macOS arm64, repository Python 3.14.7; SciPy 1.18.1,
statsmodels 0.15.0, Hypothesis 6.170.11.

## Reference methods and reproduction

- Wilson: [statsmodels proportion_confint](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html), `method="wilson"`, alpha=0.05 (accessed 2026-10-26).
- Beta: [SciPy beta](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.beta.html), `cdf` and inverse `ppf`; [regularized incomplete beta](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.betainc.html) defines the reference CDF (both accessed 2026-10-26).
- Generated tests use [Hypothesis](https://hypothesis.readthedocs.io/en/latest/reference/api.html) with deterministic settings, no deadline or persistent example database (accessed 2026-10-26).
- SPRT log thresholds agree with the [NIST sequential sampling equations](https://www.itl.nist.gov/div898/handbook/pmc/section2/pmc26.htm). The ASN approximation below follows [Vakili, dissertation, section 8.1, printed p. 91](https://ecommons.cornell.edu/server/api/core/bitstreams/07991409-8a89-4d7d-9d60-2ee897dfc935/content) (both accessed 2026-10-26).

From the repository:

```sh
uv run --with scipy --with statsmodels --with hypothesis pytest tests/crosscheck -q
uv run --with scipy --with statsmodels --with hypothesis python tests/crosscheck/test_stats_crosscheck.py
uv run pytest
uv run ruff check .
```

The script command prints the deterministic Beta grid, upper-tail cases, median timings and
all simulation results as JSON. Optional dependencies are guarded by three importorskip calls.
The test run used a temporary uv cache and Hypothesis directory, disabled bytecode writes and
pytest's cache provider. Downloaded libraries are temporary wheels, not vendored repository code;
versions above identify them (no third-party source checkout or commit was used).

## Numerical results

These maxima cover the stated samples, not the entire parameter domain.

| Comparison | Coverage | Largest observed absolute error / outcome |
|---|---|---|
| Wilson | 500 Hypothesis pairs, n ≤ 10,000; explicit 0/n edges at n=1,2,10,100,10,000 | All within 1e-9 |
| Wilson diagnostic | 10,000 random pairs, Python Random(606), n uniform 1…10,000 then events uniform 0…n | 2.220446049250313e-16 at events=8, n=24 (Python 3.12.15 scratch run) |
| Beta CDF | 300 Hypothesis cases; diagnostic grid of 1,937 evaluations | 5.174749517777855e-13 at a=b=500, x=0.9 |
| Beta quantile | 150 Hypothesis cases with q in [1e-6, 1−1e-6]; diagnostic grid of 1,490 evaluations | 1.8816540547916816e-9 at a=429, b=425, q=0.999999 |
| Beta upper tail | Additional nine evaluations, three shapes × three q values | Maximum 0.04809069214388728 at a=1, b=500, q=1 |
| pass@k | Exhaustive n=1…10, every c=0…n and k=1…n | All 440 triples agree within 1e-15 |

The Beta diagnostic uses 49 shape pairs from {1,2,10,50,100,250,500}² plus 100 seeded
random pairs. For each pair it checks 13 x values (endpoints, tails, mean, fixed interior
points and a random point) and ten q values from zero through 0.999999. Duplicated points
are counted. See `diagnostics()` for the exact grid. The upper-tail stress cases are separate
so their failures remain visible rather than being hidden by a relaxed central tolerance.
The pass@k oracle enumerates subsets and counts those containing a successful attempt;
it does not reuse the implementation's binomial-coefficient formula.

## Confirmed defects and minimal reproductions

All examples below were checked locally on 2026-10-26. Ten strict xfail cases preserve the
confirmed expectations without changing `src/`.

| Defect | Minimal reproduction | Observed behavior / expected behavior |
|---|---|---|
| Upper endpoint quantile | `BetaPosterior(1, 500).quantile(1)` | 0.9519093078561127 / 1.0 |
| Extreme upper-tail inversion | `BetaPosterior(500, 500).quantile(1-1e-12)` | 0.6109043594333343 / SciPy 0.6098898039757868; error 0.0010145554575474725 |
| Integer/finite shape validation | `BetaPosterior(a, 2)` for a=1.5, NaN, infinity | Constructor accepts each; should reject parameters outside its documented integer domain |
| Negative Wilson z | `wilson_interval(5, 10, z=-1)` | Reversed interval (0.6507556722888818, 0.34924432771111824) / reject |
| Infinite tolerance | `BetaPosterior(1, 1).quantile(0.5, tol=math.inf)` | 1.0 / reject nonfinite tolerance |
| Bisection termination | `BetaPosterior(2, 3).quantile(0.5, tol=t)` for t=0, −1, 1e-30 | Each exceeds bounded timeout (1 s scratch, 2 s regression); no progress guard when midpoint rounds to an endpoint |

Further measured observations: `BetaPosterior(2,3).cdf(math.nan)` returns 1.0;
`BetaPosterior(1,1).quantile(0)` returns 5.820766091346741e-11, within default tolerance
of zero. NaN policy and exact lower-endpoint behavior need an explicit contract; they are
not included among the ten xfails. Count validation checks inequalities, not integrality;
type annotations alone do not enforce integer counts (local code inspection).

The binomial identity is mathematically exact; its floating-point sum is not exact.
The observed CDF error stays below 1e-9 through the tested shapes, but small absolute CDF
errors become large quantile errors where the upper-tail density is tiny. For example,
a=b=500, q=1−1e-9 already has quantile error 1.0106189441971836e-6. Clipping the CDF at
one and nonmonotone numerical roundoff near saturation undermine the bisection predicate
(local measurement and code-based inference; SciPy reference linked above).

## SPRT simulation

Independent Bernoulli sequences stop at the **first** boundary crossing. Each table row has
10,000 sequences; Random seeds 6001 under H0 and 6002 under H1. alpha=beta=0.05.
A 100,000-observation safety cap raises a failure rather than silently censoring; all sequences
terminated (largest observed length 264). Error intervals are statsmodels Wilson 95% intervals;
ASN uncertainty is one Monte Carlo standard error.

| p0, p1 | Truth / error type | Errors | Rate | 95% interval | ASN ± SE | Wald ASN |
|---|---|---|---|---|---|---|
| 0.01, 0.1 | H0 / I | 228 / 10,000 | 2.28% | 2.01–2.59% | 39.6809 ± 0.1823 | 37.1506 |
| 0.01, 0.1 | H1 / II | 488 / 10,000 | 4.88% | 4.47–5.32% | 24.7633 ± 0.2044 | 18.3417 |
| 0.4, 0.6 | H0 / I | 349 / 10,000 | 3.49% | 3.15–3.87% | 37.0262 ± 0.2571 | 32.6785 |
| 0.4, 0.6 | H1 / II | 401 / 10,000 | 4.01% | 3.64–4.41% | 37.1650 ± 0.2575 | 32.6785 |
| 0.6, 0.4 | H0 / I | 400 / 10,000 | 4.00% | 3.63–4.40% | 36.9152 ± 0.2512 | 32.6785 |
| 0.6, 0.4 | H1 / II | 365 / 10,000 | 3.65% | 3.30–4.04% | 36.8108 ± 0.2565 | 32.6785 |

Let U=log((1−beta)/alpha), L=log(beta/(1−alpha)), and
D(p)=p log(p1/p0)+(1−p) log((1−p1)/(1−p0)). We compare
ASN(H0)≈[(1−alpha)L+alpha U]/D(p0) and
ASN(H1)≈[beta L+(1−beta)U]/D(p1), using nominal alpha/beta
(Vakili reference above). These ignore boundary overshoot. All empirical errors are below
5%; H1 at p=0.1 has a confidence interval crossing 5%, so this simulation does not prove
an exact bound. Its ASN exceeds the approximation by 35.0%; the other differences are
6.8–13.7%. Boundary overshoot is a plausible explanation, not a separate measured causal
estimate. Tests allow four nominal Monte Carlo standard errors on rates and an ASN ratio
of 0.75…1.6 for these selected designs; these are regression tolerances, not theoretical bounds.
No universal error guarantee is inferred for other parameter choices or continued updates
after a decision.

## Performance and recommendations

Median of five calls on this machine, CDF at posterior mean and quantile at q=0.5;
not a portable benchmark or a timing assertion:

| alpha, beta | CDF ms | Quantile ms |
|---|---|---|
| 1, 1 | 0.000541 | 0.008583 |
| 1, 500 | 0.115416 | 3.903542 |
| 500, 1 | 0.000417 | 0.010667 |
| 500, 500 | 0.117875 | 3.990958 |
| 1, 5000 | 1.198541 | 40.714959 |

Local loop inspection shows beta summands per CDF call and approximately 34 CDF calls
per default quantile; cost grows linearly with beta for fixed tolerance. Shapes up to 500
were manageable individually (~4 ms worst median quantile in the timing sample), but
large batches multiply that cost. The additional beta=5000 probe is outside the task's
accuracy grid and took ~41 ms per median quantile; its accuracy was not characterized.

Recommended follow-up, requiring a separate source-edit task:

1. Return exact endpoints for q=0/1; validate finite positive tolerance and stop on midpoint
   stagnation. Bound iteration count as a second safeguard.
2. Evaluate the smaller tail with symmetry and stable summation or a vetted dependency-free
   incomplete-beta algorithm; invert the survival function in the upper tail. Retain SciPy as
   the optional test oracle. Recheck extreme tails after any change.
3. Enforce the documented integer shape domain and define policies for NaN, integer counts,
   and invalid z. Avoid silently returning an ordinary probability for NaN input.
4. Document SPRT approximation/overshoot and first-crossing stopping. Extend simulations
   over additional rates and unequal alpha/beta before broader calibration claims.

## Verification and limits

Final cross-check: **21 passed, 10 xfailed**. Normal optional-dependency-free run:
**44 passed, 1 skipped**. Ruff: **all checks passed**. Protected source, existing tests,
pyproject.toml and uv.lock have no diff. Existing untracked corpus/research material was preserved.
No commits, pushes, issues, PRs, paid APIs or LLM calls were made.

UNVERIFIED: a public permalink to the inspected source commit could not be fetched through
the web tool; source observations above use the local checkout. No exhaustive proof over
all alpha/beta ≤500, no arbitrary-tolerance guarantee and no universal SPRT calibration are
claimed. Runtime measurements vary by host. All source links above were actually opened
on 2026-10-26; local empirical observations are reproducible with the companion test file.
