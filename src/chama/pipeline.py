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
    python -m chama.pipeline register-model    #    the chosen model -> MLflow registry, alias "champion"
    python -m chama.pipeline score             # 7. early-warning bands and reasons for the web pages
    python -m chama.pipeline evaluate-chama    #    test the model on a test-only chama (MLflow)
    python -m chama.pipeline drift             #    recent records vs the training data (Evidently)
    python -m chama.pipeline deploy-bundle     #    demo chama + model for the cloud release (checked for real names)
    python -m chama.pipeline deploy-publish    #    bundle -> private dataset; settings and build -> Hugging Face Space
    python -m chama.pipeline serve-release     #    the release on this laptop, demo chama only, for a tunnel
    python -m chama.pipeline demo-chama        #    chama B's pages as Humble Sister, for the web interface
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


@cli.command("register-model")
def register_model() -> None:
    """Register the chosen early-warning model, alias "champion" (S-8, D-030).

    The chosen run of the latest training batch (D-023) becomes a new version
    of chama-missed-repayment in the MLflow registry, and the alias moves to
    it. Scoring and the worker load the model by that alias. Run it after
    training; restart the worker to pick up the new version.
    """
    from chama.models.registry import ALIAS, load_champion, register

    def go() -> None:
        name, version = register()
        champion = load_champion()
        print(f"Registered {name} version {version} as @{ALIAS} (run {champion.run_id[:8]}, "
              f"checksum {champion.checksum[:12]}).")

    _run(go)


@cli.command("evaluate-chama")
@click.argument("chama_id", default="chama_a")
def evaluate_chama(chama_id: str) -> None:
    """Test the model trained on chama B on a test-only chama (D-029).

    Scores every meeting of CHAMA_ID with a known outcome using the chosen
    missed-repayment model, and logs PR AUC, ROC AUC and how often each band
    missed to the MLflow experiment chama-missed-repayment-held-out, beside
    chama B's walk-forward results. The chama must be marked test_only.
    """
    from chama.models.held_out import run

    def evaluate() -> None:
        result = run(get_engine(), load_config(), chama_id)
        m, trained = result["metrics"], result["trained"]
        print(f"{chama_id}: {m['rows']:.0f} meetings with a known outcome, {m['events']:.0f} missed "
              f"({m['event_share']:.0%})")
        print(f"  PR AUC  {m['pr_auc']:.3f} (95% {m.get('pr_auc_low', float('nan')):.3f}-"
              f"{m.get('pr_auc_high', float('nan')):.3f}); chama B walk forward "
              f"{trained.get('metrics.forward_pr_auc', float('nan')):.3f}")
        print(f"  ROC AUC {m['roc_auc']:.3f} (95% {m.get('roc_auc_low', float('nan')):.3f}-"
              f"{m.get('roc_auc_high', float('nan')):.3f}); chama B walk forward "
              f"{trained.get('metrics.forward_roc_auc', float('nan')):.3f}")
        print("  How often each band missed, with chama B's cut-offs:")
        print(result["bands_trained_cutoffs"].to_string(index=False))
        print("Logged to MLflow: experiment chama-missed-repayment-held-out.")

    _run(evaluate)


@cli.command()
@click.option("--chama", "chama_id", default="chama_b", show_default=True)
@click.option("--months", default=12, show_default=True, help="The recent window to compare.")
def drift(chama_id: str, months: int) -> None:
    """Compare a chama's recent records with the training data (S-7, Evidently).

    For each of the model's 17 inputs, tests whether the last MONTHS months of
    the chama's meetings (all its rows for a test-only chama) differ from the
    rows the model learned from. Writes an HTML report to data/reports/drift/
    and logs it to the MLflow experiment chama-missed-repayment-drift.
    """
    from chama.models.drift import run

    def go() -> None:
        result = run(get_engine(), load_config(), chama_id, months)
        o, t = result["overall"], result["table"]
        print(f"{chama_id}: {result['current_rows']} recent rows against {result['reference_rows']} "
              f"rows the model learned from")
        print(f"  {o.get('drifted_features', 0):.0f} of {len(t)} inputs drifted ({o.get('drifted_share', 0):.0%})")
        for r in t[t["drifted"]].itertuples():
            print(f"  - {r.feature} ({r.test}: {r.value:.3g}, threshold {r.threshold:g})")
        print(f"Report: {result['html']}  (also in MLflow, experiment chama-missed-repayment-drift)")

    _run(go)


