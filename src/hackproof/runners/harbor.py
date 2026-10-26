"""Run tasks through Harbor's own trial machinery (Harbor 0.25).

Reusing `Trial.create` / `Trial.run` keeps Harbor's exact semantics: image build, agent phase,
verifier placement, reward parsing and teardown. See docs/research/harbor-api.md.
Install with: uv sync --extra harbor
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from hackproof.model import Task
from hackproof.runners.base import RunResult

REWARD_KEY = "reward"


class HarborNotInstalledError(RuntimeError):
    pass


class HarborRunner:
    name = "harbor"

    def __init__(self, workdir: Path, *, environment: str = "docker") -> None:
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
        self.trials_dir = (workdir / "trials").resolve()
        self.trials_dir.mkdir(parents=True, exist_ok=True)

    def run(self, task: Task, agent: str, *, attempt: int) -> RunResult:
        trial_name = f"{task.id}--{agent}--{attempt}--{uuid.uuid4().hex[:8]}"
        config = self._trial_config(
            task=self._task_config(path=task.root),
            agent=self._agent_config(name=agent),
            environment=self._environment_config(type=self.environment),
            trials_dir=self.trials_dir,
            trial_name=trial_name,
        )
        started = time.perf_counter()
        try:
            result = asyncio.run(self._run(config))
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

    async def _run(self, config):
        trial = await self._trial.create(config)
        return await trial.run()


def _convert(result, agent: str, attempt: int, duration: float) -> RunResult:
    rewards = (result.verifier_result.rewards or {}) if result.verifier_result else {}
    reward = rewards.get(REWARD_KEY)
    if reward is None and len(rewards) == 1:
        reward = next(iter(rewards.values()))
    error = None
    if result.exception_info is not None:
        info = result.exception_info
        error = f"{info.exception_type}: {info.exception_message}"
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
