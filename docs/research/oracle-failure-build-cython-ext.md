# Oracle failure: `build-cython-ext`

Investigation: 2026-10-26. All source URLs below were opened on that date; local evidence was collected the same day. No external CI or messages were used.

**Finding: (b), unpinned dependency drift, producing a real task reproducibility defect. Confidence: high.** Three fresh, unchanged oracle trials scored zero. The immediate failure is a missing graph attribute in the reconstruction path with `planarity==1.0.0`. Changing only that installed dependency to `0.6` in a completed trial makes all eleven verifier checks pass on the same emulated machine. This is strong evidence against amd64 emulation as the cause of this particular failure. [Original trials and control evidence](../../codex/out/08-runs/).

## Provenance and procedure

Terminal-Bench checkout: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`, clean before investigation. The task uses an amd64 image, `alexgshaw/build-cython-ext:20251031`; observed image ID and repository digest are both `sha256:3612a38fadb89a96f74a1a951fb0b0af734198fd160571eeaba6401593234594`. Harbor version: 0.25.0. The oracle's pyknotid tag `0.5.3` resolved to `441c807dbec2ee32e1da572e24e58d52a4eb7afa`. [Task configuration](https://raw.githubusercontent.com/harbor-framework/terminal-bench-2/2fd12b88aafdd04a52c298e3940bcb189f9766d6/build-cython-ext/task.toml), [image evidence](../../codex/out/08-runs/image-inspect.json), [runtime versions](../../codex/out/08-runs/host.txt), [upstream commit and dependency evidence](../../codex/out/08-runs/oracle-2/inner-diagnostics.txt).

Three sequential Harbor jobs used the original task directory, `--agent oracle --env docker --n-concurrent 1 --n-attempts 1 --max-retries 0`, with telemetry disabled. Each job retains its config, lock, oracle log, verifier stdout, CTRF, and result JSON. Trial 1 used `--no-delete`; Harbor nevertheless removed its container. Trials 2–3 used `--ek keep_containers=true`, allowing post-trial inspection. The original wrapper captures its child output without including it in the assertion. For trials 2–3, a separate replay invoked that unchanged wrapper with an in-memory observer that prints child commands, return codes, stdout and stderr. No benchmark source or original reward was edited. These are **diagnostic replays**, not recovered output from the original child process; trial 1's inner output remains unavailable. [Observer](../../codex/out/08-runs/diagnostic-observer.py), [collector](../../codex/out/08-runs/collect-diagnostics.py).

| Fresh oracle | UTC start | Duration | Reward | Outer verifier | Harness exception |
|---|---|---:|---:|---|---|
| [1](../../codex/out/08-runs/oracle-1/) | 16:35:07 | 96 s | 0 | 10 pass, 1 fail | none |
| [2](../../codex/out/08-runs/oracle-2/) | 16:37:09 | 135 s | 0 | 10 pass, 1 fail | none |
| [3](../../codex/out/08-runs/oracle-3/) | 16:39:48 | 105 s | 0 | 10 pass, 1 fail | none |

## Failure and causal evidence

The failing outer check is `test_pyknotid_repository_tests`. Its fresh upstream test checkout contains eighteen enabled tests: seventeen pass and `test_reconstructed_space_curve` fails. The task explicitly requires these upstream tests to pass, excluding two other files. The test calls reconstruction before comparing writhe. [Verifier source](https://raw.githubusercontent.com/harbor-framework/terminal-bench-2/2fd12b88aafdd04a52c298e3940bcb189f9766d6/build-cython-ext/tests/test_outputs.py), [task instructions](https://raw.githubusercontent.com/harbor-framework/terminal-bench-2/2fd12b88aafdd04a52c298e3940bcb189f9766d6/build-cython-ext/instruction.md), [upstream test](https://raw.githubusercontent.com/SPOCKnots/pyknotid/441c807dbec2ee32e1da572e24e58d52a4eb7afa/tests/test_spacecurve.py).

Both diagnostic replays reach `Representation._construct_planar_graph`, line 338, then raise `KeyError: 'pos'`. The graph has node keys `vertex_position`, `vertex_start`, `vertex_end` and edge keys `edge_position`, `edge_start`, `edge_end`; pyknotid expects the older `pos`, `start`, `end` schema. The failure occurs before numerical equality is evaluated. [Trial 2 full output](../../codex/out/08-runs/oracle-2/inner-diagnostics.txt), [trial 3 full output](../../codex/out/08-runs/oracle-3/inner-diagnostics.txt), [actual metadata](../../codex/out/08-runs/oracle-2/graph-metadata.txt).

The reference pins setuptools and Cython but installs pyknotid with unconstrained runtime dependencies, including planarity. PyPI lists planarity 0.6 and the newer 1.0.0. Thus the oracle's NumPy compatibility edits do not provide a reproducible runtime dependency set. [Oracle](https://raw.githubusercontent.com/harbor-framework/terminal-bench-2/2fd12b88aafdd04a52c298e3940bcb189f9766d6/build-cython-ext/solution/solve.sh), [pyknotid dependency declaration](https://raw.githubusercontent.com/SPOCKnots/pyknotid/441c807dbec2ee32e1da572e24e58d52a4eb7afa/setup.py), [PyPI release history](https://pypi.org/project/planarity/0.6/).

Controlled intervention in trial 2: install `planarity==0.6` with `--no-deps`, leaving pyknotid sources, NumPy 2.3.0, NetworkX 3.7, Cython 3.1.3, Python 3.13.7, and CPU unchanged. The task's pytest CLI then reports **11 passed in 4.41 s**. Legacy layout keys are present. This is a successful post-trial control, not a fourth Harbor reward. [Installation](../../codex/out/08-runs/oracle-2/control-install.txt), [control dependencies](../../codex/out/08-runs/oracle-2/control-freeze.txt), [legacy layout](../../codex/out/08-runs/oracle-2/control-layout.txt), [complete verifier control](../../codex/out/08-runs/oracle-2/control-verifier-cli.txt).

An earlier control used `python -m pytest` from `/app`, introducing a namespace-package import-path difference: the upstream suite passed, but the core-loader check failed. Its log is retained separately; the passing control uses the task's actual `pytest` entry point. [Earlier control](../../codex/out/08-runs/oracle-2/control-verifier.txt).

## Emulation, limits, and remediation

Host: arm64 macOS; task: Linux x86_64, VirtualApple CPU. Reported flags include SSE2, AVX, AVX2 and FMA. Those advertised capabilities alone do not certify native-equivalent arithmetic. However, the observed error is a dictionary-key mismatch, with no timeout or illegal instruction; changing one dependency eliminates it on this same machine. [Host](../../codex/out/08-runs/host.txt), [CPU and versions](../../codex/out/08-runs/oracle-3/inner-diagnostics.txt).

**UNVERIFIED:** native amd64 behavior; historical oracle success before dependency releases; an exhaustive compatible dependency matrix. Three failures do not establish a universal failure rate, and one passing control does not prove determinism. No claim is made that every possible emulation defect is excluded.

A general fix should constrain and record the full tested dependency set and image digest, or update the reference's compatibility handling for the new metadata schema. Retain NumPy 2.3.0 and the upstream functionality requirement. Save nested stdout/stderr and check clone return codes so future failures are actionable. Re-run fresh oracle trials after any fix, including native amd64 when available. Pinning planarity 0.6 is a demonstrated local candidate, not an exhaustively validated release recommendation. An unsent [private draft](../../codex/out/08-draft-note.md) records the finding for authors.
