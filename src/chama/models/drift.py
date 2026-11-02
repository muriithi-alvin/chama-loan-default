"""Data drift (S-7): do recent records still look like the ones the model learned from?

Evidently compares each early-warning feature (analytics.member_months, the
17 inputs of the model) in two sets of rows:
- reference: the training chamas' rows with a known outcome, from before the
  window below (what the model learned from);
- current: one chama's rows from its last `months` months of meetings. For a
  test-only chama (D-029) all its rows, since the model never saw any.

Each feature gets a statistical test (Kolmogorov-Smirnov or chi-square for
small samples, a distance for large ones, Evidently's defaults) and is
"drifted" when the test says the two sets differ. The HTML report and a
table per feature go to data/reports/drift/ and to the MLflow experiment
`<target experiment>-drift`. Only feature values are used: no codes, no names.
"""
from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import PROJECT_ROOT, mlflow_dir
from chama.models.data import MISSED_REPAYMENT

VALUE_DRIFT = re.compile(r"ValueDrift\(column=(?P<column>.+?),method=(?P<method>.+?),threshold=(?P<threshold>[\d.e-]+)\)")


def split(df: pd.DataFrame, chama_id: str, training: tuple[str, ...], months: int,
          whole_chama: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(reference, current) rows of the model's features."""
    target = MISSED_REPAYMENT
    mine = df[df["chama_id"] == chama_id]
    if mine.empty:
        raise StepFailed(f"No early-warning rows for {chama_id}.")
    if whole_chama:
        current, start = mine, mine[target.time].min()
    else:
        start = mine[target.time].max() - pd.DateOffset(months=months - 1)
        current = mine[mine[target.time] >= start]
    reference = df[df["chama_id"].isin(training) & df["in_training"] & (df[target.time] < start)]
    if len(reference) < 30 or len(current) < 10:
        raise StepFailed(f"Too few rows to compare: {len(reference)} to learn from, {len(current)} recent. "
                         "Use a longer window (--months) or add more pages.")
    features = list(target.features)
    return reference[features].astype(float), current[features].astype(float)


def drift_table(snapshot_dict: dict) -> tuple[pd.DataFrame, dict]:
    """One row per feature (test, threshold, value, drifted) and the overall count and share."""
    rows, overall = [], {}
    for metric in snapshot_dict["metrics"]:
        name = metric["metric_name"]
        if name.startswith("DriftedColumnsCount"):
            overall = {"drifted_features": float(metric["value"]["count"]),
                       "drifted_share": float(metric["value"]["share"])}
        elif found := VALUE_DRIFT.match(name):
            method, threshold, value = found["method"], float(found["threshold"]), float(metric["value"])
            # p-value tests drift when small, distances when large
            drifted = value < threshold if "p_value" in method else value > threshold
            rows.append({"feature": found["column"], "test": method, "threshold": threshold,
                         "value": round(value, 6), "drifted": drifted})
    table = pd.DataFrame(rows).sort_values(["drifted", "feature"], ascending=[False, True], ignore_index=True)
    return table, overall


def run(engine, config: dict, chama_id: str = "chama_b", months: int = 12,
        tracking_dir: Path | None = None) -> dict:
    os.environ.setdefault("DO_NOT_TRACK", "1")   # Evidently's usage telemetry stays off
    from evidently import Report
    from evidently.presets import DataDriftPreset

    from chama.features.export import not_for_training
    from chama.models.held_out import chama_rows
    from chama.models.train import setup_mlflow, target_settings

    entry = next((c for c in config["chamas"] if c["id"] == chama_id), None)
    if entry is None:
        raise StepFailed(f"No chama {chama_id!r} in config/pipeline.yaml.")
    skip = set(not_for_training(config))
    training = tuple(c["id"] for c in config["chamas"] if c["id"] not in skip)
    df = pd.concat([chama_rows(engine, c) for c in {*training, chama_id}], ignore_index=True)
    whole = bool(entry.get("test_only"))
    reference, current = split(df, chama_id, training, months, whole)

    snapshot = Report([DataDriftPreset()]).run(reference_data=reference, current_data=current)
    table, overall = drift_table(snapshot.dict())

    out_dir = PROJECT_ROOT / "data" / "reports" / "drift"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{chama_id}_{datetime.now(UTC):%Y-%m-%d}"
    html = out_dir / f"{stem}.html"
    snapshot.save_html(str(html))
    table.to_csv(out_dir / f"{stem}.csv", index=False)

    settings = target_settings(config, MISSED_REPAYMENT.name)
    mlflow = setup_mlflow(Path(tracking_dir or mlflow_dir()), f"{settings['experiment']}-drift")
    with mlflow.start_run(run_name=f"{chama_id}: {'all rows' if whole else f'last {months} months'}"):
        mlflow.set_tags({"target": MISSED_REPAYMENT.name, "chama": chama_id, "test": "data_drift"})
        mlflow.log_params({"chama": chama_id, "window": "all rows" if whole else f"{months} months",
                           "reference_rows": len(reference), "current_rows": len(current),
                           "training_chamas": ",".join(training)})
        mlflow.log_metrics(overall | {f"drift_{r.feature}": float(r.drifted) for r in table.itertuples()})
        mlflow.log_artifact(str(html), "reports")
        mlflow.log_text(table.to_csv(index=False), "tables/drift_by_feature.csv")
    return {"table": table, "overall": overall, "html": html,
            "reference_rows": len(reference), "current_rows": len(current)}
