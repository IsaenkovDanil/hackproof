# Hackproof

[![CI](https://github.com/IsaenkovDanil/hackproof/actions/workflows/ci.yml/badge.svg)](https://github.com/IsaenkovDanil/hackproof/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Quality audits for RL environments and benchmark graders.

An RL environment is only as good as its grader: if a task rewards an agent that did not solve it,
training teaches the wrong skill and benchmark numbers stop meaning anything. Hackproof checks the
properties a trustworthy task should have and explains how to fix the ones that fail:

- trivial baseline agents earn zero reward;
- the grader is isolated from anything the agent could change;
- the agent's sandbox holds no copy of the answer;
- the grader rejects near-miss solutions;
- the reference solution passes every time;
- difficulty is calibrated for training.

Status: early. Two checks run today on [Harbor](https://docs.harborframework.com) tasks
(the format behind Terminal-Bench 2.0), through Harbor's own trial machinery and Docker:

| Check | Property | Verdicts |
| --- | --- | --- |
| `baseline.nop` | A do-nothing agent earns zero reward | fail on any reward; a verifier error never counts as zero |
| `reference.reliability` | The reference solution passes every time | Wald SPRT on repeated runs: a broken reference fails after ~2 runs, a stable one is confirmed after 31 |

Scope and assumptions: [docs/threat-model.md](docs/threat-model.md).

```bash
uv sync --extra harbor
uv run hackproof inspect tests/fixtures/harbor          # parse only, no Docker
uv run hackproof audit tests/fixtures/harbor --oracle-runs 31
```

Each task gets a JSON report in `hackproof-reports/`. Exit code 1 means a check failed.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Try the statistics helpers

```bash
uv run hackproof stats wilson 0 20
uv run hackproof stats posterior 0 10 --below 0.02
uv run hackproof stats pass-at-k 10 3 5
```

## License

[Apache-2.0](LICENSE)
