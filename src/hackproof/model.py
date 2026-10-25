"""Format-independent representation of a task.

Adapters turn a task in some framework's format (Harbor, verifiers, ...) into a `Task`. Checks
only ever see `Task`, so a new format needs a new adapter, not new checks.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Never part of a task's identity: editor, VCS and interpreter litter.
IGNORED_NAMES = frozenset({".git", "__pycache__", ".DS_Store", ".pytest_cache", ".ruff_cache"})


class TaskFormatError(ValueError):
    """A directory is not a valid task. `problems` lists every issue found, not just the first."""

    def __init__(self, root: Path, problems: list[str]) -> None:
        self.root = root
        self.problems = problems
        listing = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"{root} is not a valid task:\n{listing}")


@dataclass(frozen=True)
class Task:
    """One task, with paths resolved and content fingerprinted.

    `digest` is a SHA-256 over every file's relative path and bytes, so two reports with the same
    digest audited byte-identical tasks.
    """

    id: str
    format: str
    root: Path
    instruction: str
    config: dict[str, Any]
    environment_dir: Path
    tests_dir: Path
    solution_dir: Path | None
    digest: str
    files: tuple[str, ...] = field(repr=False)

    @property
    def has_solution(self) -> bool:
        return self.solution_dir is not None


def iter_task_files(root: Path) -> Iterator[Path]:
    """Every regular file under `root`, sorted by relative path, skipping IGNORED_NAMES."""
    stack = [root]
    found: list[Path] = []
    while stack:
        current = stack.pop()
        for entry in current.iterdir():
            if entry.name in IGNORED_NAMES:
                continue
            if entry.is_symlink():
                # Links are recorded by target text, never followed: a task must not pull in
                # files from outside its own directory.
                found.append(entry)
            elif entry.is_dir():
                stack.append(entry)
            elif entry.is_file():
                found.append(entry)
    yield from sorted(found, key=lambda p: p.relative_to(root).as_posix())


def directory_digest(root: Path) -> str:
    """SHA-256 fingerprint of a directory's files (paths, link targets and contents)."""
    h = hashlib.sha256()
    for path in iter_task_files(root):
        rel = path.relative_to(root).as_posix().encode()
        if path.is_symlink():
            payload = b"link:" + str(path.readlink()).encode()
        else:
            payload = path.read_bytes()
        h.update(len(rel).to_bytes(8, "big") + rel)
        h.update(len(payload).to_bytes(8, "big") + payload)
    return h.hexdigest()
