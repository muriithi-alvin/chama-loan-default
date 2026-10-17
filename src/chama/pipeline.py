"""Run the data pipeline (inside the `chama` conda environment).

Usage:
    python -m chama.pipeline all               # every step below, in order
    python -m chama.pipeline ingest            # 1. raw Excel -> raw schema
    python -m chama.pipeline suggest-aliases   # 2. name spellings -> review file
    python -m chama.pipeline load-aliases      #    reviewed file -> private.member_aliases
    python -m chama.pipeline anonymise         # 3. raw -> staging, names -> codes
    python -m chama.pipeline clean             # 4. staging -> analytics with dbt, checks, report
    python -m chama.pipeline dbt <args>        #    any dbt command, e.g. "dbt test"
    python -m chama.pipeline export            # 5. modelling table (codes only) -> Google Drive

Add --help after any step for details.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import click

from chama import StepFailed
from chama.config import load_config, pseudonym_key, shown_path
from chama.db import get_engine


def _run(step: Callable[[], None]) -> None:
    """Run a step; show a planned stop as a short message, not a traceback."""
    try:
        step()
    except StepFailed as e:
        raise click.ClickException(str(e)) from e


def run_clean(config: dict, engine) -> None:
    """Step 4: dbt build (models and checks), then the quality report."""
    from chama.cleaning.transform import run_dbt
    from chama.validation.report import run as report

    run_dbt(["build"], config)
    report(engine)


def run_all(config: dict, engine) -> None:
    """Every step in order, from an empty or existing database.

    Name matching needs a person, so the run stops after writing the review
    file when it finds spellings nobody has reviewed yet.
    """
    from chama.anonymisation import aliases, anonymise
    from chama.db import create_schemas
    from chama.ingestion import excel_loader

    def heading(text: str) -> None:
        print(f"\n=== {text} ===")

    heading("0. Database schemas")
    create_schemas(engine)
    print("schemas and private tables ready")

    heading("1. Ingest")
    excel_loader.run(config, engine)

    heading("2. Member names")
    aliases.restore_reviewed(config, engine)
    unreviewed = aliases.unreviewed_counts(config, engine)
    if unreviewed:
        aliases.run_suggest(config, engine)
        files = ", ".join(str(shown_path(aliases.review_file(cid))) for cid in unreviewed)
        counts = ", ".join(f"{cid}: {n}" for cid, n in unreviewed.items())
        raise StepFailed(
            f"New name spellings need a review ({counts}). Open {files}, check "
            "canonical_name, save, run load-aliases, then run all again."
        )
    print("every spelling has a reviewed alias")

    heading("3. Anonymise")
    anonymise.run(engine, pseudonym_key())

    heading("4. Clean, link loans, check")
    run_clean(config, engine)


@click.group()
def cli() -> None:
    """Chama data pipeline. Run `all`, or the steps in order; each can be re-run."""


@cli.command("all")
def all_steps() -> None:
    """Run every step in order: schemas, ingest, names, anonymise, clean.

    Works on an empty database too: reviewed names are restored from the
    review files. If new spellings are found, the run writes the review file
    and stops; review it, run load-aliases, then run all again.
    """
    _run(lambda: run_all(load_config(), get_engine()))


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
    """Load the reviewed alias files into private.member_aliases.

    Marks every row in the file as reviewed, so the file keeps a record of the
    review and `all` can restore it into a rebuilt database.
    """
    from chama.anonymisation.aliases import run_load

    _run(lambda: run_load(load_config(), get_engine()))


@cli.command()
def anonymise() -> None:
    """Copy the raw tables to staging with member codes instead of names."""
    from chama.anonymisation.anonymise import run

    _run(lambda: run(get_engine(), pseudonym_key()))


@cli.command()
def clean() -> None:
    """Build the clean tables and loans with dbt, run the checks, report.

    Stops with a message if a check fails; otherwise prints the data quality
    report and saves it to data/processed/quality_report.csv.
    """
    _run(lambda: run_clean(load_config(), get_engine()))


@cli.command(
    "dbt",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def dbt_command(args: tuple[str, ...]) -> None:
    """Run any dbt command on transform/ with the settings from .env.

    Examples: dbt test, dbt run --select loans, dbt docs generate
    """
    from chama.cleaning.transform import run_dbt

    if not args:
        raise click.UsageError("Give a dbt command, e.g. python -m chama.pipeline dbt test")
    _run(lambda: run_dbt(list(args), load_config()))


@cli.command()
@click.option(
    "--to", "out_dir", type=click.Path(file_okay=False, path_type=Path),
    help="Folder to write to (default: <DRIVE_DIR>/data, else data/processed).",
)
def export(out_dir: Path | None) -> None:
    """Write the modelling table for Colab: loan_features.parquet and a manifest.

    Only analytics.loan_features is written: member codes and features, no
    names, no free text (decision D-016). Stops if the table has a column not
    cleared for export or a value containing a member's name. Set DRIVE_DIR
    in .env to the project folder on Google Drive; the table goes to its
    data/ folder, which the Colab notebooks read.
    """
    from chama.features.export import run

    _run(lambda: run(load_config(), get_engine(), out_dir))


@cli.command()
@click.option(
    "--data", type=click.Path(dir_okay=False, path_type=Path),
    help="The exported table (default: <DRIVE_DIR>/data/loan_features.parquet).",
)
@click.option(
    "--model", "models", multiple=True,
    type=click.Choice(["logistic_regression", "random_forest", "xgboost"]),
    help="Train only this model (repeat for more). Default: all in config.",
)
@click.option(
    "--imbalance", multiple=True,
    type=click.Choice(["none", "class_weight", "kmeans_smote", "cluster_centroids"]),
    help="Only this imbalance strategy (repeat for more). Default: all in config.",
)
def train(data: Path | None, models: tuple[str, ...], imbalance: tuple[str, ...]) -> None:
    """Train and test the models on the exported table; log each run to MLflow.

    Every model is tested walking forward in time (trained on earlier loans,
    scored on the next year) and with members held out, once per imbalance
    strategy. Runs go to <DRIVE_DIR>/mlruns (else ./mlruns); view them with
    the mlflow ui command printed at the end. Does not need the database.
    """
    from chama.config import mlflow_dir
    from chama.models.train import run, summary_table

    def go() -> None:
        summary, _ = run(data_path=data, models=list(models) or None,
                         imbalance=list(imbalance) or None)
        print()
        print(summary_table(summary).to_string(index=False))
        print("\nCompare runs in the browser (PowerShell):")
        print('  $env:MLFLOW_ALLOW_FILE_STORE = "true"')
        print(f'  mlflow ui --backend-store-uri "{mlflow_dir().resolve().as_uri()}"')

    _run(go)


if __name__ == "__main__":
    cli()
