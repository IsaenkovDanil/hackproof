# Harbor 0.25.0 Python API: verified local trials

All source URLs below were opened on **2026-10-26**. Installed `harbor==0.25.0` with `uv venv --python 3.12 /Users/danil/hackproof-vendor/harbor-api-env` and `uv pip install --python /Users/danil/hackproof-vendor/harbor-api-env/bin/python 'harbor==0.25.0'`. No Hackproof dependency was added. Exact installed dependencies: installed-packages.json (local evidence, not published).

Ten relevant wheel source files match byte-for-byte the earlier internals checkout at commit `872da9479f4a2078142d22c49c9ffae0f09e2e63`; URLs, HTTP 200 responses and SHA-256 digests are in source-access.json (local evidence, not published). This establishes correspondence for those files, not the wheel's complete build provenance (UNVERIFIED). Terminal-Bench tasks use the existing task-04 checkout at commit `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; see [task-04 evidence](local-run-report.md). Runtime measurements below are supported by the linked local JSON, rather than inferred from upstream documentation.

## Working Python entry point

```python
import asyncio
from pathlib import Path
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    TrialConfig,
)
from harbor.trial.trial import Trial


async def main():
    trial = await Trial.create(
        TrialConfig(
            task=TaskConfig(path=Path("/absolute/path/to/task")),
            agent=AgentConfig(name="oracle"),  # 'nop' for the baseline
            environment=EnvironmentConfig(type="docker"),
            trials_dir=Path("/absolute/output/trials"),
            trial_name="task--oracle",
        )
    )
    result = await trial.run()
    Path("/absolute/output/result.json").write_text(result.model_dump_json(indent=2))
    print(result.verifier_result, result.exception_info)


if __name__ == "__main__":
    asyncio.run(main())
```

This import/configuration/factory/run sequence actually completed all six trials. The complete sequential runner is run_trials.py (local evidence, not published); run it using the throwaway environment's `bin/python`. It uses `model_dump(mode='json')` so paths, UUIDs and datetimes serialize correctly. Plain `model_dump()` contains Python objects. Use a fresh `trials_dir`/trial names for repetitions to retain independent evidence. Source: [configuration source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py), [trial source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py).

These are **trial-level** config classes. `harbor.models.task.config.TaskConfig` instead describes `task.toml`; confusing the two loses the local task-selection API. `Trial.create` and `run` are both awaited. Setup/factory errors can raise before a result exists; normal run-phase exceptions are often recorded and returned, but cancellation is re-raised, and finalization failures can also propagate. Do not assume every call returns successfully. Source: [configuration source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py), [trial source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py).

## Field names and defaults

The following covers every field of the five runtime config objects used by this API (including the default verifier). `None` is Python null, `[]`/`{}` are fresh collections. Defaults are validated effective defaults where noted. Machine-readable declared defaults/types, including fields omitted by serialization, are in field-defaults.json (local evidence, not published). Source for all tables: [configuration source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py).

