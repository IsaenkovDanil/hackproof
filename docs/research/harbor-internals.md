# Harbor internals for the Hackproof adapter

Access date for **all sources: 2026-10-26**. Source baseline: official [Harbor repository](https://github.com/harbor-framework/harbor), discovered through the [official documentation](https://docs.harborframework.com/); cloned to `/Users/danil/hackproof-vendor/harbor`, commit `872da9479f4a2078142d22c49c9ffae0f09e2e63`. All Harbor code links below are immutable permalinks to that commit. Conclusions describe this revision, not every released Harbor version. Analysis is source-based; no task, container, paid service, or LLM was run. Runtime observations are **UNVERIFIED** unless explicitly stated otherwise.

## 1. Task directory and complete configuration inventory

A single-step task has `task.toml`, `instruction.md`, an environment definition, and a verifier script unless tests are bundled in a separate verifier image. `solution/` is optional for ordinary agents but needed for the oracle. Arbitrary supporting files can accompany these; there is no exhaustive finite list of user data filenames. [Task loading and validation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/task.py#L56-L91), [named paths](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/paths.py#L34-L157), [environment definition alternatives](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/definition.py#L7-L36).

| Path | Purpose / requirement |
|---|---|
| `task.toml` | Parsed task configuration; required. |
| `instruction.md` | Agent instruction for a single-step task. |
| `environment/Dockerfile` | Build definition, optional with `environment.docker_image` or Compose. Build context is `environment/`, not task root. |
| `environment/docker-compose.yaml` | Optional multi-service definition; main agent service is `main`. |
| `environment/*` | Build inputs; for a prebuilt image without a local build specification, nonempty environment files can be uploaded after start. |
| `tests/test.sh` | Linux verifier entry point; supporting files live alongside it. |
| `tests/test.bat` | Windows verifier entry point. Script discovery is OS-specific. |
| `tests/Dockerfile`, `tests/docker-compose.yaml` | Separate verifier build definitions; selected ahead of the agent environment fallback. |
| `solution/solve.sh`, `solution/solve.bat` | Reference solution; uploaded only by the oracle in the reviewed agent path. |
| `trajectory.json` | Optional prior ATIF context; support depends on agent capabilities. |
| `README.md`, `.gitignore` | Recognized auxiliary paths, not substitutes for instructions. |
| `.harborignore` | Optional file-selection rules; nested selection affects staged tests and solutions. |
| `steps/<name>/instruction.md` | Instructions for each configured multi-step entry. |
| `steps/<name>/tests/`, `steps/<name>/solution/` | Optional per-step test/solution overrides, otherwise shared fallbacks. |
| `steps/<name>/workdir/`, `workdir/setup.sh` within that step | Optional staged step inputs and setup script. |

Sources for the table: [paths](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/paths.py#L34-L243), [environment upload condition](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/definition.py#L39-L53), [Docker build overlay](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker-compose-build.yaml#L1-L6), [verifier image precedence](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/verifier_mode.py#L89-L133), [file selection](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/file_filter.py#L1-L92), [step staging](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/multi_step.py#L285-L320). Windows is included for format completeness; concrete execution discussion below focuses on Linux Docker.

The following inventory covers every declared field in `models/task/config.py`, including inherited fields. `None` means omitted/unset in Python, not a TOML literal. Tables and arrays default to fresh empty values where shown. Types are Python model types; TOML represents dictionaries as tables and nested models as subtables. Defaults are **schema defaults**, not necessarily initializer-template values or provider allocations. [Full schema source](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L222-L878).

### Root fields and package metadata

| Field | Type | Default |
|---|---|---|
| `schema_version` | str | `"1.4"` |
| `task` | PackageInfo or None | None |
| `metadata` | dict[str, Any] | {} |
| `verifier` | VerifierConfig | default model below |
| `agent` | AgentConfig | default model below |
| `environment` | EnvironmentConfig | default model below |
| `solution` | SolutionConfig | default model below |
| `source` | str or None | None |
| `multi_step_reward_strategy` | `"mean"` / `"final"` or None | None; multi-step resolves to mean |
| `steps` | list[StepConfig] or None | None |
| `artifacts` | list[str or ArtifactConfig] | [] |
| `task.name` | str | required if `[task]` exists; validated `org/name` |
| `task.version` | str or None | None; nonempty when set |
| `task.description` | str | `""` |
| `task.authors` | list[Author] | [] |
| `task.keywords` | list[str] | [] |
| `task.authors[].name` | str | required |
| `task.authors[].email` | str or None | None |

Sources: [root fields and reward strategy](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L846-L901), [package and author fields](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L282-L336).

### Agent, verifier, solution, and phase network settings

| Section / field | Type | Default / meaning |
|---|---|---|
| `agent.timeout_sec` | float or None | None; no task-level agent execution deadline |
| `agent.user` | str or int or None | None; container default USER |
| `agent.network_mode`, `verifier.network_mode` | NetworkMode or None | None; inherit environment baseline |
| `agent.allowed_hosts`, `verifier.allowed_hosts` | list[str] or None | None; valid only with explicit allowlist mode |
| `verifier.timeout_sec` | float | 600.0 seconds |
| `verifier.env` | dict[str, str] | {} |
| `verifier.user` | str or int or None | None; verifier environment default USER |
| `verifier.environment_mode` | `"shared"` / `"separate"` or None | None; resolves shared without verifier environment, separate with it |
| `verifier.environment` | EnvironmentConfig or None | None; same complete schema as environment below |
| `verifier.collect` | list[VerifierCollectConfig] | [] |
| `solution.env` | dict[str, str] | {}; reference-solution command environment |

Sources: [phase settings](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L222-L247), [agent/solution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L339-L348), [verifier](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L573-L629). There is **no `agent.env` field in task.toml** at this revision; agent environment overlays belong to trial/job configuration (`--agent-env KEY=VALUE`), while task-wide variables use `environment.env`. [Trial agent env](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py#L149-L167).

### Environment fields (also apply to `verifier.environment`)

| Field under `environment` | Type | Default |
|---|---|---|
| `build_timeout_sec` | float | 600.0 seconds |
| `docker_image` | str or None | None |
| `os` | `"linux"` / `"windows"` | `"linux"` |
| `cpus` | int or float or None | None |
| `memory_mb`, `storage_mb`, `gpus` | int or None, each | None |
| `gpu_types` | list[str] or None | None; any acceptable type |
| `tpu` | TpuSpec or None | None |
| `mcp_servers` | list[MCPServerConfig] | [] |
| `env` | dict[str, str] | {}; supports `${VAR}` and `${VAR:-default}` host resolution |
| `skills_dir` | str or None | None |
| `healthcheck` | HealthcheckConfig or None | None |
| `workdir` | str or None | None; otherwise container WORKDIR |
| `network_mode` | NetworkMode | `"public"` |
| `allowed_hosts` | list[str] or None | None |
| `allow_internet` | bool or None | None; deprecated compatibility input, excluded from dumps |

Sources: [baseline networking](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L250-L272), [environment](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L435-L490). NetworkMode is `no-network`, `public`, or `allowlist`; host entries support exact/wildcard hostnames, IP literals and CIDRs, with validation. [Modes and host validation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L40-L212). Missing resource declarations are not promises of a fixed CPU/RAM allocation: runtime overrides and provider enforcement decide effective behavior. [Resource resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/base.py#L400-L557).

### Nested models and steps

| Model | Complete fields: type = default |
|---|---|
| `HealthcheckConfig` | `command: str` required; `interval_sec: float = 5.0`; `timeout_sec: float = 30.0`; `start_period_sec: float = 0.0`; `start_interval_sec: float = 5.0`; `retries: int = 3` |
| `TpuSpec` | `type: str` required/nonempty; `topology: str` required, validated dimension string; chip count is computed, not a TOML field |
| `MCPServerConfig` | `name: str` required; `transport: "stdio" / "sse" / "streamable-http" = "sse"`; `url: str or None = None`; `command: str or None = None`; `args: list[str] = []`; `headers: dict[str,str] = {}` |
| `ArtifactConfig` | `source: str` required; `destination: str or None = None`; `exclude: list[str] = []`; `service: str or None = None` (main container) |
| `VerifierCollectConfig` | `command: str` required; `service: str = "main"`; `timeout_sec: float = 60.0`; `user: str or int or None = None` |
| `StepConfig` (`[[steps]]`) | `name: str` required/unique portable directory name; `agent: AgentConfig` default model; `verifier: VerifierConfig` default model; `min_reward: float or dict[str,float] or None = None`; `healthcheck: HealthcheckConfig or None = None`; `artifacts: list[str or ArtifactConfig] = []` |

Sources: [healthcheck and TPU](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L351-L422), [MCP validation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L632-L680), [artifacts](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L692-L775), [collection and steps](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L778-L843). MCP HTTP transports require `url`, stdio requires `command`; `http` is normalized to `streamable-http`. Artifact destinations are relative and cannot escape or replace the manifest. A step's min_reward gates continuation, not validity of the overall numeric reward domain.

Legacy inputs: root `version` migrates to `schema_version`; environment `memory`/`storage` size strings migrate to MB fields, with conflicts rejected; deprecated `allow_internet` maps to public/no-network only if modern settings are absent. [Migrations](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L505-L570), [version/network migration](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L896-L965). `metadata` is intentionally arbitrary; lint options live at `metadata.harbor.lint` (`select`, `extend-select`, `ignore`), not new fixed root fields. [Lint config](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/lint.py#L28-L67), [lint model](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/models.py#L58-L73).

**Initializer versus parser:** schema omission resolves shared verification, but `_init_task` explicitly writes separate mode by default. Initializer/template timeouts also differ from the bare model. Do not infer omitted defaults from a generated example. [Initializer](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/init.py#L120-L157), [template](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/template-task/task.toml#L1-L12), [mode resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/verifier_mode.py#L15-L69).

## 2. Trial lifecycle (numbered diagram)

1. **Load and select implementation:** `await Trial.create(TrialConfig(...))` loads/resolves the task, checks configuration and selects `SingleStepTrial`, `MultiStepTrial`, or regrade implementation. [Trial.create](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L469-L550).
2. **Prepare/build/pull/start:** `Trial.run` calls `_prepare` → `_setup_agent_environment` → `_start_agent_environment` → provider `start`. Docker's `DockerEnvironment.start` chooses prebuilt versus build, runs Compose build when needed, removes stale session containers, then Compose up; prebuilt image availability/pulling is delegated to Compose. Local task Compose can change the resulting service configuration. [Preparation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L601-L667), [environment start](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1845-L1864), [Docker start](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker.py#L1014-L1097), [prebuilt selection](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/definition.py#L26-L36), [Compose merge order](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker.py#L360-L434).
3. **Readiness and installation:** `_prepare` runs environment healthcheck, uploads injected skills, and calls `_setup_agent` → `agent.setup` with configured agent user. Agent setup has its own timeout. [Preparation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L641-L658), [agent setup](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1880-L1894).
4. **Execute agent:** `SingleStepTrial._run_agent` → `Trial._run_agent_phase` → `agent.run`, with instruction, context, user, environment overlays and phase network policy. Timeout/nonzero installed-agent exits are recorded; those cases can still proceed to grading. [Single-step agent](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/single_step.py#L74-L86), [phase execution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L700-L785).
5. **Collect evidence:** upload agent logs; collect artifact files and configured collection hooks. In separate mode stop main service before sidecar evidence collection, then stop the agent environment before verifier start. [Single-step ordering](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/single_step.py#L36-L54), [phased collection](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1591-L1684).
6. **Verify:** `_run_verifier` chooses `_run_shared_verifier` (same environment) or `_run_separate_verifier` (fresh environment, collected artifacts uploaded). `VerifierFactory` selects the verifier; standard `Verifier.verify` clears stale reward files, stages tests unless bundled, marks the entry script executable, and executes it. [Dispatch](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/single_step.py#L88-L110), [verifier environments](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L981-L1134), [standard verifier](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L167-L272).
7. **Read reward:** use mounted verifier logs or download them; prefer `reward.json` to `reward.txt`; return `VerifierResult`. Exceptions are recorded in trial results rather than silently becoming zero rewards. [Reward collection](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L274-L310), [exception/finalization handling](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L601-L678).
8. **Teardown and persist:** shared mode stops the environment after verification; separate verifier context stops its own environment in `finally`; finalization closes bridges, stops agent environment idempotently, writes `result.json`, and emits END. [Ordering](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/single_step.py#L36-L60), [separate cleanup](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1084-L1134), [finalization](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L660-L667). Runtime `environment.delete` defaults true. [Runtime configuration](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py#L218-L245).

Effective deadlines combine task values, runtime overrides/caps and multipliers; agent default None is distinct from verifier/build defaults of 600 seconds. Base agent setup default is 360 seconds. [Timeout resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1686-L1732), [setup constant](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/agents/base.py#L60-L65). This list describes single-step execution; multi-step trials reuse the agent environment across configured steps and can aggregate/gate rewards. [Multi-step implementation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/multi_step.py#L1-L220).

## 3. Verifier placement, file timing, ownership, reset

| Configuration | Runtime placement |
|---|---|
| Neither mode nor verifier environment declared | Shared agent container |
| `environment_mode = "shared"`, no verifier environment | Shared agent container |
| `environment_mode = "separate"` | Fresh verifier environment; absent verifier-specific definition, reuse clean agent image/configuration |
| Verifier environment declared, mode omitted | Separate |
| Shared mode plus verifier environment | Configuration error |

[Resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/verifier_mode.py#L15-L69), [configuration consistency](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L580-L629). For separate mode, verifier-specific image or tests build definition wins; an image/build that bundles tests skips test upload and must supply the expected `/tests/test.sh`. Otherwise tests are uploaded after the verifier container starts. Collected artifacts carry outputs into separate grading; the changed agent filesystem is not automatically cloned. [Definition precedence](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/verifier_mode.py#L89-L133), [transfer](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1013-L1081), [bundled tests path](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L126-L142).

In shared mode, tests are uploaded to `/tests` **after the agent phase**, inside `Verifier.verify`, rather than mounted into the agent by that path. The implementation removes stale reward files and overlays tests; it does **not** reset the general filesystem, restore installed executables, or replace the container before shared grading. Separate mode empties the verifier log directory before transfer/grading. These are code-path observations, not a proof that an arbitrary task image is free of leaked tests or answers. [Verifier staging and cleanup](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L167-L223), [shared path](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L981-L1011), [separate log reset](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1037-L1066).

Multi-step qualification: before the next agent/setup phase, a preceding shared verifier causes `_prepare_step` to clear its tests and grading outputs. That is a targeted between-step cleanup, not a fresh general agent filesystem. [Step preparation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/multi_step.py#L149-L170).

**Linux Docker ownership/permissions:** normal directory upload uses `docker compose cp source/. main:/tests`, without `-a` or a verifier-specific chown. Its fallback builds a tar with UID/GID 0, preserves source modes, and extracts as root. The verifier explicitly runs `chmod +x` on the entry script as root; it does not impose a recursive read-only permission scheme. Filtered staging tries to preserve metadata. Consequently there is no Harbor-wide numeric mode or owner guarantee covering every provider, source tree and pre-existing target. Exact normal-path Docker ownership and resulting modes were **UNVERIFIED at runtime**; inspect the actual container for an audit. [Docker transfer](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker_unix.py#L25-L32), [tar fallback](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker_unix.py#L70-L118), [normal copy](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker_unix.py#L152-L179), [chmod](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L261-L272), [filtered metadata](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/utils/file_staging.py#L15-L98).

The agent environment also gets writable log/artifact mounts, including `/logs/verifier`; directory preparation uses `chmod 777` for writable mount roots on Linux. Fresh verifier execution and late test upload therefore should not be treated as a complete audit of the evidence channel. **Inference:** Hackproof must assess mounts and collected inputs as well as container separation. [Agent mounts](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L2063-L2096), [directory creation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/base.py#L716-L738), [Docker preparation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker.py#L1091-L1097).

## 4. Execution user and network

Agent setup/run use `agent.user`; verifier execution uses `verifier.user`; each defaults None, meaning the image/Compose USER rather than an unconditional root override. A root-default image yields root execution; an image with another USER yields that user. Explicit per-step user settings can override task settings in multi-step mode. Utility staging/cleanup commands may explicitly use root independently of the agent/verifier user. [Schema](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L339-L348), [verifier user](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L580-L586), [user scoping](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/base.py#L560-L582), [Docker exec user](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker.py#L1355-L1371), [Docker command](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker.py#L1403-L1425), [single-step dispatch](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/single_step.py#L74-L108).

Network is public by default. A task can set baseline `environment.network_mode` and optional allowlist; agent/verifier sections can override the phase policy independently. A separate verifier can also declare its own environment baseline. Runtime allowlist additions and inference endpoint allowances can modify effective policy; provider support is validated, and unsupported dynamic transitions can fail instead of silently enforcing them. [Baseline/phase fields](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/config.py#L222-L272), [policy resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/network_policy.py#L130-L184), [inference allowances](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/network_policy.py#L24-L73), [provider transition validation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L285-L415). **UNVERIFIED:** live network enforcement on Docker or other providers; no connectivity probes were run.

## 5. Reward contract and failure handling

Standard paths are `/logs/verifier/reward.txt` and `/logs/verifier/reward.json`; the text form is one float (e.g. `1.0`), producing `{"reward": 1.0}`; JSON is a metric-name object (e.g. `{"reward": 1.0, "accuracy": 0.75}`). The result model expects `dict[str, float | int]`. [Environment paths](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/paths.py#L1-L170), [parser](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L69-L124), [result model](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/verifier/result.py#L1-L5).

| Condition | Standard verifier behavior |
|---|---|
| Both files exist | JSON wins; no fallback to text if JSON is malformed. |
| Neither exists | `RewardFileNotFoundError`. |
| Selected file has zero bytes | `RewardFileEmptyError`; whitespace-only text instead fails parsing. |
| Invalid text float or invalid JSON | `VerifierOutputParseError`. |
| NaN, infinity, numeric overflow to infinity | Explicitly rejected in both parsers. |
| JSON string, list, null, nested object as a value | Rejected by numeric checks; top-level numeric scalar gets past that check but fails the final dictionary result model. |
| Finite negative or >1 | No range check or clamping in this path; accepted numerically. |
| Empty JSON object | No explicit nonempty-dictionary check. |
| JSON boolean values | Python bool passes the `int` type check; no explicit boolean rejection. Final Pydantic handling is **UNVERIFIED at runtime**. |
| Nonzero test process exit | Standard verifier does not use the returned exit code to decide reward; reward parsing still determines the result unless execution itself raises. |

Sources: [parse details](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L69-L124), [execution and file precedence](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L267-L310), [typed result](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/verifier/result.py#L1-L5). A parse/missing-file error becomes trial `exception_info`; callers must distinguish infrastructure/verifier failure from legitimate zero reward. [Trial error recording](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L601-L678). These conclusions concern the standard verifier; a configured custom verifier can define other behavior. [Verifier factory](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/factory.py#L1-L99).

## 6. Oracle and no-op agents; exact single-task CLI

Both exist: `OracleAgent.name()` is `oracle`; it uploads `solution/` to `/solution`, executes the OS-compatible solve script, and logs its output. `NopAgent` is `nop`; setup and run do nothing. Neither implementation calls an LLM. [Oracle](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/agents/oracle.py#L20-L159), [no-op](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/agents/nop.py#L9-L32).

For an installed checkout of the pinned Harbor version, a Linux task directory and a local Docker service:

```sh
harbor run --path /absolute/path/to/task --agent oracle --env docker --n-attempts 1
harbor run --path /absolute/path/to/task --agent nop --env docker --n-attempts 1
```

`--path` must name one task directory, not a dataset directory, to select exactly one task. These are source-verified CLI forms, **not executed in this session**. `harbor run` aliases job start; the flag definitions are [path](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/jobs.py#L1143-L1152), [agent](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/jobs.py#L617-L633), [environment](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/jobs.py#L868-L882), [attempt count](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/jobs.py#L482-L493), [alias](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/main.py#L164-L171). No model/API key is needed by these agents themselves, but arbitrary task/verifier scripts and declared host-variable requirements can introduce dependencies or costs; choose a self-contained task before running. [Task environment access](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/jobs.py#L169-L201), [verifier env](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L229-L243).

## 7. Minimal programmatic trial

Use the async factory rather than assuming direct `Trial(...)` construction is sufficient. It chooses the correct concrete implementation and loads task provenance. [Factory](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L469-L525), [configuration models](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py#L398-L457), [trial fields](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/trial/config.py#L488-L513).

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
            agent=AgentConfig(name="nop"),  # or "oracle"
            environment=EnvironmentConfig(type="docker"),
            trials_dir=Path("./trials"),
        )
    )
    result = await trial.run()
    print(result.verifier_result, result.exception_info)


if __name__ == "__main__":
    asyncio.run(main())
```

Source-derived example; **UNVERIFIED by execution**. `Trial.run` returns a result even for many exceptions, so checking rewards alone is insufficient. [Run/error contract](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L601-L678).

## 8. Datasets, registry, cache, Terminal-Bench license

Source-verified command forms (not run):

```sh
harbor datasets list --legacy
harbor datasets download terminal-bench@2.0 --output-dir /absolute/path/to/datasets
harbor datasets download terminal-bench@2.0 --cache
```

Plain `datasets list` now prints a registry website link; `--legacy` lists the table. Download defaults to **export mode**, current directory if no output is supplied, with a dataset/task layout; `--cache` requests cache mode. [List implementation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/datasets.py#L27-L99), [download options and defaults](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/datasets.py#L166-L266), [dataset export handling](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/download.py#L1-L260).

The default registry factory creates `HarborRegistryClient` (Supabase-backed), not simply a fetch of `registry.json`. Explicit JSON registry paths/custom URLs and Git registry repositories have separate clients. The old default JSON URL remains in constants, but the factory maps that default URL to HarborRegistryClient too. [Factory](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/registry/client/factory.py#L10-L45), [Harbor backend](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/registry/client/harbor/harbor.py#L108-L160), [JSON registry](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/registry/client/json.py#L15-L72), [constants](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/constants.py#L4-L17). No live registry query or authentication was performed.

For Git task IDs, `TasksClient` clones to a temporary directory using shallow/sparse checkout, resolves/fetches requested commits, optionally handles Git LFS, and materializes task trees into the output/cache. Cache root is `~/.cache/harbor/tasks`; Git entries use `<shortuuid(str(task_id))>/<task-directory-name>`. Reuse requires a resolved commit and existing nonempty tree; mutable references can trigger refresh. Package tasks use downloaded archives with content hashes, under `~/.cache/harbor/tasks/packages/<org>/<name>/<digest>` for their default local path; client output-root overrides can change the prefix. [Git download](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/tasks/client.py#L233-L343), [reuse/layout](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/tasks/client.py#L491-L517), [package download](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/tasks/client.py#L368-L460), [IDs/local paths](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/id.py#L1-L74), [client root](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/tasks/client.py#L586-L603).

The checked-in legacy registry's `terminal-bench@2.0` entry pins task source to `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c` in `laude-institute/terminal-bench-2` (now redirected to `harbor-framework/terminal-bench-2`). This is checked-in registry evidence, **not confirmation of today's live registry mapping**. [Pinned entry](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/registry.json#L94011-L94026), [official dataset repository](https://github.com/harbor-framework/terminal-bench-2).

Current Terminal-Bench 2 repository license is **Apache-2.0** (current HEAD observed `2fd12b88aafdd04a52c298e3940bcb189f9766d6`). [License](https://github.com/harbor-framework/terminal-bench-2/blob/2fd12b88aafdd04a52c298e3940bcb189f9766d6/LICENSE#L1-L176). **UNVERIFIED:** license at the older exact registry task commit: opening its raw LICENSE returned HTTP 404. Current licensing should not be retroactively assumed for every embedded dataset, external download, base image, or historical task revision; those require their own provenance review.

## 9. Harbor license and auditor reuse

Harbor's repository LICENSE is **Apache-2.0**. It grants reproduction, derivative-work and distribution rights; redistribution conditions include providing the license, marking changed files, preserving relevant notices, and carrying applicable NOTICE attributions. It has a patent termination clause and does not grant general trademark rights. **Source-based inference:** the reviewed license contains no auditor-specific prohibition and permits building a third-party adapter/auditor subject to those conditions. This does not establish terms for hosted services, third-party images or datasets. [Harbor license](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/LICENSE#L66-L141). **UNVERIFIED:** separate hosted-service contractual terms; they were not needed or accepted for this local source review.

## 10. Existing validation and gaps

Harbor already exposes `harbor lint /path/to/task --json` and optional `--select ALL`. It statically checks files; it does not run the task or prove oracle correctness. Default rules include invalid configuration, unknown fields, invalid layout/files, shared verifier, overlapping artifacts, artifact/log overlap, dangerous Compose privileges/capabilities/bind mounts, unpinned Python dependencies, verifier runtime installs/downloads, and possible test/solution leakage into the agent image. `root-agent` and `unpinned-image` exist but **are not in DEFAULT_RULES**. Source heuristics cannot establish complete runtime isolation. [Rules/defaults](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/models.py#L7-L55), [CLI/exit status](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/lint.py#L70-L146), [task validation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/task.py#L615-L695), [root/shared checks](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/task.py#L255-L294), [source checks](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/task.py#L444-L595).

`harbor check <task-dir>` is a separate **agent/LLM-based rubric review**, defaulting to Claude Code and a model; it was not run. The legacy `harbor task check` is removed and directs callers to this command. Rubric criteria cover instruction/test agreement in both directions, informative tests, anti-cheating, structured schemas, pinned dependencies, typos, tests/solutions in images, test dependency placement, hardcoded solutions, and explicit output filenames. [Check implementation](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/analyze.py#L84-L175), [legacy removal](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/tasks.py#L515-L545), [complete rubric](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/quality_checker/default-rubric.toml#L1-L54). One rubric recommendation about installing test dependencies during verification differs from lint's runtime-install warning; treat these as independent policy layers rather than consistent security guarantees.

Oracle evaluation is available through the normal harness and can be repeated with `--n-attempts`. The reviewed oracle implementation does not assert that rewards must equal one: nonzero solve exit is recorded in `exit-code.txt`; it still relies on downstream verification. **No automatic oracle-must-pass invariant was found in the reviewed trial/agent/lint/check paths.** Adapter review guidance asks for 100% oracle success, which is an author workflow requirement, not proof that every normal run enforces it. [Oracle exit handling](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/agents/oracle.py#L124-L159), [review guidance](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/adapter_review.py#L30-L45), [trial flow](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/single_step.py#L36-L110). **UNVERIFIED:** exhaustive absence of such checks across all external CI/services.

## Implications for the Hackproof adapter

These are engineering conclusions from the linked implementation, not measured findings about particular tasks.

- Reuse `Trial.create`/`run`, typed results and output directories; inspect `exception_info` separately from reward so verifier failures cannot count as successful zero baselines. [Run contract](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L601-L678).
- Reuse `oracle` and `nop` for deterministic local baselines; add explicit oracle-pass and no-op-zero assertions, repetitions and uncertainty calculations in Hackproof. Harbor's utility agents do not enforce those statistical properties. [Agents](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/agents/oracle.py#L124-L159), [nop](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/agents/nop.py#L9-L32).
- Determine effective verifier mode from configuration resolution, including steps; late test upload alone is not isolation. Preserve the task's grading semantics when reporting shared-mode risk. [Mode resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/models/task/verifier_mode.py#L15-L79).
- Reuse separate verifier/artifact transfer where appropriate; independently check artifact provenance, mounts and permitted output paths because fresh containers still consume agent-produced evidence. [Transfer](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1013-L1081), [agent mounts](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L2063-L2096).
- Reuse lint findings, with recorded rule selection/version; explicitly enable root/image rules if required. Add runtime image-content and permission checks because syntax heuristics do not prove absence of hidden tests/reference data. [Lint defaults](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/models.py#L7-L55).
- Validate reward metric names, expected range, nonempty output and failure status in the adapter; avoid assuming all finite Harbor rewards are probabilities or binary success. [Parser](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/verifier/verifier.py#L69-L124).
- Record actual agent/verifier users, effective network policy, image identity and trial overrides; omitted config is not enough to describe the sandbox boundary. [Policy resolution](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/network_policy.py#L130-L184), [execution users](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/environments/docker/docker.py#L1355-L1371).
- Pin Harbor and task source revisions/content hashes and license provenance; do not rely on mutable registry head or cache directory names as complete reproducibility records. [Task downloads](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/tasks/client.py#L491-L517), [trial lock](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/trial/trial.py#L1203-L1212).
- Implement near-miss/mutation adequacy, repeated reference-solution reliability, content-neutral judge stability and training-difficulty calibration as explicit Hackproof checks; the reviewed static lint and rubric paths do not establish these properties. [Lint](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/lint/task.py#L615-L695), [rubric](https://github.com/harbor-framework/harbor/blob/872da9479f4a2078142d22c49c9ffae0f09e2e63/src/harbor/cli/quality_checker/default-rubric.toml#L1-L54). Keep all findings at defect-class/detection/remediation level.
