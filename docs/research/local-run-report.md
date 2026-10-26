# Local Harbor runs and Terminal-Bench 2.0 catalogue

Date: **2026-10-26** (Europe/Moscow). Runtime statements below are measurements from this session; source-derived statements link to sources accessed on that date. Task 03's `harbor-internals.md` was read before execution.

## Environment and provenance

- Apple M5, arm64; macOS 27.0.1, build 26A434. Docker Desktop 4.96.3 (244472), client/server Engine 29.9.2; Linux arm64 server with 10 CPUs and 8,319,504,384 bytes of memory. See [captured environment commands](../../codex/out/04-runs/environment.json).
- Installed Harbor **0.25.0** with `uv tool install harbor`, using uv 0.13.5, following the [official installation instructions](https://docs.harborframework.com/getting-started/installation) (accessed 2026-10-26). [Install log](../../codex/out/04-runs/install.log), [installed versions](../../codex/out/04-runs/harbor-package.json). The wheel's exact Git commit is UNVERIFIED; the prior source-analysis checkout remains at `872da9479f4a2078142d22c49c9ffae0f09e2e63` and was not substituted for the installed release.
- Downloaded the [public Terminal-Bench 2.0 repository](https://github.com/harbor-framework/terminal-bench-2/tree/2fd12b88aafdd04a52c298e3940bcb189f9766d6), exact commit `2fd12b88aafdd04a52c298e3940bcb189f9766d6`, into `/Users/danil/hackproof-vendor/terminal-bench-2`. This snapshot has 89 task directories. The clone uses 95,528 KiB (93.29 MiB), including 47,564 KiB of Git data. [Download log](../../codex/out/04-runs/dataset-download.log), [provenance](../../codex/out/04-runs/dataset-provenance.json). Today's live registry mapping was not queried; this is a reproducible repository snapshot, rather than an asserted registry resolution.
- Used local `oracle` and `nop` only, with `HARBOR_TELEMETRY=0`, one concurrent trial, one attempt per job, no retries, no model flag, and normal container deletion. The [official telemetry documentation](https://docs.harborframework.com/telemetry/telemetry) describes the opt-out (accessed 2026-10-26). No paid API, API key, LLM call, login, upload, commit, push, issue, or PR was used.

## Selected tasks and measured runs

The sample covers shell/log analysis (`log-summary-date-ranges`), Python async behavior (`cancel-async-tasks`), compilation of Cython extensions (`build-cython-ext`), an Nginx service (`nginx-request-logging`), and PyTorch-to-C model execution (`pytorch-model-cli`). The compiled-extension image supplies the larger-image case. No task in this snapshot declares an environment Compose file; Nginx is a service inside one container, so multi-container execution remains UNVERIFIED. Source: [snapshot](https://github.com/harbor-framework/terminal-bench-2/tree/2fd12b88aafdd04a52c298e3940bcb189f9766d6), accessed 2026-10-26; per-task metadata URL access is recorded in [the source-access log](../../codex/out/04-runs/catalogue-source-access.json).

Each job used this command pattern, with its task, agent, and job name substituted:

```sh
HARBOR_TELEMETRY=0 harbor run \
  --path /Users/danil/hackproof-vendor/terminal-bench-2/TASK \
  --agent oracle --env docker --n-concurrent 1 --n-attempts 1 \
  --max-retries 0 --jobs-dir /Users/danil/hackproof/codex/out/04-runs/jobs \
  --job-name TASK-oracle-1
```

For no-op, `--agent nop` was used. Image architecture was obtained with `docker image inspect`; complete inspections retain image IDs and repository digests. Sizes below are Docker image `.Size` in MiB (2^20 bytes), not compressed download or unique physical disk sizes. Wall time includes CLI startup, setup/pull where needed, agent, verification, and cleanup. The first run uses the job timestamps; subsequent runs use an outer wall-clock measurement, also retaining trial phase timestamps. First attempts may pull images; later attempts use cached images but still repeat dependency installs/downloads inside fresh containers. Consequently these timings are not controlled performance comparisons.

| Task | Agent / attempt | Reward | Wall s | Image MiB | Arch | amd64 emulation | Harness exception |
|---|---|---:|---:|---:|---|---|---|
| build-cython-ext | nop / 1 | 0.0 | 11.2 | 1128.6 | amd64 | yes | none |
| build-cython-ext | oracle / 1 | 0.0 | 119.1 | 1128.6 | amd64 | yes | none |
| cancel-async-tasks | nop / 1 | 0.0 | 19.7 | 172.3 | amd64 | yes | none |
| cancel-async-tasks | oracle / 1 | 1.0 | 33.0 | 172.3 | amd64 | yes | none |
| cancel-async-tasks | oracle / 2 | 1.0 | 31.7 | 172.3 | amd64 | yes | none |
| cancel-async-tasks | oracle / 3 | 1.0 | 31.4 | 172.3 | amd64 | yes | none |
| cancel-async-tasks | oracle / 4 | 1.0 | 31.1 | 172.3 | amd64 | yes | none |
| log-summary-date-ranges | nop / 1 | 0.0 | 17.0 | 179.1 | amd64 | yes | none |
| log-summary-date-ranges | oracle / 1 | 1.0 | 92.5 | 179.1 | amd64 | yes | none |
| nginx-request-logging | nop / 1 | 0.0 | 20.3 | 234.1 | amd64 | yes | none |
| nginx-request-logging | oracle / 1 | 1.0 | 28.2 | 234.1 | amd64 | yes | none |
| nginx-request-logging | oracle / 2 | 1.0 | 23.9 | 234.1 | amd64 | yes | none |
| nginx-request-logging | oracle / 3 | 1.0 | 23.7 | 234.1 | amd64 | yes | none |
| nginx-request-logging | oracle / 4 | 1.0 | 24.9 | 234.1 | amd64 | yes | none |
| pytorch-model-cli | nop / 1 | 0.0 | 109.8 | 173.1 | amd64 | yes | none |
| pytorch-model-cli | oracle / 1 | 1.0 | 186.2 | 173.1 | amd64 | yes | none |

Evidence: [machine-readable summary](../../codex/out/04-runs/run-summary.json), [outer timings and commands](../../codex/out/04-runs/matrix-events.jsonl), [complete job/trial artifacts](../../codex/out/04-runs/jobs/), and `*-image-inspect.json` in [raw logs](../../codex/out/04-runs/). Images with `amd64` on the measured arm64 host imply emulation; [a captured process list](../../codex/out/04-runs/emulation-observation.json) additionally shows `/run/rosetta/rosetta` during the compiled-extension run. No native-arm64 control was run, so the slowdown factor is **UNVERIFIED**.

## Repetitions

- `cancel-async-tasks`: 4 oracle runs, rewards `[1.0, 1.0, 1.0, 1.0]`; no reward variation observed.
- `nginx-request-logging`: 4 oracle runs, rewards `[1.0, 1.0, 1.0, 1.0]`; no reward variation observed.

Four passing executions are a small reliability sample, not proof of determinism or a zero flake rate. Repetitions were sequential, with fresh containers and cached images.

## Problems, diagnoses, and fixes

1. The desktop execution sandbox initially denied the Docker socket and uv's cache lock. Authorized elevated command execution allowed access to the existing daemon/cache; no Docker daemon setting or benchmark file was changed. Subsequent run results are from that working configuration.
2. `build-cython-ext` oracle returned **0**, with no Harbor exception or recorded nonzero oracle exit. The verifier passed 10 tests and failed `test_pyknotid_repository_tests`. The nested repository test process reported 17 passes and one failure. Its full nested assertion is truncated by the outer test's captured-process representation, so the root cause and whether emulation, dependency drift, randomness, or an existing task defect contributed are **UNVERIFIED**. [Verifier output](../../codex/out/04-runs/jobs/build-cython-ext-oracle-1/), [oracle install/build output](../../codex/out/04-runs/jobs/build-cython-ext-oracle-1/). The oracle's downloaded pyknotid source reports commit `441c807dbec2ee32e1da572e24e58d52a4eb7afa` in its log. This failure was preserved; no task, verifier, or reference solution was edited. A proposed follow-up is to reproduce the nested test with complete stdout and pinned dependencies on native amd64 before attributing cause.
3. Provided solutions/verifiers download dependencies at runtime; e.g. the compiled task installed current unpinned transitive dependencies. Image caching alone therefore does not make trials offline or fully reproducible. This is observed in the [oracle log](../../codex/out/04-runs/jobs/build-cython-ext-oracle-1/) and reflected conservatively in the catalogue. No dependency fixes were applied to the corpus.

No Harbor exceptions or missing rewards were recorded in the 16 completed trials. Expected no-op test failures produced reward 0 and were not counted as harness errors.

## Catalogue and disk / cleanup

The [CSV](../../corpus/terminal-bench-2.csv) has one row per task, with column semantics and source/license limits in [corpus/README.md](../../corpus/README.md). All 89 remote `task.toml` files were opened and matched byte-for-byte. Metadata difficulty/category were copied, not recalibrated. All 89 entry scripts invoke pytest; all have a reference solution; all provided workflows contain download/dependency commands. `tests_in_image` remains unknown because no complete prebuilt-image filesystem audit was performed. Only the five sampled execution images have measured architecture; the other 84 are unknown. Repository [Apache-2.0 license](https://raw.githubusercontent.com/harbor-framework/terminal-bench-2/2fd12b88aafdd04a52c298e3940bcb189f9766d6/LICENSE) was opened on 2026-10-26; licenses of embedded/downloaded assets remain UNVERIFIED.

After all trials, `docker ps -a` contains **no containers from these five task names**. Existing unrelated containers were left in place; the five sampled images remain cached. [Disk and cleanup measurements](../../codex/out/04-runs/disk-and-cleanup.json):

```text
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          7         2         1.287GB   1.076GB (83%)
Containers      2         1         36.86kB   4.096kB (11%)
Local Volumes   0         0         0B        0B
Build Cache     0         0         0B        0B
```

The Docker totals cover the entire daemon, including unrelated existing images/containers; an exact before/after task-only physical delta was not measured. The five image `.Size` values sum to 1.843 GiB before deduplicating shared layers. Host `du -sk` readings: dataset clone 95,528 KiB (93.29 MiB), Harbor tool environment 247,016 KiB (241.23 MiB), task 04 raw artifacts 1,660 KiB (1.62 MiB). Tool/cache hard links and shared Docker layers mean these figures should not be added as unique physical storage. Docker storage retained after cleanup excludes the deleted trial containers' transient dependency installations.

## Implications for Hackproof

These are engineering recommendations from the measurements above, not claims about the entire benchmark:

- Support amd64 emulation explicitly: it worked for this sample's execution, but architecture and image digest belong in every result. Prefer an available arm64-native task/image for fast local smoke tests only after validating equivalent grading behavior. Do not infer an emulation speed penalty from these uncontrolled timings.
- Assert oracle success separately from harness completion: the compiled task returned reward 0 even though Harbor completed successfully and the shell command exited 0. A no-op zero alone does not establish a valid task.
- Keep missing reward and harness exceptions distinct from reward 0. Retain verifier stdout, phase times, task checksum, installed dependency versions, and image identity when diagnosing failures.
- Treat runtime network access and dependency versions as reproducibility inputs. An image cache does not cache all per-container installations; an offline-ready audit requires a separate prepared environment and rerun.
- Keep repeat counts and uncertainty visible; this session's two four-run samples do not establish determinism. Multi-container execution, native-arm64 equivalence/performance, and the failing nested test require further work.
- Plan disk for both images and temporary per-trial dependencies. Leave cached images available between audits; clean only containers created by the audit.

Validation: 89 unique CSV IDs match the downloaded task set; metadata URL checks all matched; all 16 trials have a parsed reward and no Harbor exception; both repeated tasks have four recorded oracle trials; image identities are retained for all five tasks; cleanup found no remaining task containers. Existing Hackproof checks passed: 44 pytest tests and Ruff. No production source, test, dependency, lockfile, workflow, root README, or AGENTS file was edited.
