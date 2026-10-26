# Verifiers internals and Prime Environments Hub census

Research date: **2026-10-26**. The current source checkout is `PrimeIntellect-ai/verifiers` commit **4e0635c6c63f9584cab9a7d86dd54571a7eb1e35** (2026-10-25). Legacy behavior is pinned separately to **fdbfe496f5bfd39efa799ca0eacde25a7628aa88** (`v0.1.15.dev18`, peeled commit, 2026-06-01). These are source snapshots, not a claim that every Hub package works with either version. All linked sources were opened on **2026-10-26**. Third-party checkouts and Hub archives are under `/Users/danil/hackproof-vendor/`. [Current package root][root]; [legacy loader][legacy-load].

## 1. Package structure and the two API generations

| Aspect | Legacy snapshot | Current snapshot |
|---|---|---|
| Import / entry point | `import verifiers as vf`; installed module exposes `load_environment(**env_args) -> Environment`; loader imports module and calls it | `import verifiers.v1 as vf`; installed package exports its `Taskset` subclass through `__all__`; loader resolves taskset, harness, judge and environment plugins |
| Package layout | `pyproject.toml` plus e.g. `reverse_text.py`; Hatch build includes that module; environment owns dataset, parser and rubric | `pyproject.toml`, package `__init__.py`, `taskset.py`; optional server modules, packaged grading assets and images |
| Task data | Dataset rows / rollout state: prompt, answer, info, task, additional fields | Frozen `TaskData` with prompt, reference fields on subclasses, image, resources, artifacts and scoring policy; mutable per-rollout `State`; behavior on `Task` |
| Agent interaction | `SingleTurnEnv` specializes `MultiTurnEnv`; `ToolEnv` adds tool dispatch and a turn loop | `Harness` installs/launches an agent program; `Runtime` supplies execution/files; `Env` composes the taskset and agent roles |

Sources: [legacy loader][legacy-load], [legacy package manifest][legacy-package], [SingleTurnEnv][single], [MultiTurnEnv][multi], [ToolEnv][tool], [current package guide][building], [tasksets][tasksets], [harnesses][harnesses], [plugin loader][loaders]. The current top-level `verifiers/__init__.py` only exposes version metadata; it does not promise legacy root-import compatibility. Treat intermediate bridge APIs and Hub runtime labels as separate compatibility evidence. [Current root][root].

## 2. Reward signatures and aggregation

**Legacy:** there is no single compulsory positional signature. The type aliases are `IndividualRewardFunc = Callable[..., float | Awaitable[float]]` and `GroupRewardFunc = Callable[..., list[float] | Awaitable[list[float]]]`. A normal function can be `def reward(completion, answer, **kwargs) -> float`, or its async equivalent. The rubric supplies arguments by inspected parameter names: `prompt`, `completion`, `answer`, `state`, `info`, `task`, parser/class objects, and extra task/provider fields. A function declaring `**kwargs` receives the merged objects. Group functions use plural names such as `completions`, `answers`, `states`; return annotation `list` can also trigger group detection. [Types][legacy-types]; [Rubric implementation][rubric].

Weights default to one; a nonempty weight list must match the function count. The total is the **sum of score × weight**, not a normalized mean. Zero-weight functions still execute and produce metrics. Individual invocation casts the result to float; a group function returns one score per rollout. The legacy implementation catches reward-function exceptions, logs them and substitutes zero(s), so a zero can conceal an infrastructure or programming error. Reward functions run in order in `score_group`, with concurrency across states. Do not infer accepted return types from the class docstring alone. [Rubric implementation][rubric].

