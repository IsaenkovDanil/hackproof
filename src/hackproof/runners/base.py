"""Runner interface shared by all execution backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hackproof.model import Task

# Built-in agents every backend must provide.
ORACLE = "oracle"  # runs the task's reference solution
NOP = "nop"  # does nothing


@dataclass(frozen=True)
class RunResult:
    """Outcome of one trial.

    `reward_valid` is False when the trial failed in a way that makes the reward meaningless
    (environment, verifier or reward-file errors). Such runs are never counted as a zero
    reward: a grader that crashes has not graded anything.
    """

    agent: str
    attempt: int
    reward: float | None
    reward_valid: bool
    error: str | None = None
    duration_sec: float | None = None
    verifier_mode: str | None = None
    trial_dir: Path | None = None

    @property
    def counted(self) -> bool:
        return self.reward_valid and self.reward is not None


class Runner(Protocol):
    name: str

    def run(self, task: Task, agent: str, *, attempt: int) -> RunResult: ...
