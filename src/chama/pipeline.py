"""Run the data pipeline (inside the `chama` conda environment).

Usage:
    python -m chama.pipeline all               # every step below, in order
    python -m chama.pipeline ingest            # 1. raw Excel -> raw schema
    python -m chama.pipeline suggest-aliases   # 2. name spellings -> review file
    python -m chama.pipeline load-aliases      #    reviewed file -> private.member_aliases
    python -m chama.pipeline anonymise         # 3. raw -> staging, names -> codes
    python -m chama.pipeline clean             # 4. staging -> analytics with dbt, checks, report
    python -m chama.pipeline dbt <args>        #    any dbt command, e.g. "dbt test"
    python -m chama.pipeline export            # 5. modelling tables (codes only) -> Google Drive
    python -m chama.pipeline train             # 6. train, test and log the models (MLflow)
    python -m chama.pipeline extract <photos>  #    ledger photos -> rows, with a vision model
    python -m chama.pipeline extract-eval      #    extraction measured against the typed pages
    python -m chama.pipeline score             # 7. early-warning bands and reasons for the web pages
    python -m chama.pipeline demo-chama        #    chama B's pages with fictional names, for demos
    python -m chama.pipeline web-user add ...  #    accounts for the web interface (also list, deactivate)
    python -m chama.pipeline web-stats         #    page times from the web server's request log

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
    """Write the modelling tables for Colab, each as Parquet with a manifest.

    Only analytics.loan_features and analytics.member_months are written:
    member codes and features, no names, no free text (decision D-016). Stops,
    writing nothing, if a table has a column not cleared for export or a value
    containing a member's name. Set DRIVE_DIR in .env to the project folder on
    Google Drive; the tables go to its data/ folder, which the Colab notebooks
    read.
    """
    from chama.features.export import run

    _run(lambda: run(load_config(), get_engine(), out_dir))


@cli.command()
@click.option(
    "--target", "targets", multiple=True,
    type=click.Choice(["loan_default", "missed_repayment"]),
    help="Train only this target (repeat for both). Default: every target in config.",
)
@click.option(
    "--data-dir", type=click.Path(file_okay=False, path_type=Path),
    help="Folder with the exported tables (default: <DRIVE_DIR>/data, else data/processed).",
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
def train(targets: tuple[str, ...], data_dir: Path | None, models: tuple[str, ...],
          imbalance: tuple[str, ...]) -> None:
    """Train and test the models on the exported tables; log each run to MLflow.

    Two targets: loan_default (will this loan default?) and missed_repayment
    (will a repayment be missed in the next meetings?). Every model is tested
    walking forward in time and with members held out, once per imbalance
    strategy. Runs go to <DRIVE_DIR>/mlruns (else ./mlruns), one MLflow
    experiment per target; view them with the mlflow ui command printed at the
    end. Does not need the database.
    """
    from chama.config import mlflow_dir
    from chama.models.train import run, summary_table

    def go() -> None:
        summary, _ = run(targets=list(targets) or None, data_dir=data_dir,
                         models=list(models) or None, imbalance=list(imbalance) or None)
        print()
        print(summary_table(summary).to_string(index=False))
        print("\nCompare runs in the browser (PowerShell):")
        print('  $env:MLFLOW_ALLOW_FILE_STORE = "true"')
        print(f'  mlflow ui --backend-store-uri "{mlflow_dir().resolve().as_uri()}"')

    _run(go)


@cli.command()
@click.argument("photos", nargs=-1, required=True,
                type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--provider", help="Extraction provider from config/pipeline.yaml, e.g. groq or "
                                 "claude. Default: extraction.provider.")
def extract(photos: tuple[Path, ...], provider: str | None) -> None:
    """Read ledger photos into the raw layout with a vision model.

    Each photo is sent to the extraction provider (D-024, D-025): by default
    the open-weight Qwen model on Groq's free plan (GROQ_API_KEY in .env). The
    rows come back exactly as written, with flags on the lines to check.
    Prints the rows and saves them to data/interim/extractions/<provider>/
    (this computer only).
    """
    from chama.extraction.run import run_extract

    _run(lambda: run_extract(list(photos), load_config(), provider))


@cli.command("extract-eval")
@click.option("--chama", "chama_id", default="chama_b", show_default=True)
@click.option("--pages", help="Page numbers to test, e.g. 12,48,120. Default: a sample spread "
                              "through the ledger.")
@click.option("--sample", type=int, help="How many pages in the sample (default: extraction.eval_sample).")
@click.option("--refresh", is_flag=True, help="Read the pages again instead of reusing saved "
                                              "extractions.")
@click.option("--provider", help="Extraction provider from config/pipeline.yaml, e.g. groq or "
                                 "claude. Default: extraction.provider.")
def extract_eval(chama_id: str, pages: str | None, sample: int | None, refresh: bool,
                 provider: str | None) -> None:
    """Measure extraction against the hand-typed Excel files, cell by cell.

    Reads each page with the extraction model (or reuses its saved extraction),
    lines its rows up with the typed rows of the same photo and reports the
    share of cells right, lines found, how many wrong lines the checks flagged,
    time and cost per page. Run it once per provider to compare them on the
    same pages. Writes data/processed/extraction_eval_<provider>.csv (counts
    only) and data/interim/extraction_mismatches_<provider>.csv (every wrong
    cell).
    """
    from chama.extraction.run import run_evaluate

    page_numbers = [int(p) for p in pages.split(",")] if pages else None
    _run(lambda: run_evaluate(load_config(), chama_id, page_numbers, sample, refresh, provider))


@cli.command()
@click.option("--chama", "chama_ids", multiple=True,
              help="Score only this chama (repeat for more). Default: every chama in config.")
def score(chama_ids: tuple[str, ...]) -> None:
    """Save early-warning bands and reasons for the web pages (S-4).

    Scores every member who owes at each chama's latest recorded meeting with
    the chosen missed-repayment model (D-023): a band (Low, Medium, High) from
    the run's cut-offs and the three strongest reasons in plain words, saved to
    app.risk_scores with the meeting, the model run and the time. The score
    itself is not saved. Needs the MLflow runs (DRIVE_DIR or ./mlruns).
    """
    from chama.web.services.scoring import run_score

    _run(lambda: run_score(load_config(), get_engine(), list(chama_ids) or None))


@cli.command("demo-chama")
@click.option("--from", "source_id", default="chama_b", show_default=True)
@click.option("--to", "demo_id", default="chama_demo", show_default=True)
def demo_chama(source_id: str, demo_id: str) -> None:
    """Copy a chama's typed pages with fictional names, for demonstrations (D-028).

    Writes data/raw/<to>/ and its reviewed names file. Every member gets a fixed
    fictional name, free-text columns are emptied and no photos are copied, and
    the copy is checked for every real name before it is saved. Then run `all`
    and `score`: the demo chama's bands match the real chama's, and a page
    scanned into it never touches the real records.
    """
    from chama.web.services.demo import build_demo_chama

    _run(lambda: build_demo_chama(load_config(), pseudonym_key(), source_id, demo_id))


@cli.group("web-user")
def web_user() -> None:
    """Accounts for the web interface: add, list, deactivate, codes (R3).

    Create the person's sign-in in Supabase first (Authentication > Users >
    Add user, with Auto Confirm); this says what the email may open.
    """


@web_user.command("add")
@click.option("--email", required=True)
@click.option("--role", required=True, type=click.Choice(["official", "member", "admin"]))
@click.option("--chama", "chama_id", required=True)
@click.option("--member", "member_code", help="Member accounts: the member code whose records they see.")
@click.option("--name", help="Officials: the name shown on the pages (fictional for a demo account).")
@click.option("--position", type=click.Choice(["chair", "treasurer", "secretary"]))
def web_user_add(email: str, role: str, chama_id: str, member_code: str | None, name: str | None,
                 position: str | None) -> None:
    """Give an email access to a chama's pages."""
    from chama.db import create_schemas
    from chama.web.services.accounts import add_user

    def go() -> None:
        engine = get_engine()
        create_schemas(engine)
        print(add_user(engine, email, role, chama_id, member_code, name, position))

    _run(go)


@web_user.command("list")
def web_user_list() -> None:
    """Every account, its role, chama and whether it is active."""
    from chama.web.services.accounts import list_users

    _run(lambda: print("\n".join(list_users(get_engine()))))


@web_user.command("deactivate")
@click.option("--email", required=True)
def web_user_deactivate(email: str) -> None:
    """Stop an account signing in and end its sessions."""
    from chama.web.services.accounts import deactivate_user

    _run(lambda: print(deactivate_user(get_engine(), email)))


@web_user.command("codes")
@click.option("--chama", "chama_id", required=True)
def web_user_codes(chama_id: str) -> None:
    """Member codes of a chama with the names the pages show, to link a member account."""
    from chama.web.services.accounts import member_code_list

    _run(lambda: print("\n".join(member_code_list(get_engine(), chama_id))))


@cli.command("web-stats")
@click.option("--last", type=int, help="Only the last N requests.")
def web_stats(last: int | None) -> None:
    """Median and 95th percentile server time per API route (X9)."""
    from chama.web.services.stats import run_stats
    from chama.web.settings import web_settings

    _run(lambda: run_stats(web_settings().log_dir, last))


if __name__ == "__main__":
    cli()
