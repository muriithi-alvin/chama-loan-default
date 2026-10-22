"""Train and test every model and imbalance strategy for each target; log to MLflow.

Each target has its own MLflow experiment (config: modelling.targets). One run
per model and strategy (decisions D-019, D-020), holding:
  params   the target, model, strategy and test settings
  tags     the data version (file hash, export time, git commit, label rule)
           and the training batch: every run of one `train` call shares it, so
           notebooks can pick the best run of the latest batch
  metrics  forward_* (walk forward, the main test), members_* (members held
           out), the band cut-offs and how the bands sorted the test rows
  files    test scores, the risk band table, precision-recall and calibration
           plots, SHAP importance, and the final model, trained on every row
           with a known outcome

The data is the exported tables only (codes, no names), so this runs the same
here and in Colab.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import export_dir, load_config, mlflow_dir

SUMMARY_COLUMNS = {
    "target": "target",
    "run": "run",
    "forward_pr_auc": "PR AUC",
    "forward_pr_auc_low": "low",
    "forward_pr_auc_high": "high",
    "forward_event_share": "chance",
    "forward_roc_auc": "ROC AUC",
    "forward_brier": "Brier",
    "members_pr_auc": "PR AUC (members held out)",
    "members_roc_auc": "ROC AUC (members held out)",
    "high_band_event_rate": "high band rate",
    "low_band_event_rate": "low band rate",
    "high_band_share_of_events": "events in high band",
}


def setup_mlflow(tracking_dir: Path, experiment: str):
    """Point MLflow at a plain folder (on Drive when DRIVE_DIR is set).

    MLflow 3 keeps folder tracking in maintenance mode and asks for a database
    instead; a folder of small files syncs safely through Google Drive, a
    database file written from Colab does not (decision D-019).
    """
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    os.environ.setdefault("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
    import mlflow

    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_dir.resolve().as_uri())
    mlflow.set_experiment(experiment)
    return mlflow


def target_settings(config: dict, target_name: str) -> dict:
    """The shared modelling settings with one target's own settings on top."""
    modelling = config["modelling"]
    shared = {k: v for k, v in modelling.items() if k != "targets"}
    return shared | modelling["targets"][target_name]


def data_version(data_path: Path, config: dict) -> dict[str, str]:
    """Tags tying a run to the exact table it learned from."""
    from chama.models.data import load_manifest

    manifest = load_manifest(data_path)
    statuses = manifest.get("default_statuses") or config.get("default_statuses") or []
    return {
        "data_file": data_path.name,
        "data_md5": hashlib.md5(data_path.read_bytes()).hexdigest(),
        "data_exported_at": str(manifest.get("exported_at")),
        "data_git_commit": str(manifest.get("git_commit")),
        "label_rule": ", ".join(statuses),
        "history_months": str(manifest.get("history_months") or config.get("history_months")),
        "warning_horizon_meetings": str(
            manifest.get("warning_horizon_meetings") or config.get("warning_horizon_meetings")
        ),
    }


