"""Run the data pipeline step by step (inside the `chama` conda environment).

Usage:
    python -m chama.pipeline ingest            # 1. raw Excel -> raw schema
    python -m chama.pipeline suggest-aliases   # 2. name spellings -> review file
    python -m chama.pipeline load-aliases      #    reviewed file -> private.member_aliases
    python -m chama.pipeline anonymise         # 3. raw -> staging, names -> codes
    python -m chama.pipeline clean             # 4. types and fixes (next)

Add --help after any step for details.
"""
from __future__ import annotations

from collections.abc import Callable

import click

from chama import StepFailed
from chama.config import load_config, pseudonym_key
from chama.db import get_engine


def _run(step: Callable[[], None]) -> None:
    """Run a step; show a planned stop as a short message, not a traceback."""
    try:
        step()
    except StepFailed as e:
        raise click.ClickException(str(e)) from e


@click.group()
def cli() -> None:
    """Chama data pipeline. Run the steps in order; each one can be re-run."""


@cli.command()
def ingest() -> None:
    """Copy the raw Excel files into the raw schema, exactly as written."""
    from chama.ingestion.excel_loader import run

    _run(lambda: run(load_config(), get_engine()))


@cli.command("suggest-aliases")
@click.option("--overwrite", is_flag=True, help="Replace a review file that has unloaded changes.")
def suggest_aliases(overwrite: bool) -> None:
    """Suggest which name spellings are the same member.

    Writes data/interim/aliases_<chama>.csv. Check the `canonical_name` column,
    correct it where needed, save, then run load-aliases.
    """
    from chama.anonymisation.aliases import run_suggest

    _run(lambda: run_suggest(load_config(), get_engine(), overwrite))


@cli.command("load-aliases")
def load_aliases() -> None:
    """Load the reviewed alias files into private.member_aliases."""
    from chama.anonymisation.aliases import run_load

    _run(lambda: run_load(load_config(), get_engine()))


@cli.command()
def anonymise() -> None:
    """Copy the raw tables to staging with member codes instead of names."""
    from chama.anonymisation.anonymise import run

    _run(lambda: run(get_engine(), pseudonym_key()))


@cli.command()
def clean() -> None:
    """Give dates, amounts and statuses proper types (not built yet)."""
    click.echo("Step 'clean' is not built yet - see the GitHub issues.")


if __name__ == "__main__":
    cli()
