"""Test the chosen model on a chama it never learned from (decision D-029).

The missed-repayment model was trained on chama B only. Here every meeting of
a test-only chama (chama A) whose outcome is known is scored with that model,
and compared with what really happened, using the same measures as the
walk-forward test (Milestone 2 report, section 10):
- PR AUC and ROC AUC with bootstrap 95% intervals: how well the order works;
- how often each band missed, with chama B's band cut-offs (what the colours
  would have meant to chama A's officials) and with chama A's own top 20% /
  next 30% (whether the order still separates the chama's own members).

Results go to the MLflow experiment `<target experiment>-held-out`, beside
chama B's walk-forward runs, so the two can be compared run by run. Only
member codes, months and scores are logged; names never leave the database.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import mlflow_dir
from chama.models.data import MISSED_REPAYMENT, add_derived, known_outcomes, xy

MIN_EVENTS = 5  # below this a PR AUC means little; say so instead of logging it


def chama_rows(engine, chama_id: str) -> pd.DataFrame:
    """The chama's early-warning rows (analytics.member_months), typed like the export."""
    from sqlalchemy import text

    target = MISSED_REPAYMENT
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM analytics.member_months WHERE chama_id = :c"),
                         conn, params={"c": chama_id})
    if df.empty:
        raise StepFailed(f"No early-warning rows for {chama_id}. Scan and accept its pages first, "
                         "then run the pipeline.")
    for col in (target.time, "outcome_month"):
        df[col] = pd.to_datetime(df[col])
    df[target.label] = df[target.label].astype("Int64")
    df["in_training"] = df["in_training"].astype(bool)
    return add_derived(df)


def evaluate(df: pd.DataFrame, model, cutoffs: dict[str, float], settings: dict) -> dict:
    """Scores, metrics and band tables for the rows with a known outcome."""
    from chama.models.evaluate import band_cutoffs, band_metrics, band_table, metrics, scored

    target = MISSED_REPAYMENT
    known = known_outcomes(df)
    X, y = xy(known, target)
    events = int(y.astype(int).sum()) if len(y) else 0
    if events < MIN_EVENTS or events == len(y):
        raise StepFailed(
            f"Only {len(y)} meetings with a known outcome and {events} missed repayments: too few to "
            f"test on (at least {MIN_EVENTS} misses and some meetings without one are needed). "
            "Add more of the chama's pages first."
        )
    pred = scored(known, target, model.predict_proba(X)[:, 1])
    n_boot, seed = settings["bootstrap_samples"], settings["random_state"]
    own_cutoffs = band_cutoffs(pred["score"], settings["band_shares"])
    with_trained = band_table(pred, cutoffs, n_boot, seed)
    with_own = band_table(pred, own_cutoffs, n_boot, seed)
    return {
        "pred": pred,
        "metrics": metrics(pred, n_boot, seed),
        "bands_trained_cutoffs": with_trained,
        "bands_own_cutoffs": with_own,
        "band_metrics": band_metrics(with_own),
        "own_cutoffs": own_cutoffs,
    }


def run(engine, config: dict, chama_id: str, tracking_dir: Path | None = None) -> dict:
    """Evaluate the chosen model on `chama_id` and log the result to MLflow."""
    from chama.models import plots
    from chama.models.chosen import chosen_model
    from chama.models.train import setup_mlflow, target_settings

    entry = next((c for c in config["chamas"] if c["id"] == chama_id), None)
    if entry is None:
        raise StepFailed(f"No chama {chama_id!r} in config/pipeline.yaml.")
    if not entry.get("test_only"):
        raise StepFailed(f"{chama_id} is not marked test_only in config/pipeline.yaml, so the model may "
                         "have learned from it; a held-out test would not be fair (D-029).")

    target = MISSED_REPAYMENT
    settings = target_settings(config, target.name)
    tracking_dir = Path(tracking_dir or mlflow_dir())
    trained, model, cutoffs = chosen_model(target.name, config, tracking_dir)
    df = chama_rows(engine, chama_id)
    result = evaluate(df, model, cutoffs, settings)

    mlflow = setup_mlflow(tracking_dir, f"{settings['experiment']}-held-out")
    m = result["metrics"]
    with mlflow.start_run(run_name=f"{chama_id}: {trained['params.model']} trained on chama B"):
        mlflow.set_tags({"target": target.name, "test": "held_out_chama", "chama": chama_id,
                         "trained_run_id": trained["run_id"]})
        mlflow.log_params({
            "target": target.name, "chama": chama_id, "model": trained["params.model"],
            "imbalance": trained["params.imbalance"], "trained_run_id": trained["run_id"],
            "meetings": int(df["page_no"].nunique()),
            "first_month": str(df[target.time].min().date()), "last_month": str(df[target.time].max().date()),
        })
        # chama B's walk-forward results beside chama A's, for comparison in the same run
        trained_forward = {
            "trained_" + key.removeprefix("metrics."): float(value)
            for key, value in trained.items()
            if key.startswith("metrics.forward_") and pd.notna(value)
        }
        mlflow.log_metrics({f"held_out_{k}": v for k, v in m.items()} | result["band_metrics"] | trained_forward)
        title = f"{target.name}: {chama_id}, model trained on chama B"
        mlflow.log_figure(plots.precision_recall(result["pred"], title), "plots/precision_recall.png")
        mlflow.log_text(result["pred"].to_csv(index=False), "tables/held_out_scores.csv")
        mlflow.log_text(result["bands_trained_cutoffs"].to_csv(index=False), "tables/bands_chama_b_cutoffs.csv")
        mlflow.log_text(result["bands_own_cutoffs"].to_csv(index=False), "tables/bands_own_cutoffs.csv")
    return result | {"trained": trained}
