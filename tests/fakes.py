"""A scripted runner for testing checks without Docker."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from hackproof.model import Task
from hackproof.runners.base import RunResult

ERROR = object()  # script entry meaning "this run produced no valid reward"


class ScriptedRunner:
    """Returns rewards from a per-agent script; repeats the last entry when it runs out."""

    name = "scripted"

    def __init__(self, scripts: dict[str, Iterable[object]]) -> None:
        self.scripts = {agent: list(entries) for agent, entries in scripts.items()}
        self.calls: dict[str, int] = defaultdict(int)

    def run(self, task: Task, agent: str, *, attempt: int) -> RunResult:
        script = self.scripts[agent]
        entry = script[min(self.calls[agent], len(script) - 1)]
        self.calls[agent] += 1
        if entry is ERROR:
            return RunResult(agent, attempt, None, False, error="VerifierError: boom")
        return RunResult(agent, attempt, float(entry), True, verifier_mode="shared")