**Current:** task methods are marked with `@vf.reward(weight=1.0, priority=0)` or `@vf.metric`. A concrete signature is `async def correct(self, trace: vf.Trace) -> float`. Injection supports declared names `trace`, `runtime`, `deployment`, and `task` (the task's **TaskData**, while `self` is its **Task**). Rewards return a float or mapping of score names to floats; the same function weight applies to each mapping entry. `None` leaves a signal unscored. `Task.score` runs metrics, then rewards, then configured judges; handlers within a phase use `asyncio.gather`. At this commit plain synchronous scoring methods returning floats are **not supported by that invocation path**: there is no sync-to-awaitable wrapper. Use async scoring methods even for deterministic computations. This is source inspection, not a current-v1 runtime test. [Task.score][task]; [decorators and invocation][decorators].

Each recorded reward stores score and weight; `trace.reward` sums the weighted values. It is not automatically bounded to `[0,1]`. Nonfinite scores raise; scoring exceptions cross a `TaskError` boundary instead of being silently turned into wrong-answer scores. Separate judge configs carry their own weight/model/client; changing the solver endpoint does not automatically change the judge endpoint. [Trace recording][trace]; [Task.score][task]; [judge configuration guide][tasksets].

## 3. Execution isolation and grader placement

Legacy `SandboxEnv` uses Prime's sandbox client to create a remote container and execute commands; its configuration includes image, CPU, memory, disk and timeouts. Its Python rubric stays in the evaluator process and may call into the same sandbox through captured client/state. The class itself does **not** establish a fresh trusted grader filesystem separate from the solver's modified filesystem. `ToolEnv` alone also does not imply container isolation: tool implementation decides where operations occur. [Legacy SandboxEnv][sandbox]; [ToolEnv][tool].

Current runtimes include local `subprocess`, local `docker`, and remote `prime`. `subprocess` has the evaluator host's file/process/network access. Python hooks, including rewards, run in the evaluator process; `runtime.run/read/write` explicitly reaches the sandbox. A Python reward using `Path.read_text()` therefore reads the evaluator host, not the container. A container boundary for the solver does not make arbitrary host-side execution of generated code safe. [Runtime guide][runtimes].

The current scoring default is **shared**, not isolated. With `ScoringConfig(mode="isolated")`, the framework finalizes and collects declared solver output artifacts, stops solver execution, provisions a fresh verifier runtime, runs task setup, restores artifacts, stages private verifier assets, and scores against that runtime. Python grading orchestration remains evaluator-side. `stage_verifier` is the appropriate place to introduce trusted private tests; `setup` runs on both sides. Output artifacts must occupy paths separate from trusted tests. Local subprocess does not provide the filesystem boundary required for artifact-based isolated scoring. This improves isolation but is not proof that an environment's image, transfer paths or grader dependencies are trustworthy. [Scoring default][scoring]; [grading implementation][grading]; [isolated grading guide][building].

## 4. Install and run without a paid model

**Demonstrated:** Hub `primeintellect/reverse-text@0.1.4`, `verifiers==0.1.12`, Python 3.12.15. The official CLI accepts `prime env install primeintellect/reverse-text@0.1.4`; equivalent direct installation from the public package index was used here. The installed Hub loader, real rollout loop, SDK response conversion, XML parser and rubric were exercised with an in-memory deterministic completion stub. No model endpoint, LLM generation, real API key, or paid sandbox was used. [Official install implementation][prime-cli]; [Hub version metadata][reverse-hub]; [tested rollout implementation][tested-rollout]; [tested client conversion][tested-client].

```bash
uv venv /tmp/hackproof-vf-smoke --python 3.12
uv pip install --python /tmp/hackproof-vf-smoke/bin/python \
  'verifiers==0.1.12' 'reverse-text==0.1.4' \
  --extra-index-url https://hub.primeintellect.ai/primeintellect/reverse-text/install/simple/
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  /tmp/hackproof-vf-smoke/bin/python /Users/danil/hackproof-vendor/prime-hub-05/stub_eval.py
```

The complete executed script, result JSON, package freeze and run log are retained in `/Users/danil/hackproof-vendor/prime-hub-05/`. The script substitutes a one-row `abc` dataset at the loader's dataset boundary, then runs one fixed completion per case. This tests package integration and deterministic grading; it does **not** validate the real downloaded dataset or model quality. The stub cannot open a network connection. Measured results:

| Case | Reward | Interpretation |
|---|---:|---|
| Correct fixed response | 1.0 | Accepted by real parser and rubric |
| Empty response | 0.0 | Client raises `EmptyModelResponseError`; rubric scores the empty completion; retain the error separately |
| Incorrect fixed response | 0.0 | Completed rollout, rejected by rubric |

The Hub metadata declares `verifiers>=0.1.5.post0`, but that minimum failed locally because the package passes a callable dataset and the old framework expects `.column_names`. Pinning 0.1.12 resolved the loader incompatibility. The working run also emitted a parser/rubric-parser mismatch warning. Do not treat a dependency lower bound or a successful install as a successful environment load. These are measured local observations, not a claim about every installation. [Hub dependency metadata][reverse-hub]; [tested rubric][tested-rubric].

For current v1, the documented local endpoint route is `[client] base_url="http://localhost:8000/v1"` with an endpoint-compatible harness (for example `null`, which uses chat completions), and an explicitly local runtime. `null` is a chat agent harness, **not** a no-op completion stub. A no-auth endpoint may need a literal placeholder because of SDK client requirements; that is not a real credential. This path was source-checked but not executed here, in keeping with the no-LLM-call rule. `vf-replay` rescores saved single-agent traces without rerunning the solver, skipping hooks that need unavailable runtime/deployment resources; configured model judges can still require calls. Offline replay is not a full sandbox evaluation. A paid-model fallback is unnecessary for the demonstrated stub route. [Evaluation configuration][evaluation]; [null harness][null]; [replay implementation][replay].

## 5. Built-in validation

Current v1 supplies `Task.validate(runtime) -> bool | None` and `vf-validate`. Authors must implement their own gold check; the default returns `None`, reported as unchecked. A `True` result is an author's hook result, not independent proof that a reference answer gets exactly 1. Without an `--only-*` selection, gold and no-op checks run in separate fresh runtimes. The no-op check rejects **reward >= 1.0**; a positive partial reward below 1.0 passes. Hackproof therefore needs its own stricter zero-reward baseline assertion and a declared score scale. [Task.validate][task]; [validation implementation][validate].

There is a source/docs discrepancy: `docs/debugging.md` says validation does not transfer artifacts or call `stage_verifier`, but current `_score_untouched` explicitly collects artifacts and calls `grade_task` for isolated scoring, and invokes `stage_verifier` in the shared path. The gold path still directly invokes `Task.validate` after setup. Follow this pinned implementation when building the adapter; verify the installed version's behavior with fixtures. No equivalent generic reference-plus-no-op validator was found in the inspected legacy rubric/loader/class files; this is a scoped source finding, not a claim that all legacy packages lack bespoke tests. [Debugging guide][debugging]; [validation implementation][validate]; [legacy rubric][rubric].

## 6. Census method and limitations

`corpus/prime-hub.csv` contains exactly **50 distinct owner/name entries**, obtained from the unauthenticated public API ordered by **stars descending**, `limit=50`, `offset=0`, `visibility=PUBLIC`. The response reported 1,849 public entries; the cutoff row had 5 stars. Ties retain server order; the API does not declare a secondary ordering. These are star counts, not installs, downloads or evidence of active training usage. The visually observed Hub's “Most installs” view is a different ranking and was not mixed into this census. [Public ranked response][census-api]; [CLI list parameters][prime-cli].

All 50 version-metadata endpoints and their returned source archives were retrieved; archive SHA-256 and the source file used for classification are recorded in each row. Retained evidence is in `/Users/danil/hackproof-vendor/prime-hub-05/`, including `top50.json`, `access-log.json`, and one version directory per entry. Classification is manual source inspection of the dominant default behavior: 21 single-turn, 3 multi-turn, 12 tool, 14 sandbox. `sandbox` takes precedence when submissions execute in a managed/container runtime; code evaluated on the host is not called sandboxed. These counts are computed from this CSV, not a framework guarantee. [Ranked response][census-api]; row-level version sources in the CSV.

`needs_api_key` excludes the replaceable solver endpoint and describes additional credentials for the reviewed default environment/scorer/user simulator/runtime. It includes Modal and HUD credentials, even if those services call them tokens. `no` permits a local/stub solver and does not promise zero compute cost or offline datasets. Optional services and transitive uncertainty are in notes. Missing licenses and unconfirmed environment source repositories are `UNVERIFIED`; upstream datasets, third-party libraries and user profiles are not substituted for an environment's repository. `reward_kind=UNVERIFIED` is retained for `proximal/frontier-swe` because its task-specific verifier mix was not fully audited. Further field definitions and row-level provenance are in `corpus/README.md`.

## Implications for the Hackproof adapter

1. **Dispatch by installed code and version.** Maintain a legacy loader/rubric adapter and a taskset/task/trace adapter. Record distribution versions, archive hash, dataset revision, image digest and actual imported module. Hub labels alone are insufficient: AIME packages use v1 imports despite V0 metadata; the skill package has the inverse style mismatch; same-named packages across owners can collide after installation. These observations are recorded with version-source URLs in the census. [Plugin resolution][loaders].
2. **Start with deterministic local scoring.** The demonstrated reverse-text path is a small integration fixture. Add single-turn exact/programmatic examples and multi-turn stateful examples before remote sandboxes or model judges. Preserve per-component scores and weights, and require each task to declare its reward scale; do not assume a weighted sum is a probability. [Legacy rubric][rubric]; [current task scoring][task].
3. **Keep failures distinct from incorrect answers.** Preserve rollout errors, skipped/missing rewards, dropped traces, parser failures and judge failures. Legacy zero substitution and the observed empty-response error make reward-only reports ambiguous. [Legacy rubric][rubric]; [current trace][trace]; local stub result described above.
4. **Inspect the real grader boundary.** Check scoring mode, runtime backend, image contents, mounts, output transfer paths, private-test staging, and where tools execute. Prefer fresh verifier runtimes and allowlisted output artifacts; never infer grader isolation from `SandboxEnv` or a `sandbox` tag. [Runtime guide][runtimes]; [grading implementation][grading].
5. **Reuse validation as evidence, then add stricter checks.** Require exact zero for trivial baselines, actually score gold fixtures, test several deterministic seeds, and exercise isolated artifact transfer. Treat unchecked gold hooks as missing evidence. Add mutation checks and judge-invariance probes separately; their presence is not established by `vf-validate`. [Validation implementation][validate].

## Source index

Every URL below was accessed **2026-10-26**; fixed commits are intentional. The URL/status log is retained as `prime-hub-05/source-access.json` under the vendor root.

[root]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/__init__.py
[legacy-load]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/utils/env_utils.py
[legacy-package]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/environments/reverse_text/pyproject.toml
[single]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/envs/singleturn_env.py
[multi]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/envs/multiturn_env.py
[tool]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/envs/tool_env.py
[building]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/docs/building-environments.md
[tasksets]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/docs/tasksets.md
[harnesses]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/docs/harnesses.md
[loaders]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/utils/loaders.py
[legacy-types]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/types.py
[rubric]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/rubrics/rubric.py
[task]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/task.py
[decorators]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/utils/decorators.py
[trace]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/trace.py
[sandbox]: https://github.com/PrimeIntellect-ai/verifiers/blob/fdbfe496f5bfd39efa799ca0eacde25a7628aa88/verifiers/envs/sandbox_env.py
[runtimes]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/docs/runtimes.md
[scoring]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/configs/scoring.py
[grading]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/grading.py
[evaluation]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/docs/evaluation.md
[null]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/harnesses/null/harness.py
[replay]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/cli/replay.py
[validate]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/verifiers/v1/cli/validate.py
[debugging]: https://github.com/PrimeIntellect-ai/verifiers/blob/4e0635c6c63f9584cab9a7d86dd54571a7eb1e35/docs/debugging.md
[tested-rollout]: https://github.com/PrimeIntellect-ai/verifiers/blob/19797056fd65a55268ffcafc98605525236e7bbb/verifiers/envs/multiturn_env.py
[tested-client]: https://github.com/PrimeIntellect-ai/verifiers/blob/19797056fd65a55268ffcafc98605525236e7bbb/verifiers/clients/openai_chat_completions_client.py
[tested-rubric]: https://github.com/PrimeIntellect-ai/verifiers/blob/19797056fd65a55268ffcafc98605525236e7bbb/verifiers/rubrics/rubric.py
[prime-cli]: https://github.com/PrimeIntellect-ai/prime/blob/933c0309cdfe10bda26d4ac01a14f42eb60c05ff/packages/prime/src/prime_cli/commands/env.py
[reverse-hub]: https://api.primeintellect.ai/api/v1/environmentshub/primeintellect/reverse-text/@0.1.4
[census-api]: https://api.primeintellect.ai/api/v1/environmentshub/?sort_by=stars&sort_order=desc&limit=50&offset=0&visibility=PUBLIC