| Model | Fields and defaults |
|---|---|
| TaskConfig | `path=None`, `git_url=None`, `git_commit_id=None`, `name=None`, `ref=None`, `overwrite=False`, `download_dir=None`, `source=None`. Exactly one of `path` or package `name` must be supplied; `ref` requires `name`, commit requires Git URL. |
| TrialConfig | `task` required; `trial_name=""`, `trials_dir=Path("trials")`, `install_only=False`, `timeout_multiplier=1.0`; `agent_timeout_multiplier`, `verifier_timeout_multiplier`, `agent_setup_timeout_multiplier`, `environment_build_timeout_multiplier` all None; `agent=AgentConfig()`, `environment=EnvironmentConfig()`, `verifier=VerifierConfig()`, `user_agent=None`; `artifacts=[]`, `extra_instruction_paths=[]`, `extra_instructions=[]`, `job_id=None`, `source_trial=None`. |
| AgentConfig | `name=None` declared, resolves to `"oracle"` if name/import path absent; `import_path`, `model_name`, `base_url`, `model_api_key_name`, `model_api_format`, `n_concurrent`, `concurrency_group`, `override_timeout_sec`, `override_setup_timeout_sec`, `max_timeout_sec`, `load_trajectory` all None; `skip_model_parsing=False`, `resume_trajectory=False`; `skills=[]`, `extra_allowed_hosts=[]`, `include_logs=[]`, `exclude_logs=[]`, `mcp_servers=[]`, `kwargs={}`, `env={}`. |
| EnvironmentConfig | `type=None` declared, resolves to `"docker"` when type/import path absent; `import_path=None`, `force_build=False`, `delete=True`, `stream=False`; `cpu_enforcement_policy="auto"`, `memory_enforcement_policy="auto"`; `override_cpus`, `override_memory_mb`, `override_storage_mb`, `override_gpus`, `override_tpu`, `mounts` all None; `suppress_override_warnings=False` deprecated/no effect/excluded from dumps; `extra_docker_compose=[]`, `env={}`, `kwargs={}`, `extra_allowed_hosts=[]`. |
| VerifierConfig | `override_timeout_sec=None`, `max_timeout_sec=None`, `include_logs=[]`, `exclude_logs=[]`, `env={}`, `import_path=None`, `kwargs={}`, `disable=False`, `extra_allowed_hosts=[]`. |

Empty log filters/env and several verifier fields are conditionally omitted from `model_dump`; omission does not mean the model lacks the field. Timeout override fields belong here; `timeout_sec` belongs to the task configuration. Fixture task limits are agent 120 s and verifier 60 s; no trial overrides were applied. Source: [configuration source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py); fixture contents and resolved `lock.json` under trial evidence (local evidence, not published).

## Result and failure contract

The return type is `harbor.models.trial.result.TrialResult`. Every top-level serialized field is listed below. Source: [result source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/result.py); observed values: six result dumps (local evidence, not published).

| Fields | Meaning / observed values |
|---|---|
| `id`, `task_name`, `trial_name`, `trial_uri` | UUID, names and URI of the host trial directory. |
| `task_id`, `source`, `task_checksum` | Local task path here, null source, checksum of task content. Local selection does not automatically add the dataset Git commit to provenance. |
| `config`, `agent_info` | Resolved runtime config; agent name/version/model info (`model_info=null` here). |
| `agent_result` | AgentContext: `n_input_tokens`, `n_cache_tokens`, `n_output_tokens`, `cost_usd`, `model_usage`, `rollout_details`, `metadata`; all null in these utility-agent runs. |
| `verifier_result` | `{"rewards": {"reward": 1.0}}` or zero here. Numeric reward is **`result.verifier_result.rewards["reward"]`**. Check for null before access; other tasks can use other metric keys. |
| `verifier_environment_mode` | `"shared"` for all six runs. This is observed grading mode, not evidence of grader isolation. |
| `exception_info` | Null in all six. On handled failure: `exception_type`, `exception_message`, `exception_traceback`, `occurred_at`. |
| `started_at`, `finished_at` | UTC timestamps; subtract for trial duration. |
| `environment_setup`, `agent_setup`, `agent_execution`, `verifier` | Each a nullable TimingInfo with nullable `started_at`/`finished_at`. Subtract within a phase when both exist; phases do not cover all teardown/collection overhead. |
| `step_results` | Null for these single-step trials; multi-step StepResult contains `step_name`, `agent_result`, `verifier_result`, `exception_info`, `agent_execution`, `verifier`. Multi-step runtime behavior is UNVERIFIED here. |

`reward_valid` and `failure_cause` are Python properties, **not keys in the result JSON**. `reward_valid` checks a nonempty reward map and the policy of recorded trial/step exceptions; `failure_cause` selects the first recorded exception's classification. An exception may coexist with a reward: do not blindly map every exception to zero or discard every reward. These successful runs have `reward_valid=True`, `failure_cause=None`. Source: [result source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/result.py), [error policy](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/error_policy.py).