@cli.command("deploy-bundle")
def deploy_bundle() -> None:
    """Write the cloud release's private bundle to data/deploy/bundle (D-032).

    The interface copy's typed pages and names and the champion model. A copy
    with fictional names is checked for every word of every real member's name
    first; Humble Sister's copy keeps its real names (D-036), so its bundle stays
    on this laptop for serve-release and deploy-publish refuses it.
    """
    import json

    from chama.deploy import build

    def go() -> None:
        out = build(load_config())
        m = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
        checked = ("real names kept, as the chama's officials agreed (D-036); it stays on this laptop"
                   if m.get("real_names") else f"checked against {m['checked_against_real_names']} real names")
        print(f"Bundle written to {shown_path(out)}: {len(m['files'])} files, model version "
              f"{m['model']['version']} (checksum {m['model']['checksum'][:12]}), {checked}.")

    _run(go)


@cli.command("deploy-publish")
@click.option("--ref", default="main", show_default=True, help="The Git branch the image is built from.")
@click.option("--rebuild", is_flag=True, help="Rebuild the image, for example after pushing new code.")
def deploy_publish(ref: str, rebuild: bool) -> None:
    """Publish the release to Hugging Face from the settings in .env (D-032, D-041).

    Uploads data/deploy/bundle to a private dataset, makes a private storage
    bucket and mounts it in the Space at /data (where the records added later
    are kept), sets up the public Space with its variables and secrets, and
    uploads the Dockerfile, which starts the build. Needs a PRO account. Safe
    to run again: the bucket and what it holds are kept. Needs HF_TOKEN and the
    other settings listed in docs/deployment.md.
    """
    from chama.deploy import publish

    def go() -> None:
        address = publish(ref, rebuild)
        print(f"Published. Build log: the Space's Logs tab. The site will open at {address}")
        print(f"Ready when {address}/api/health says ready, with storage 'kept in the storage bucket'.")
        print(f"Add {address}/api/session/google/callback to Supabase's Redirect URLs for Google sign-in.")

    _run(go)


@cli.command("serve-release")
@click.option("--address", required=True, help="The tunnel's https address, shown on ngrok's Forwarding line.")
@click.option("--fresh", is_flag=True, help="Start again from the demo chama's starting state.")
def serve_release(address: str, fresh: bool) -> None:
    """Run the release on this laptop for a tunnel, until Ctrl+C (D-034).

    Uses its own database holding only the demo chama, so real chamas' records
    are out of reach. --fresh drops that database and its scanned pages, for
    example to reuse a demo page.
    """
    from chama.deploy import serve_on_laptop

    _run(lambda: serve_on_laptop(address, fresh))


@cli.command("first-start", hidden=True)
def first_start() -> None:
    """At the cloud release's start-up: load and score the demo chama into the
    container's empty database and add its two accounts (D-033)."""
    from chama.deploy import first_start as start

    _run(lambda: start(load_config(), get_engine()))


@cli.group("release-storage", hidden=True)
def release_storage() -> None:
    """In the cloud release: keep its records in the storage bucket at BACKUP_DIR (D-041)."""


def _bucket():
    from chama.release_storage import base_dir

    base = base_dir()
    if base is None:
        raise click.ClickException("BACKUP_DIR is not set.")
    return base


@release_storage.command("check")
def release_storage_check() -> None:
    """Exit 0 when the bucket's folder can be written to (waits up to 30 s for the mount)."""
    from chama.release_storage import wait_for_mount

    base = _bucket()
    if not wait_for_mount(base):
        raise click.ClickException(f"{base} cannot be written to: is the storage bucket attached?")
    print(f"storage bucket ready at {base}")


@release_storage.command("attach")
def release_storage_attach() -> None:
    """Link each release chama's scans, photos and names file into the bucket."""
    from chama.release_storage import attach

    for line in attach(_bucket(), load_config()):
        print(f"kept in the bucket: {line}")


@release_storage.command("restore")
def release_storage_restore() -> None:
    """Restore the newest saved database, if there is one (the database must be empty)."""
    from chama.release_storage import restore

    def go() -> None:
        found = restore(_bucket())
        print(f"restored the records saved in {found.name}" if found else "no saved records: starting from the bundle")

    _run(go)


@release_storage.command("save")
def release_storage_save() -> None:
    """Save the database to the bucket now."""
    from chama.release_storage import save

    _run(lambda: print(f"database saved: {save(_bucket()).name}"))


