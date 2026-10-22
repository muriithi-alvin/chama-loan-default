"""The chosen model of each target (decision D-023).

`modelling.targets.<target>.chosen` in config/pipeline.yaml names the model
and imbalance strategy carried forward. Its run from the latest training batch
holds the final model (trained on every row with a known outcome) and the band
cut-offs tested out of time (D-022). Notebook 03 and, later, the officials'
dashboard (M4) score with these.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import load_config, mlflow_dir


def chosen_run(target_name: str, config: dict | None = None,
               tracking_dir: Path | None = None) -> pd.Series:
    """The chosen model's run from the latest training batch, as a row of
    mlflow.search_runs (run_id, params.*, metrics.*, tags.*)."""
    from chama.models.train import setup_mlflow, target_settings

    config = config or load_config()
    settings = target_settings(config, target_name)
    chosen = settings["chosen"]
    tracking_dir = Path(tracking_dir or mlflow_dir())
    mlflow = setup_mlflow(tracking_dir, settings["experiment"])
    runs = mlflow.search_runs(
        filter_string=(f"params.model = '{chosen['model']}' "
                       f"and params.imbalance = '{chosen['imbalance']}'")
    )
    if "tags.training_batch" in runs.columns:
        runs = runs[runs["tags.training_batch"].notna()]
    else:
        runs = runs.iloc[0:0]
    if runs.empty:
        raise StepFailed(
            f"No {chosen['model']} + {chosen['imbalance']} run for {target_name} in "
            f"{tracking_dir}. Run python -m chama.pipeline train first."
        )
    return runs.sort_values("tags.training_batch").iloc[-1]


def chosen_model(target_name: str, config: dict | None = None,
                 tracking_dir: Path | None = None):
    """The chosen run, its fitted final model and its band cut-offs."""
    import mlflow

    run = chosen_run(target_name, config, tracking_dir)
    model = mlflow.sklearn.load_model(f"runs:/{run['run_id']}/model")
    cutoffs = {"medium": float(run["metrics.band_cutoff_medium"]),
               "high": float(run["metrics.band_cutoff_high"])}
    return run, model, cutoffs
