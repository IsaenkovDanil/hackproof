# Notes for coding agents

- Scope: Hackproof is a quality-assurance tool. Checks verify properties of an environment and
  report how to fix failures. Reports never include step-by-step instructions for abusing a
  specific environment; findings go privately to authors first (see the roadmap).
- Layout: `src/hackproof/` (package), `tests/` (pytest). One module per concern: `cli.py`,
  `stats.py`, later `model.py`, `adapters/`, `checks/`, `report.py`.
- Statistics stay dependency-free and short enough to verify by hand against the explainer
  document (sections 6 and 8). Every formula gets a test with a hand-computed value.
- Every new check comes with fixtures: one task where the property holds and one where it does
  not, each with the expected verdict.
- Run `uv run pytest` and `uv run ruff check .` before proposing a change.
- Python >= 3.11, standard `pyproject.toml`; pin new dependencies with a lower bound.
