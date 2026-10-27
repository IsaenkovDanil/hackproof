"""Harbor runner logic that does not need Harbor or Docker installed."""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from hackproof.adapters import harbor
from hackproof.runners.harbor import _convert, trial_limits

COUNT_LINES = Path(__file__).parent / "fixtures" / "harbor" / "count-lines"
LIMITS = {"default_agent_timeout_sec": 1800.0, "min_trial_deadline_sec": 3600.0}


def test_task_limits_are_respected():
    # Fixture: agent 120 s, verifier 60 s, build default 600 s.
    override, deadline = trial_limits(harbor.load_task(COUNT_LINES), **LIMITS)
    assert override is None
    assert deadline == 3600.0


def test_missing_agent_limit_gets_a_default(tmp_path):
    # Finding 4: Harbor runs an agent without a deadline when the task declares none.
    shutil.copytree(COUNT_LINES, tmp_path / "t")
    toml = tmp_path / "t" / "task.toml"
    toml.write_text(toml.read_text().replace("[agent]\ntimeout_sec = 120\n", ""))
    override, deadline = trial_limits(harbor.load_task(tmp_path / "t"), **LIMITS)
    assert override == 1800.0
    # 1800 + 60 + 600 + 900 = 3360 is below the 3600 s floor.
    assert deadline == 3600.0


def test_deadline_grows_with_long_task_limits(tmp_path):
    shutil.copytree(COUNT_LINES, tmp_path / "t")
    toml = tmp_path / "t" / "task.toml"
    toml.write_text(toml.read_text().replace("timeout_sec = 120", "timeout_sec = 7200"))
    _, deadline = trial_limits(harbor.load_task(tmp_path / "t"), **LIMITS)
    assert deadline == 7200 + 60 + 600 + 900


def _result(rewards=None, exception=None, valid=True):
    return SimpleNamespace(
        verifier_result=SimpleNamespace(rewards=rewards) if rewards is not None else None,
        exception_info=exception,
        reward_valid=valid,
        trial_uri="file:///tmp/trials/x",
        verifier_environment_mode="shared",
    )


def test_convert_reads_reward_key():
    run = _convert(_result({"reward": 1}), "oracle", 0, 1.5)
    assert (run.reward, run.counted, run.error) == (1.0, True, None)
    assert run.trial_dir == Path("/tmp/trials/x")


def test_convert_single_other_metric_is_used():
    assert _convert(_result({"accuracy": 0.3}), "oracle", 0, 1.0).reward == 0.3


def test_convert_ambiguous_metrics_are_not_counted_and_explained():
    run = _convert(_result({"accuracy": 1, "style": 0.5}), "oracle", 0, 1.0)
    assert not run.counted
    assert "no 'reward' metric" in run.error


def test_convert_verifier_failure_is_never_a_zero():
    exc = SimpleNamespace(exception_type="VerifierTimeoutError", exception_message="slow")
    run = _convert(_result({"reward": 0}, exception=exc, valid=False), "nop", 0, 1.0)
    assert not run.counted
    assert run.error == "VerifierTimeoutError: slow"


@pytest.mark.parametrize("value", [True, "120", None])
def test_non_numeric_limits_are_ignored(tmp_path, value):
    shutil.copytree(COUNT_LINES, tmp_path / "t")
    toml = tmp_path / "t" / "task.toml"
    replacement = (
        ""
        if value is None
        else f"timeout_sec = {str(value).lower() if value is True else repr(value)}"
    )
    toml.write_text(toml.read_text().replace("timeout_sec = 120", replacement.replace("'", '"')))
    override, _ = trial_limits(harbor.load_task(tmp_path / "t"), **LIMITS)
    assert override == 1800.0
