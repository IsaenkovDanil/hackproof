"""Command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from hackproof import __version__
from hackproof.adapters import harbor
from hackproof.model import TaskFormatError
from hackproof.stats import BetaPosterior, pass_at_k, wilson_interval

app = typer.Typer(
    help="Quality audits for RL environments and benchmark graders.",
    no_args_is_help=True,
)
stats_app = typer.Typer(help="Statistics helpers used by the checks.", no_args_is_help=True)
app.add_typer(stats_app, name="stats")


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def inspect(
    path: Path,
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Parse Harbor task directories at PATH and summarise them, without running anything."""
    task_dirs = list(harbor.discover_tasks(path)) if path.is_dir() else []
    if not task_dirs:
        typer.echo(f"no Harbor tasks found at {path}", err=True)
        raise typer.Exit(code=2)

    summaries, failures = [], 0
    for task_dir in task_dirs:
        try:
            task = harbor.load_task(task_dir)
        except TaskFormatError as exc:
            failures += 1
            summaries.append({"id": task_dir.name, "valid": False, "problems": exc.problems})
            continue
        summaries.append(
            {
                "id": task.id,
                "valid": True,
                "format": task.format,
                "sha256": task.digest,
                "has_solution": task.has_solution,
                "files": len(task.files),
                "config_sections": sorted(task.config),
            }
        )

    if as_json:
        typer.echo(json.dumps({"tasks": summaries}, indent=2))
    else:
        for s in summaries:
            if s["valid"]:
                solution = "with solution" if s["has_solution"] else "no solution"
                typer.echo(
                    f"{s['id']}: ok, {s['files']} files, {solution}, sha256 {s['sha256'][:12]}"
                )
            else:
                typer.echo(f"{s['id']}: invalid")
                for problem in s["problems"]:
                    typer.echo(f"  - {problem}")
    raise typer.Exit(code=1 if failures else 0)


def _make_runner(workdir: Path):
    """Build the execution backend. Tests replace this with a scripted fake."""
    from hackproof.runners.harbor import HarborRunner

    return HarborRunner(workdir)


@app.command()
def audit(
    path: Path,
    out: Path = typer.Option(Path("hackproof-reports"), help="Directory for JSON reports."),
    nop_runs: int = typer.Option(2, min=1, help="Runs of the no-op baseline agent (P1)."),
    oracle_runs: int = typer.Option(
        31, min=1, help="Maximum reference-solution runs (P5); SPRT stops earlier when decisive."
    ),
) -> None:
    """Run the checks on Harbor tasks at PATH. Exit 1 if any check fails, 2 on tool errors."""
    from hackproof.checks import check_nop_baseline, check_reference_reliability
    from hackproof.report import build_report
    from hackproof.runners.harbor import HarborNotInstalledError

    task_dirs = list(harbor.discover_tasks(path)) if path.is_dir() else []
    if not task_dirs:
        typer.echo(f"no Harbor tasks found at {path}", err=True)
        raise typer.Exit(code=2)
    try:
        runner = _make_runner(out)
    except HarborNotInstalledError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    out.mkdir(parents=True, exist_ok=True)
    any_fail = tool_error = False
    for task_dir in task_dirs:
        try:
            task = harbor.load_task(task_dir)
        except TaskFormatError as exc:
            tool_error = True
            typer.echo(f"{task_dir.name}: invalid task, skipped ({'; '.join(exc.problems)})")
            continue
        checks = [
            check_nop_baseline(task, runner, runs=nop_runs),
            check_reference_reliability(task, runner, max_runs=oracle_runs),
        ]
        report = build_report(task, checks, runner=runner.name)
        report_path = out / f"{task.id}.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        typer.echo(f"{task.id}: {report['summary']['verdict']}  ({report_path})")
        for check in checks:
            typer.echo(f"  [{check.verdict.value:>7}] {check.property} {check.id}: {check.summary}")
            if check.fix and check.verdict.value in ("fail", "warn"):
                typer.echo(f"            fix: {check.fix}")
        any_fail |= report["summary"]["verdict"] == "fail"
    raise typer.Exit(code=1 if any_fail else 2 if tool_error else 0)


@stats_app.command("wilson")
def wilson(events: int, n: int) -> None:
    """95% Wilson interval for EVENTS out of N runs."""
    low, high = wilson_interval(events, n)
    typer.echo(f"{events}/{n}: rate {events / n:.4f}, 95% Wilson interval [{low:.4f}, {high:.4f}]")


@stats_app.command("posterior")
def posterior(
    successes: int,
    n: int,
    below: float = typer.Option(None, help="Also print P(rate < BELOW)."),
) -> None:
    """Beta posterior for a success rate, starting from a uniform prior."""
    post = BetaPosterior.from_counts(successes, n)
    low, high = post.credible_interval()
    typer.echo(
        f"Beta({post.alpha}, {post.beta}): mean {post.mean():.4f}, "
        f"95% credible interval [{low:.4f}, {high:.4f}]"
    )
    if below is not None:
        typer.echo(f"P(rate < {below}) = {post.cdf(below):.4f}")


@stats_app.command("pass-at-k")
def pass_at_k_command(n: int, c: int, k: int) -> None:
    """Unbiased pass@k from N attempts with C successes."""
    typer.echo(f"pass@{k} = {pass_at_k(n, c, k):.4f}")
