"""Harbor task format (used by Terminal-Bench 2.0).

Layout, per https://docs.harborframework.com/core-concepts/tasks/overview.md:

    my-task/
    ├── instruction.md
    ├── task.toml
    ├── environment/   Dockerfile, docker-compose.yaml or another environment spec
    ├── solution/      solve.sh (optional)
    └── tests/         test.sh, which writes /logs/verifier/reward.txt or reward.json

This module only reads files. Running a task is the executor's job.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from hackproof.model import Task, TaskFormatError, directory_digest, iter_task_files

FORMAT = "harbor"
ENVIRONMENT_SPECS = ("Dockerfile", "docker-compose.yaml", "docker-compose.yml", "Apptainer.def")


def looks_like_task(path: Path) -> bool:
    """Cheap test used for discovery: the two files every Harbor task has."""
    return (path / "task.toml").is_file() and (path / "instruction.md").is_file()


def load_task(path: Path) -> Task:
    """Parse a Harbor task directory, reporting every problem at once."""
    root = path.resolve()
    if not root.is_dir():
        raise TaskFormatError(root, ["not a directory"])

    problems: list[str] = []
    instruction = ""
    config: dict = {}

    instruction_path = root / "instruction.md"
    if instruction_path.is_file():
        instruction = instruction_path.read_text(encoding="utf-8")
        if not instruction.strip():
            problems.append("instruction.md is empty")
    else:
        problems.append("missing instruction.md")

    config_path = root / "task.toml"
    if config_path.is_file():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            problems.append(f"task.toml is not valid TOML: {exc}")
    else:
        problems.append("missing task.toml")

    environment_dir = root / "environment"
    if not environment_dir.is_dir():
        problems.append("missing environment/ directory")
    elif not any((environment_dir / spec).is_file() for spec in ENVIRONMENT_SPECS):
        problems.append(f"environment/ has none of: {', '.join(ENVIRONMENT_SPECS)}")

    tests_dir = root / "tests"
    if not (tests_dir / "test.sh").is_file():
        problems.append("missing tests/test.sh")

    solution_dir = root / "solution"
    if solution_dir.exists() and not solution_dir.is_dir():
        problems.append("solution exists but is not a directory")

    if problems:
        raise TaskFormatError(root, problems)

    return Task(
        id=root.name,
        format=FORMAT,
        root=root,
        instruction=instruction,
        config=config,
        environment_dir=environment_dir,
        tests_dir=tests_dir,
        solution_dir=solution_dir if solution_dir.is_dir() else None,
        digest=directory_digest(root),
        files=tuple(p.relative_to(root).as_posix() for p in iter_task_files(root)),
    )


def discover_tasks(root: Path) -> Iterator[Path]:
    """Task directories at `root` itself or one level below it, sorted by name."""
    root = root.resolve()
    if looks_like_task(root):
        yield root
        return
    for child in sorted(root.iterdir()):
        if child.is_dir() and looks_like_task(child):
            yield child
