from typer.testing import CliRunner

from hackproof import __version__
from hackproof.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_stats_wilson():
    result = runner.invoke(app, ["stats", "wilson", "0", "20"])
    assert result.exit_code == 0
    assert "[0.0000, 0.1611]" in result.output


def test_stats_posterior_with_threshold():
    result = runner.invoke(app, ["stats", "posterior", "0", "10", "--below", "0.02"])
    assert result.exit_code == 0
    assert "Beta(1, 11)" in result.output
    assert "P(rate < 0.02) = 0.1993" in result.output


def test_stats_pass_at_k():
    result = runner.invoke(app, ["stats", "pass-at-k", "10", "3", "5"])
    assert result.exit_code == 0
    assert "pass@5 = 0.9167" in result.output


def test_audit_without_tasks_is_a_tool_error(tmp_path):
    result = runner.invoke(app, ["audit", str(tmp_path)])
    assert result.exit_code == 2
