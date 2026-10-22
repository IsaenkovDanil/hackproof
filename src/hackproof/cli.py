"""Command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from hackproof import __version__
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
def audit(path: Path) -> None:
    """Audit a task directory (arrives in phase 2 of the roadmap)."""
    typer.echo(f"audit is not implemented yet; nothing was checked in {path}", err=True)
    raise typer.Exit(code=2)


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
