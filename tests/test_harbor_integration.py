"""End-to-end run through Harbor and Docker.

Slow and needs Docker plus the `harbor` extra, so it only runs when asked:
    HACKPROOF_DOCKER_TESTS=1 uv run --extra harbor pytest tests/test_harbor_integration.py
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("HACKPROOF_DOCKER_TESTS") != "1",
    reason="set HACKPROOF_DOCKER_TESTS=1 to run Docker-backed tests",
)

COUNT_LINES = Path(__file__).parent / "fixtures" / "harbor" / "count-lines"


def test_fixture_oracle_passes_and_nop_scores_zero(tmp_path):
    pytest.importorskip("harbor")
    from hackproof.adapters import harbor
    from hackproof.runners.harbor import HarborRunner

    task = harbor.load_task(COUNT_LINES)
    runner = HarborRunner(tmp_path)
    oracle = runner.run(task, "oracle", attempt=0)
    nop = runner.run(task, "nop", attempt=0)

    assert oracle.counted and oracle.reward == 1.0, oracle
    assert nop.counted and nop.reward == 0.0, nop
    assert oracle.verifier_mode == "shared"
