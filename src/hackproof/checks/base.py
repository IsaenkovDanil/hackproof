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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "property": self.property,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "evidence": self.evidence,
            "fix": self.fix,
        }