def train_one(df: pd.DataFrame, target, model: str, imbalance: str, settings: dict,
              tags: dict, mlflow) -> tuple[dict, pd.DataFrame]:
    """Test, fit the final model, explain it and log one MLflow run."""
    from chama.models import plots
    from chama.models.data import known_outcomes, xy
    from chama.models.estimators import make_model
    from chama.models.evaluate import (
        band_cutoffs,
        band_metrics,
        band_table,
        member_folds,
        metrics,
        walk_forward,
    )
    from chama.models.explain import importance, shap_values

    name = f"{model} + {imbalance}"
    seed = settings["random_state"]
    with mlflow.start_run(run_name=name) as run:
        mlflow.set_tags(tags | {"target": target.name})
        forward = walk_forward(df, target, model, imbalance, settings)
        members = member_folds(df, target, model, imbalance, settings)
        forward_metrics = metrics(forward, settings["bootstrap_samples"], seed)
        member_metrics = metrics(members, settings["bootstrap_samples"], seed)
        # cut-offs from the walk-forward scores: tested out of time (D-022)
        cutoffs = band_cutoffs(forward["score"], settings["band_shares"])
        bands = band_table(forward, cutoffs, settings["bootstrap_samples"], seed)
        mlflow.log_params({
            "target": target.name,
            "model": model,
            "imbalance": imbalance,
            "test_years": sorted(forward["test_year"].unique().tolist()),
            "min_training_events": settings["min_training_events"],
            "member_folds": settings["member_folds"],
            "band_shares": settings["band_shares"],
            "random_state": seed,
            "features": len(target.features),
        })
        mlflow.log_metrics(
            {f"forward_{k}": v for k, v in forward_metrics.items()}
            | {f"members_{k}": v for k, v in member_metrics.items()}
            | band_metrics(bands)
            | {f"band_cutoff_{name}": value for name, value in cutoffs.items()}
        )

        X, y = xy(known_outcomes(df), target)
        y = y.astype(int)
        final = make_model(target, model, imbalance, y, seed)
        final.fit(X, y)
        ranked = importance(shap_values(final, X, background=X))

        title = f"{target.name}: {name}"
        mlflow.log_figure(plots.precision_recall(forward, f"{title}\nwalk forward"),
                          "plots/precision_recall.png")
        mlflow.log_figure(plots.calibration(forward, f"{title}\nwalk forward"),
                          "plots/calibration.png")
        mlflow.log_figure(plots.importance_bar(ranked, f"{title}\nSHAP, final model"),
                          "plots/shap_importance.png")
        mlflow.log_text(bands.to_csv(index=False), "tables/risk_bands.csv")
        mlflow.log_text(ranked.rename("mean_abs_shap").to_csv(), "tables/shap_importance.csv")
        mlflow.log_text(forward.to_csv(index=False), "tables/walk_forward_scores.csv")
        mlflow.log_text(members.to_csv(index=False), "tables/members_held_out_scores.csv")
        mlflow.log_text("\n".join(target.features), "features.txt")
        # cloudpickle, not MLflow's default skops: skops refuses the
        # imbalanced-learn and XGBoost types. Models are only loaded back by
        # this project, from its own Drive folder.
        mlflow.sklearn.log_model(
            final, name="model", input_example=X.head(3),
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
        )

    summary = {"target": target.name, "run": name, "model": model, "imbalance": imbalance,
               "run_id": run.info.run_id}
    summary |= {f"forward_{k}": v for k, v in forward_metrics.items()}
    summary |= {f"members_{k}": v for k, v in member_metrics.items()}
    summary |= band_metrics(bands)
    summary |= {f"band_cutoff_{name}": value for name, value in cutoffs.items()}
    return summary, forward


def run(
    targets: list[str] | None = None,
    data_dir: Path | None = None,
    tracking_dir: Path | None = None,
    config: dict | None = None,
    models: list[str] | None = None,
    imbalance: list[str] | None = None,
    log: Callable[[str], None] = print,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    """Train every model and strategy in config (or the ones given) per target.

    Returns a summary (per target, best walk-forward PR AUC first) and the
    walk-forward scores of each run, keyed by (target, run).
    """
    from chama.models.data import TARGETS, load_table

    config = config or load_config()
    data_dir = Path(data_dir or export_dir())
    batch = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, scores = [], {}
    for target_name in targets or list(config["modelling"]["targets"]):
        target = TARGETS[target_name]
        settings = target_settings(config, target_name)
        data_path = data_dir / f"{target.table}.parquet"
        if not data_path.exists():
            raise StepFailed(
                f"{data_path} not found. Run python -m chama.pipeline export first "
                "(and check DRIVE_DIR in .env)."
            )
        df = load_table(data_path, target)
        tags = data_version(data_path, config) | {"training_batch": batch}
        mlflow = setup_mlflow(Path(tracking_dir or mlflow_dir()), settings["experiment"])
        for model in models or settings["models"]:
            for strategy in imbalance or settings["imbalance"]:
                log(f"{target_name}: training {model} + {strategy}")
                row, forward = train_one(df, target, model, strategy, settings, tags, mlflow)
                rows.append(row)
                scores[(target_name, row["run"])] = forward
    summary = pd.DataFrame(rows).sort_values(["target", "forward_pr_auc"], ascending=[True, False])
    return summary.reset_index(drop=True), scores


def summary_table(summary: pd.DataFrame) -> pd.DataFrame:
    """The main columns of a summary, rounded, for printing."""
    return summary[list(SUMMARY_COLUMNS)].rename(columns=SUMMARY_COLUMNS).round(3)
