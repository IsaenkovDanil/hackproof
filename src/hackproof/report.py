"""Machine-readable audit reports (explainer, section 9)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from hackproof import __version__
from hackproof.checks.base import CheckResult, Verdict, worst
from hackproof.model import Task

SCHEMA_VERSION = 1


def build_report(task: Task, checks: list[CheckResult], *, runner: str) -> dict[str, Any]:
    counts = Counter(c.verdict.value for c in checks)
    return {
        "schema": SCHEMA_VERSION,
        "tool": f"hackproof {__version__}",
        "runner": runner,
        "task": {"id": task.id, "format": task.format, "sha256": task.digest},
        "checks": [c.to_dict() for c in checks],
        "summary": {
            "verdict": worst(c.verdict for c in checks).value,
            "counts": {v.value: counts.get(v.value, 0) for v in Verdict},
        },
    }
