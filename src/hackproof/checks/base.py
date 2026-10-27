"""Verdicts and the result every check returns."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Verdict(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"  # not enough evidence; reported, never rounded to ok


# Order used to summarise several verdicts: the most serious one wins.
_SEVERITY = {Verdict.OK: 0, Verdict.UNKNOWN: 1, Verdict.WARN: 2, Verdict.FAIL: 3}


def worst(verdicts: Iterable[Verdict]) -> Verdict:
    return max(verdicts, key=_SEVERITY.__getitem__, default=Verdict.UNKNOWN)


@dataclass(frozen=True)
class CheckResult:
    id: str
    property: str  # P1..P7 in docs/threat-model.md
    verdict: Verdict
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    fix: str | None = None
    # True when execution errors, not the task's behaviour, kept the check from deciding.
    incomplete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "property": self.property,
            "verdict": self.verdict.value,
            "incomplete": self.incomplete,
            "summary": self.summary,
            "evidence": self.evidence,
            "fix": self.fix,
        }


def run_record(result) -> dict[str, Any]:
    """Per-trial provenance kept in check evidence."""
    return {
        "agent": result.agent,
        "attempt": result.attempt,
        "reward": result.reward,
        "valid": result.counted,
        "error": result.error,
        "duration_sec": round(result.duration_sec, 3) if result.duration_sec else None,
        "verifier_mode": result.verifier_mode,
        "trial_dir": str(result.trial_dir) if result.trial_dir else None,
    }
