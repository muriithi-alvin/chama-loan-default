"""Honest tests for small, time-ordered data (decision D-020).

Walk forward (the main test). For each test year, train on loans given before
that year whose outcome was also known before it, then score that year's
loans. This copies how the Chama would use the model: learn from the past,
judge the next requests. Pooling the years gives enough defaults to measure.

Members held out (a second check). Each member's loans are kept together in
one fold, so the model is scored on members it never saw. It ignores time, so
it reads as "would this work for a new member", not as the main result.

Metrics: precision-recall AUC (how well defaults are ranked first; its chance
level is the share of defaults), ROC AUC, and the Brier score (how close the
scores are to what happened, lower is better), with bootstrap 95% intervals.
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

from chama.models.data import KEYS, TARGET, known_outcomes, xy
from chama.models.estimators import make_model

BANDS = ["low", "medium", "high"]


def forward_splits(
    df: pd.DataFrame, test_years: list[int], min_training_defaults: int
) -> Iterator[tuple[int, pd.DataFrame, pd.DataFrame]]:
    """(year, training loans, test loans) for each test year that can be tested."""
    known = known_outcomes(df)
    for year in test_years:
        start = pd.Timestamp(year=year, month=1, day=1)
        train = known[(known["issued_month"] < start) & (known["outcome_month"] < start)]
        test = known[known["issue_year"] == year]
        if test.empty or train[TARGET].sum() < min_training_defaults:
            continue
        yield year, train, test


def walk_forward(df: pd.DataFrame, model: str, imbalance: str, settings: dict) -> pd.DataFrame:
    """Out-of-time scores for every testable year, one row per test loan."""
    parts = []
    for year, train, test in forward_splits(
        df, settings["test_years"], settings["min_training_defaults"]
    ):
        X_train, y_train = xy(train)
        fitted = make_model(model, imbalance, y_train, settings["random_state"])
        fitted.fit(X_train, y_train.astype(int))
        parts.append(
            test[KEYS + [TARGET]].assign(
                score=fitted.predict_proba(xy(test)[0])[:, 1],
                test_year=year,
                training_loans=len(train),
                training_defaults=int(y_train.sum()),
            )
        )
    if not parts:
        raise ValueError("No test year has enough known defaults before it to train on.")
    return pd.concat(parts, ignore_index=True)


def member_folds(df: pd.DataFrame, model: str, imbalance: str, settings: dict) -> pd.DataFrame:
    """Scores with each member's loans held out together, one row per loan."""
    known = known_outcomes(df).reset_index(drop=True)
    X, y = xy(known)
    folds = GroupKFold(n_splits=min(settings["member_folds"], known["member_code"].nunique()))
    parts = []
    for fold, (train_idx, test_idx) in enumerate(folds.split(X, y, groups=known["member_code"])):
        y_train = y.iloc[train_idx].astype(int)
        fitted = make_model(model, imbalance, y_train, settings["random_state"])
        fitted.fit(X.iloc[train_idx], y_train)
        parts.append(
            known.iloc[test_idx][KEYS + [TARGET]].assign(
                score=fitted.predict_proba(X.iloc[test_idx])[:, 1], fold=fold
            )
        )
    return pd.concat(parts, ignore_index=True)


def metrics(pred: pd.DataFrame, n_boot: int = 1000, random_state: int = 42) -> dict[str, float]:
    """Ranking and calibration metrics for pooled test scores, with 95% intervals."""
    y = pred[TARGET].astype(int).to_numpy()
    s = pred["score"].to_numpy()
    out = {
        "loans": float(len(y)),
        "defaults": float(y.sum()),
        "default_share": float(y.mean()),
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
    """For each risk band: loans, defaults, the default rate, and its share of all defaults."""
    y = pred[TARGET].astype(int)
    table = (
        pd.DataFrame({"band": risk_band(pred["score"], bands), "defaulted": y})
        .groupby("band")["defaulted"]
        .agg(loans="size", defaults="sum")
        .reindex(BANDS, fill_value=0)
    )
    table["default_rate"] = (table["defaults"] / table["loans"].replace(0, np.nan)).round(3)
    table["share_of_defaults"] = (table["defaults"] / max(int(y.sum()), 1)).round(3)
    return table.reset_index()


def band_metrics(table: pd.DataFrame) -> dict[str, float]:
    """The high band's catch rate and precision, for comparing runs."""
    high = table.set_index("band").loc["high"]
    flagged = table.set_index("band").loc[["medium", "high"]]
    return {
        "high_band_share_of_defaults": float(high["share_of_defaults"]),
        "high_band_default_rate": float(0 if np.isnan(high["default_rate"]) else high["default_rate"]),
        "medium_or_high_share_of_defaults": float(flagged["share_of_defaults"].sum()),
        "high_band_loans": float(high["loans"]),
    }
