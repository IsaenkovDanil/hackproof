"""Run tasks through Harbor's own trial machinery (Harbor 0.25).

Reusing `Trial.create` / `Trial.run` keeps Harbor's exact semantics: image build, agent phase,
verifier placement, reward parsing and teardown. See docs/research/harbor-api.md.
Install with: uv sync --extra harbor

Two limits keep an audit from hanging. A task that declares no agent time limit gets
`default_agent_timeout_sec`; Harbor would otherwise run its agent without a deadline. Every
trial also runs under a wall-clock deadline that is never shorter than what the task's own
limits allow, so Hackproof cannot fail a run the task itself permits.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from hackproof.model import Task
from hackproof.runners.base import RunResult

REWARD_KEY = "reward"
# Harbor's defaults when a task does not set them (docs/research/harbor-internals.md).
HARBOR_DEFAULT_VERIFIER_SEC = 600.0
HARBOR_DEFAULT_BUILD_SEC = 600.0
SETUP_AND_TEARDOWN_ALLOWANCE_SEC = 900.0


class HarborNotInstalledError(RuntimeError):
    pass


class TrialDeadlineExceededError(RuntimeError):
    pass


class HarborRunner:
    name = "harbor"

    def __init__(
        self,
        workdir: Path,
        *,
        environment: str = "docker",
        default_agent_timeout_sec: float = 1800.0,
        min_trial_deadline_sec: float = 3600.0,
    ) -> None:
        try:
            from harbor.models.trial.config import (
                AgentConfig,
                EnvironmentConfig,
                TaskConfig,
                TrialConfig,
            )
            from harbor.trial.trial import Trial
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            raise HarborNotInstalledError(
                "Harbor is not installed; run `uv sync --extra harbor`"
            ) from exc
        self._agent_config = AgentConfig
        self._environment_config = EnvironmentConfig
        self._task_config = TaskConfig
        self._trial_config = TrialConfig
        self._trial = Trial
        self.environment = environment
        self.default_agent_timeout_sec = default_agent_timeout_sec
        self.min_trial_deadline_sec = min_trial_deadline_sec
        self.trials_dir = (workdir / "trials").resolve()
        self.trials_dir.mkdir(parents=True, exist_ok=True)

    def run(self, task: Task, agent: str, *, attempt: int) -> RunResult:
        trial_name = f"{task.id}--{agent}--{attempt}--{uuid.uuid4().hex[:8]}"
        agent_override, deadline = trial_limits(
            task,
            default_agent_timeout_sec=self.default_agent_timeout_sec,
            min_trial_deadline_sec=self.min_trial_deadline_sec,
        )
        config = self._trial_config(
            task=self._task_config(path=task.root),
            agent=self._agent_config(name=agent, override_timeout_sec=agent_override),
            environment=self._environment_config(type=self.environment),
            trials_dir=self.trials_dir,
            trial_name=trial_name,
        )
        started = time.perf_counter()
        try:
            result = asyncio.run(self._run(config, deadline))
        except Exception as exc:  # setup/factory errors raise before a result exists
            return RunResult(
                agent=agent,
                attempt=attempt,
                reward=None,
                reward_valid=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_sec=time.perf_counter() - started,
                trial_dir=self.trials_dir / trial_name,
            )
        return _convert(result, agent, attempt, time.perf_counter() - started)

    async def _run(self, config, deadline: float):
        trial = await self._trial.create(config)
        try:
            # Cancellation runs Harbor's own finally-blocks, so the trial is torn down first.
            return await asyncio.wait_for(trial.run(), timeout=deadline)
        except TimeoutError as exc:
            raise TrialDeadlineExceededError(f"trial exceeded {deadline:.0f} s") from exc


def trial_limits(
    task: Task, *, default_agent_timeout_sec: float, min_trial_deadline_sec: float
) -> tuple[float | None, float]:
    """(agent timeout override or None, wall-clock deadline) for one trial of `task`.

    The override is set only when the task declares no agent limit. The deadline covers the
    task's own agent, verifier and build limits plus setup and teardown, and is at least
    `min_trial_deadline_sec`.
    """
    agent_sec = _section_number(task, "agent", "timeout_sec")
    verifier_sec = _section_number(task, "verifier", "timeout_sec")
    build_sec = _section_number(task, "environment", "build_timeout_sec")
    needed = (
        (agent_sec if agent_sec is not None else default_agent_timeout_sec)
        + (verifier_sec if verifier_sec is not None else HARBOR_DEFAULT_VERIFIER_SEC)
        + (build_sec if build_sec is not None else HARBOR_DEFAULT_BUILD_SEC)
        + SETUP_AND_TEARDOWN_ALLOWANCE_SEC
    )
    override = None if agent_sec is not None else default_agent_timeout_sec
    return override, max(min_trial_deadline_sec, needed)


def _section_number(task: Task, section: str, key: str) -> float | None:
    value = task.config.get(section, {}).get(key)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _convert(result, agent: str, attempt: int, duration: float) -> RunResult:
    rewards = (result.verifier_result.rewards or {}) if result.verifier_result else {}
    reward = rewards.get(REWARD_KEY)
    if reward is None and len(rewards) == 1:
        reward = next(iter(rewards.values()))
    error = None
    if result.exception_info is not None:
        info = result.exception_info
        error = f"{info.exception_type}: {info.exception_message}"
    elif reward is None and rewards:
        error = f"no '{REWARD_KEY}' metric among {sorted(rewards)}"
    trial_dir = None
    if getattr(result, "trial_uri", None):
        trial_dir = Path(str(result.trial_uri).removeprefix("file://"))
    return RunResult(
        agent=agent,
        attempt=attempt,
        reward=float(reward) if reward is not None else None,
        reward_valid=bool(result.reward_valid) and reward is not None,
        error=error,
        duration_sec=duration,
        verifier_mode=getattr(result, "verifier_environment_mode", None),
        trial_dir=trial_dir,
    )
