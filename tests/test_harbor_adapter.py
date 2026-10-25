import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hackproof.adapters import harbor
from hackproof.cli import app
from hackproof.model import TaskFormatError, directory_digest

FIXTURES = Path(__file__).parent / "fixtures" / "harbor"
COUNT_LINES = FIXTURES / "count-lines"

runner = CliRunner()


@pytest.fixture
def task_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "count-lines"
    shutil.copytree(COUNT_LINES, dest)
    return dest


def test_load_fixture():
    task = harbor.load_task(COUNT_LINES)
    assert task.id == "count-lines"
    assert task.format == "harbor"
    assert "answer.txt" in task.instruction
    assert task.config["verifier"]["timeout_sec"] == 60
    assert task.has_solution
    assert task.files == (
        "environment/Dockerfile",
        "environment/data.txt",
        "instruction.md",
        "solution/solve.sh",
        "task.toml",
        "tests/test.sh",
    )
    assert len(task.digest) == 64


def test_digest_is_stable_and_content_sensitive(task_copy: Path):
    original = harbor.load_task(COUNT_LINES).digest
    assert harbor.load_task(task_copy).digest == original

    (task_copy / "environment" / "data.txt").write_text("alpha\nbeta\n")
    assert harbor.load_task(task_copy).digest != original


def test_digest_ignores_vcs_and_cache_litter(task_copy: Path):
    before = directory_digest(task_copy)
    (task_copy / "__pycache__").mkdir()
    (task_copy / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    (task_copy / ".DS_Store").write_bytes(b"\x00")
    assert directory_digest(task_copy) == before


def test_digest_distinguishes_renamed_files(task_copy: Path):
    before = directory_digest(task_copy)
    (task_copy / "environment" / "data.txt").rename(task_copy / "environment" / "data2.txt")
    assert directory_digest(task_copy) != before


def test_missing_solution_is_allowed(task_copy: Path):
    shutil.rmtree(task_copy / "solution")
    task = harbor.load_task(task_copy)
    assert not task.has_solution
    assert task.solution_dir is None


def test_every_problem_is_reported_at_once(task_copy: Path):
    (task_copy / "instruction.md").write_text("   \n")
    (task_copy / "task.toml").write_text("not = [valid")
    (task_copy / "environment" / "Dockerfile").unlink()
    (task_copy / "tests" / "test.sh").unlink()
    with pytest.raises(TaskFormatError) as info:
        harbor.load_task(task_copy)
    problems = info.value.problems
    assert len(problems) == 4
    assert any("instruction.md is empty" in p for p in problems)
    assert any("not valid TOML" in p for p in problems)
    assert any("environment/" in p for p in problems)
    assert any("tests/test.sh" in p for p in problems)


def test_compose_file_counts_as_environment(task_copy: Path):
    (task_copy / "environment" / "Dockerfile").unlink()
    (task_copy / "environment" / "docker-compose.yaml").write_text("services: {}\n")
    assert harbor.load_task(task_copy).id == "count-lines"


def test_discover_tasks(tmp_path: Path):
    shutil.copytree(COUNT_LINES, tmp_path / "b-task")
    shutil.copytree(COUNT_LINES, tmp_path / "a-task")
    (tmp_path / "not-a-task").mkdir()
    (tmp_path / "README.md").write_text("hi")
    assert [p.name for p in harbor.discover_tasks(tmp_path)] == ["a-task", "b-task"]
    assert list(harbor.discover_tasks(tmp_path / "a-task")) == [(tmp_path / "a-task").resolve()]


def test_cli_inspect_text():
    result = runner.invoke(app, ["inspect", str(COUNT_LINES)])
    assert result.exit_code == 0
    assert "count-lines: ok, 6 files, with solution" in result.output


def test_cli_inspect_json_reports_invalid_tasks(tmp_path: Path):
    shutil.copytree(COUNT_LINES, tmp_path / "good")
    shutil.copytree(COUNT_LINES, tmp_path / "bad")
    (tmp_path / "bad" / "tests" / "test.sh").unlink()
    result = runner.invoke(app, ["inspect", "--json", str(tmp_path)])
    assert result.exit_code == 1
    tasks = {t["id"]: t for t in json.loads(result.output)["tasks"]}
    assert tasks["good"]["valid"] is True
    assert tasks["bad"]["valid"] is False
    assert tasks["bad"]["problems"] == ["missing tests/test.sh"]


def test_cli_inspect_nothing_found(tmp_path: Path):
    result = runner.invoke(app, ["inspect", str(tmp_path)])
    assert result.exit_code == 2
