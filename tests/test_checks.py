import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hackproof import cli
from hackproof.adapters import harbor
from hackproof.checks import Verdict, check_nop_baseline, check_reference_reliability, worst
from hackproof.report import build_report
from tests.fakes import ERROR, ScriptedRunner

COUNT_LINES = Path(__file__).parent / "fixtures" / "harbor" / "count-lines"


@pytest.fixture
def task():
    return harbor.load_task(COUNT_LINES)


# --- P1: no-op baseline -------------------------------------------------------------


def test_nop_zero_is_ok(task):
    result = check_nop_baseline(task, ScriptedRunner({"nop": [0]}), runs=2)
    assert result.verdict is Verdict.OK
    assert result.evidence["rewards"] == [0.0, 0.0]


def test_nop_paid_is_fail(task):
    result = check_nop_baseline(task, ScriptedRunner({"nop": [0, 1]}), runs=2)
    assert result.verdict is Verdict.FAIL
    assert "1 of 2" in result.summary
    assert result.fix


def test_nop_partial_credit_is_fail(task):
    result = check_nop_baseline(task, ScriptedRunner({"nop": [0.3]}), runs=1)
    assert result.verdict is Verdict.FAIL


def test_nop_verifier_errors_are_not_zero(task):
    only_errors = check_nop_baseline(task, ScriptedRunner({"nop": [ERROR]}), runs=2)
    assert only_errors.verdict is Verdict.UNKNOWN
    mixed = check_nop_baseline(task, ScriptedRunner({"nop": [0, ERROR]}), runs=2)
    assert mixed.verdict is Verdict.WARN


# --- P5: reference reliability -----------------------------------------------------


def test_stable_reference_needs_31_runs(task):
    runner = ScriptedRunner({"oracle": [1]})
    result = check_reference_reliability(task, runner, max_runs=50)
    assert result.verdict is Verdict.OK
    assert runner.calls["oracle"] == 31
    assert result.evidence["sprt"]["decision"] == "accept_h0"


def test_too_few_clean_runs_is_unknown(task):
    result = check_reference_reliability(task, ScriptedRunner({"oracle": [1]}), max_runs=5)
    assert result.verdict is Verdict.UNKNOWN
    # Wilson upper bound for 0 failures in 5 runs.
    assert result.evidence["failure_rate_ci95"] == [0.0, 0.4345]


def test_broken_reference_fails_after_two_runs(task):
    runner = ScriptedRunner({"oracle": [0]})
    result = check_reference_reliability(task, runner, max_runs=31)
    assert result.verdict is Verdict.FAIL
    assert runner.calls["oracle"] == 2
    assert "Pin dependency versions" in result.fix


def test_flaky_reference_warns(task):
    runner = ScriptedRunner({"oracle": [1, 1, 0, 1, 1, 0, 1]})
    result = check_reference_reliability(task, runner, max_runs=31)
    assert result.verdict is Verdict.WARN
    assert result.evidence["failures"] == 2


def test_reference_errors_are_not_failures(task):
    runner = ScriptedRunner({"oracle": [ERROR]})
    result = check_reference_reliability(task, runner, max_runs=31)
    assert result.verdict is Verdict.UNKNOWN
    assert runner.calls["oracle"] == 3


def test_missing_solution_is_unknown(tmp_path):
    shutil.copytree(COUNT_LINES, tmp_path / "t")
    shutil.rmtree(tmp_path / "t" / "solution")
    task = harbor.load_task(tmp_path / "t")
    runner = ScriptedRunner({"oracle": [1]})
    assert check_reference_reliability(task, runner).verdict is Verdict.UNKNOWN
    assert runner.calls["oracle"] == 0


# --- summary, report and CLI -------------------------------------------------------


def test_worst_verdict_order():
    assert worst([Verdict.OK, Verdict.UNKNOWN]) is Verdict.UNKNOWN
    assert worst([Verdict.UNKNOWN, Verdict.WARN]) is Verdict.WARN
    assert worst([Verdict.WARN, Verdict.FAIL, Verdict.OK]) is Verdict.FAIL
    assert worst([]) is Verdict.UNKNOWN


def test_report_shape(task):
    runner = ScriptedRunner({"nop": [0], "oracle": [0]})
    checks = [check_nop_baseline(task, runner), check_reference_reliability(task, runner)]
    report = build_report(task, checks, runner=runner.name)
    assert report["task"] == {"id": "count-lines", "format": "harbor", "sha256": task.digest}
    assert report["summary"] == {
        "verdict": "fail",
        "counts": {"ok": 1, "warn": 0, "fail": 1, "unknown": 0},
    }
    json.dumps(report)  # serialisable


@pytest.mark.parametrize(
    ("scripts", "exit_code", "verdict"),
    [
        ({"nop": [0], "oracle": [1]}, 0, "unknown"),  # 3 clean runs: too few to decide
        ({"nop": [1], "oracle": [1]}, 1, "fail"),
    ],
)
def test_cli_audit(monkeypatch, tmp_path, scripts, exit_code, verdict):
    monkeypatch.setattr(cli, "_make_runner", lambda workdir: ScriptedRunner(scripts))
    out = tmp_path / "reports"
    result = CliRunner().invoke(
        cli.app, ["audit", str(COUNT_LINES), "--out", str(out), "--oracle-runs", "3"]
    )
    assert result.exit_code == exit_code, result.output
    report = json.loads((out / "count-lines.json").read_text())
    assert report["summary"]["verdict"] == verdict
    assert "baseline.nop" in result.output