Timeouts were **not induced** in these six runs; the following is source-verified, runtime UNVERIFIED: agent execution expiry becomes `AgentTimeoutError` and can still be graded; verifier expiry becomes `VerifierTimeoutError`; environment start/build expiry becomes `EnvironmentStartTimeoutError`; setup expiry becomes `AgentSetupTimeoutError`. The error policy marks agent time exhaustion as reward-valid, but verifier/sandbox failures as invalid. Missing, empty or malformed reward files become `RewardFileNotFoundError`, `RewardFileEmptyError`, `VerifierOutputParseError`, rather than legitimate zero rewards. Source: [trial source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py), [error policy](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/error_policy.py), [verifier source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py).

## Logs, artifacts and timings

Host root for each run: `codex/out/07/trials/<task>--<agent>/`; `trial_uri` records its absolute URI. Observed files include `config.json`, `lock.json`, **`result.json`** (singular), `trial.log`, `verifier/reward.txt`, `verifier/test-stdout.txt`, `artifacts/manifest.json`, and oracle-only `agent/oracle.txt` (no `exit-code.txt` was produced for these successful solves). There is no nop trajectory file in these runs. `exception.txt` and `verifier/test-stderr.txt` are available paths but were not produced here. Source: [path source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/paths.py); actual trial directories (local evidence, not published).

Linux container paths are `/logs/agent`, `/logs/verifier`, `/logs/artifacts`; oracle receives `/solution`, verifier receives `/tests`. Reward text lives at `/logs/verifier/reward.txt`; JSON alternative is `/logs/verifier/reward.json`. Configured artifacts and the convention directory are collected into host `artifacts/` with a manifest; the observed manifests record successful collection of the empty `/logs/artifacts` convention directory (no task output files were declared). Source: [path source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/paths.py); observed manifests under trials (local evidence, not published).

| Task | Agent | Reward | Wall seconds | Harbor error |
|---|---|---:|---:|---|
| count-lines | oracle | 1.0 | 20.483 | none |
| count-lines | nop | 0.0 | 7.229 | none |
| cancel-async-tasks | oracle | 1.0 | 31.414 | none |
| cancel-async-tasks | nop | 0.0 | 18.131 | none |
| nginx-request-logging | oracle | 1.0 | 45.121 | none |
| nginx-request-logging | nop | 0.0 | 27.162 | none |

Wall time uses monotonic `perf_counter` around **both** `Trial.create` and `trial.run`, including teardown. It differs slightly from the result's `finished_at - started_at`. Raw measurements: summary.json (local evidence, not published). One attempt per combination; this is API compatibility evidence, not a reliability estimate. Task-04 passing-task selection: [earlier report](local-run-report.md).

## Fixture and differences from harbor-internals.md

`tests/fixtures/harbor/count-lines` runs **unchanged**: oracle 1, nop 0, no exceptions. No fixture correction is needed. Its oracle and baseline used identical task checksums; source/test/fixture files were not edited. Evidence: oracle (local evidence, not published), nop (local evidence, not published).

The [internals reference](harbor-internals.md) section 7 is now execution-verified for Harbor 0.25.0, Docker, these single-step tasks and these two agents. No behavior conflict was found in the reviewed matching source files. This reference adds the complete runtime config defaults, exact result shape, `reward_valid`/`failure_cause` semantics and six real measurements. The path module's own directory-layout docstring says `results.json`, but its implemented property and all six actual outputs use `result.json`; the internals reference already uses the correct singular name. Source: [path source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/paths.py), [result source](https://raw.githubusercontent.com/harbor-framework/harbor/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/result.py).

Remaining UNVERIFIED: induced failures/timeouts, multi-step/separate grading, provider/platform portability, complete wheel-to-Git build provenance, live dataset registry mapping and repeated-run reliability. Neither source identity for ten files nor six passing runs proves those properties.
