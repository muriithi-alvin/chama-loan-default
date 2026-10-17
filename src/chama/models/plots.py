"""Figures for each training run, logged to MLflow and shown in the notebooks.

Built with matplotlib's Figure directly (no pyplot), so they work the same in
a terminal, in Jupyter and in Colab.
"""
from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure
from sklearn.calibration import calibration_curve
from sklearn.metrics import precision_recall_curve

from chama.models.data import TARGET


def precision_recall(pred: pd.DataFrame, title: str) -> Figure:
    """Precision against recall of defaults; the dashed line is chance."""
    y = pred[TARGET].astype(int)
    precision, recall, _ = precision_recall_curve(y, pred["score"])
    fig = Figure(figsize=(5, 4), layout="constrained")
    ax = fig.subplots()
    ax.step(recall, precision, where="post")
    ax.axhline(y.mean(), linestyle="--", color="grey", label=f"chance ({y.mean():.2f})")
    ax.set(xlabel="Recall (share of defaults caught)", ylabel="Precision", title=title,
           xlim=(0, 1), ylim=(0, 1.05))
    ax.legend(loc="upper right")
    return fig


def calibration(pred: pd.DataFrame, title: str, bins: int = 5) -> Figure:
    """Average score against the share that defaulted, in equal-sized groups."""
    y = pred[TARGET].astype(int)
    observed, predicted = calibration_curve(y, pred["score"], n_bins=bins, strategy="quantile")
    fig = Figure(figsize=(5, 4), layout="constrained")
    ax = fig.subplots()
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfect")
    ax.plot(predicted, observed, marker="o", label="model")
    ax.set(xlabel="Average risk score", ylabel="Share that defaulted", title=title,
           xlim=(0, 1), ylim=(0, 1))
    ax.legend(loc="upper left")
    return fig


def importance_bar(importance: pd.Series, title: str, top: int = 15) -> Figure:
    """Mean absolute SHAP contribution of the strongest features."""
    shown = importance.head(top)[::-1]
    fig = Figure(figsize=(6, 0.35 * len(shown) + 1.2), layout="constrained")
    ax = fig.subplots()
    ax.barh(shown.index, shown.to_numpy())
    ax.set(xlabel="Mean |SHAP contribution|", title=title)
    return fig
