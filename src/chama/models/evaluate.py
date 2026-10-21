"""Honest tests for small, time-ordered data (decision D-020).

Walk forward (the main test). For each test year, train on rows from before
that year whose outcome was also known before it, then score that year's
rows. This copies how the Chama would use a model: learn from the past, judge
what comes next. Pooling the years gives enough events to measure.

Members held out (a second check). Each member's rows are kept together in
one fold, so the model is scored on members it never saw. It ignores time, so
it reads as "would this work for a new member", not as the main result.

Metrics: precision-recall AUC (how well events are ranked first; its chance
level is the share of events), ROC AUC, and the Brier score (how close the
scores are to what happened, lower is better), with bootstrap 95% intervals.

Score tables keep the target's key columns, `actual` (1 = the event happened)
and `score`.
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

from chama.models.data import Target, known_outcomes, xy
from chama.models.estimators import make_model

BANDS = ["low", "medium", "high"]


def forward_splits(
    df: pd.DataFrame, target: Target, test_years: list[int], min_training_events: int
) -> Iterator[tuple[int, pd.DataFrame, pd.DataFrame]]:
    """(year, training rows, test rows) for each test year that can be tested."""
    known = known_outcomes(df)
    year = known[target.time].dt.year
    for test_year in test_years:
        start = pd.Timestamp(year=test_year, month=1, day=1)
        train = known[(known[target.time] < start) & (known["outcome_month"] < start)]
        test = known[year == test_year]
        if test.empty or train[target.label].sum() < min_training_events:
            continue
        yield test_year, train, test


def scored(rows: pd.DataFrame, target: Target, scores) -> pd.DataFrame:
    """The key columns of the rows with their actual outcome and score."""
    return rows[list(target.keys)].assign(
        actual=rows[target.label].astype(int).to_numpy(), score=scores
    )


def walk_forward(df: pd.DataFrame, target: Target, model: str, imbalance: str,
                 settings: dict) -> pd.DataFrame:
    """Out-of-time scores for every testable year, one row per test row."""
    parts = []
    for year, train, test in forward_splits(
        df, target, settings["test_years"], settings["min_training_events"]
    ):
        X_train, y_train = xy(train, target)
        y_train = y_train.astype(int)
        fitted = make_model(target, model, imbalance, y_train, settings["random_state"])
        fitted.fit(X_train, y_train)
        parts.append(
            scored(test, target, fitted.predict_proba(xy(test, target)[0])[:, 1]).assign(
                test_year=year, training_rows=len(train), training_events=int(y_train.sum())
            )
        )
    if not parts:
        raise ValueError("No test year has enough known events before it to train on.")
    return pd.concat(parts, ignore_index=True)


def member_folds(df: pd.DataFrame, target: Target, model: str, imbalance: str,
                 settings: dict) -> pd.DataFrame:
    """Scores with each member's rows held out together, one row per row."""
    known = known_outcomes(df).reset_index(drop=True)
    X, y = xy(known, target)
    y = y.astype(int)
    folds = GroupKFold(n_splits=min(settings["member_folds"], known["member_code"].nunique()))
    parts = []
    for fold, (train_idx, test_idx) in enumerate(folds.split(X, y, groups=known["member_code"])):
        fitted = make_model(target, model, imbalance, y.iloc[train_idx], settings["random_state"])
        fitted.fit(X.iloc[train_idx], y.iloc[train_idx])
        parts.append(
            scored(known.iloc[test_idx], target,
                   fitted.predict_proba(X.iloc[test_idx])[:, 1]).assign(fold=fold)
        )
    return pd.concat(parts, ignore_index=True)


def metrics(pred: pd.DataFrame, n_boot: int = 1000, random_state: int = 42) -> dict[str, float]:
    """Ranking and calibration metrics for pooled test scores, with 95% intervals."""
    y = pred["actual"].astype(int).to_numpy()
    s = pred["score"].to_numpy()
    out = {
        "rows": float(len(y)),
        "events": float(y.sum()),
        "event_share": float(y.mean()),
        "pr_auc": float(average_precision_score(y, s)),
        "roc_auc": float(roc_auc_score(y, s)),
        "brier": float(brier_score_loss(y, s)),
    }
    rng = np.random.default_rng(random_state)
    boot = {"pr_auc": [], "roc_auc": []}
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        boot["pr_auc"].append(average_precision_score(y[idx], s[idx]))
        boot["roc_auc"].append(roc_auc_score(y[idx], s[idx]))
    for name, values in boot.items():
        if values:
            out[f"{name}_low"], out[f"{name}_high"] = map(float, np.percentile(values, [2.5, 97.5]))
    return out


def risk_band(scores, bands: dict[str, float]) -> np.ndarray:
    """low / medium / high from the score cut-offs in config (risk_bands)."""
    scores = np.asarray(scores, dtype=float)
    return np.select(
        [scores >= bands["high"], scores >= bands["medium"]], ["high", "medium"], default="low"
    )


def band_table(pred: pd.DataFrame, bands: dict[str, float]) -> pd.DataFrame:
    """For each risk band: rows, events, the event rate, and its share of all events."""
    y = pred["actual"].astype(int)
    table = (
        pd.DataFrame({"band": risk_band(pred["score"], bands), "actual": y})
        .groupby("band")["actual"]
        .agg(rows="size", events="sum")
        .reindex(BANDS, fill_value=0)
    )
    table["event_rate"] = (table["events"] / table["rows"].replace(0, np.nan)).round(3)
    table["share_of_events"] = (table["events"] / max(int(y.sum()), 1)).round(3)
    return table.reset_index()


def band_metrics(table: pd.DataFrame) -> dict[str, float]:
    """The high band's catch rate and precision, for comparing runs."""
    by_band = table.set_index("band")
    high = by_band.loc["high"]
    return {
        "high_band_share_of_events": float(high["share_of_events"]),
        "high_band_event_rate": float(0 if np.isnan(high["event_rate"]) else high["event_rate"]),
        "medium_or_high_share_of_events": float(by_band.loc[["medium", "high"], "share_of_events"].sum()),
        "high_band_rows": float(high["rows"]),
    }