@cli.command("demo-chama")
@click.option("--from", "source_id", default=None, help="Default: the copy's copy_of in config/pipeline.yaml.")
@click.option("--to", "demo_id", default="chama_demo", show_default=True)
def demo_chama(source_id: str | None, demo_id: str) -> None:
    """Copy a chama's typed pages for the web interface (D-028, D-036).

    Writes data/raw/<to>/ and its reviewed names file, as the copy's settings in
    config/pipeline.yaml say: real names (with renames) or fictional ones, and
    pages up to records_until. Free-text columns are emptied and no photos are
    copied. An earlier copy is moved to data/interim/replaced/. Then run `all`
    and `score`: a page scanned into the copy never touches the real records.
    """
    from chama.web.services.demo import build_demo_chama

    _run(lambda: build_demo_chama(load_config(), pseudonym_key(), source_id, demo_id))


@cli.group("web-user")
def web_user() -> None:
    """Accounts for the web interface: add, list, deactivate, codes (R3).

    Signing in is Supabase's (D-037): a password (Authentication > Users > Add
    user, with Auto Confirm), Google with the same email, or a code texted to
    the phone. This says what the email or phone may open.
    """


@web_user.command("add")
@click.option("--email", help="For a password or Google sign-in.")
@click.option("--phone", help="07XXXXXXXX or +2547XXXXXXXX: for codes by text. Officials need one.")
@click.option("--role", required=True, type=click.Choice(["official", "member", "admin"]))
@click.option("--chama", "chama_id", required=True)
@click.option("--member", "member_code", help="Member accounts: the member code whose records they see.")
@click.option("--name", help="Officials: the name shown on the pages.")
@click.option("--position", type=click.Choice(["chair", "treasurer", "secretary"]))
def web_user_add(email: str | None, phone: str | None, role: str, chama_id: str, member_code: str | None,
                 name: str | None, position: str | None) -> None:
    """Give an email or phone access to a chama's pages."""
    from chama.db import create_schemas
    from chama.web.services.accounts import add_user

    def go() -> None:
        engine = get_engine()
        create_schemas(engine)
        print(add_user(engine, email, role, chama_id, member_code, name, position, phone=phone))

    _run(go)


@web_user.command("list")
def web_user_list() -> None:
    """Every account, its role, chama and whether it is active."""
    from chama.web.services.accounts import list_users

    _run(lambda: print("\n".join(list_users(get_engine()))))


@web_user.command("deactivate")
@click.option("--email", required=True, help="The account's email, or its phone for a phone-only account.")
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


@cli.command("meeting-texts")
@click.option("--send-test", is_flag=True,
              help="Text each official the next meeting's message now, as a test. It is not recorded, so the "
                   "real text still goes the day before.")
def meeting_texts_command(send_test: bool) -> None:
    """The text officials get the day before each meeting (D-045): when it goes,
    to whom and what it says. Sends nothing unless --send-test."""
    from datetime import datetime

    from chama.web.data import users
    from chama.web.services import meeting_texts as texts
    from chama.web.services.sms_hook import HookRefused, SmsSettings, send_text
    from chama.web.settings import chamas

    def go() -> None:
        from chama.db import create_schemas

        engine = get_engine()
        create_schemas(engine)
        today = datetime.now(texts.NAIROBI).date()
        print("\n".join(texts.preview(engine, today)))
        if not send_test:
            return
        sms = SmsSettings.from_env()
        if not sms.can_text:
            raise StepFailed("Add AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY to .env first.")
        for chama_id, chama in chamas().items():
            if not chama.get("meets"):
                continue
            meeting = texts.next_meeting(chama["meets"], today)
            with engine.begin() as conn:
                officials = users.officials_with_phones(conn, chama_id)
                counts = texts.counts_for(conn, chama_id)
            for official in officials:
                words = texts.message(official.language, meeting, counts, texts.site_address())
                try:
                    answer = send_text(sms, official.phone, words)
                    print(f"[{chama_id}] test sent to the number ending {official.phone[-3:]}: "
                          f"{answer.get('status')}, {answer.get('cost', 'cost not given')}")
                except HookRefused as e:
                    print(f"[{chama_id}] not sent to the number ending {official.phone[-3:]}: {e.message}")

    _run(go)


@cli.command("web-stats")
@click.option("--last", type=int, help="Only the last N requests.")
def web_stats(last: int | None) -> None:
    """Median and 95th percentile server time per API route (X9)."""
    from chama.web.services.stats import run_stats
    from chama.web.settings import web_settings

    _run(lambda: run_stats(web_settings().log_dir, last))


if __name__ == "__main__":
    cli()
