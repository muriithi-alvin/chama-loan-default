"""SHAP explanations: which factors raised or lowered a loan's risk score.

Contributions are on the model's own scale (log-odds for logistic regression
and XGBoost, probability for the random forest), so compare them within one
model. Columns are the prepared features, for example
`missingindicator_amount_vs_own_max` (1 when the member had no earlier loan of
the type) or `loan_type_emergency`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import LogisticRegression


def prepared(model, X: pd.DataFrame) -> pd.DataFrame:
    """The features as the classifier sees them, with their names."""
    prep = model.named_steps["prep"]
    return pd.DataFrame(prep.transform(X), columns=prep.get_feature_names_out(), index=X.index)


def shap_values(model, X: pd.DataFrame, background: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per loan, one column per prepared feature: its push on the score.

    `background` (usually the training loans) is the reference that linear
    contributions are measured from; trees need none.
    """
    Xp = prepared(model, X)
    clf = model.named_steps["model"]
    if isinstance(clf, LogisticRegression):
        reference = prepared(model, background) if background is not None else Xp
        values = shap.LinearExplainer(clf, reference).shap_values(Xp)
    else:
        values = shap.TreeExplainer(clf).shap_values(Xp)
    if isinstance(values, list):   # older shap: one array per class
        values = values[1]
    values = np.asarray(values)
    if values.ndim == 3:           # (loans, features, classes)
        values = values[:, :, 1]
    return pd.DataFrame(values, columns=Xp.columns, index=X.index)


def importance(contributions: pd.DataFrame) -> pd.Series:
    """Mean absolute contribution per feature, largest first."""
    return contributions.abs().mean().sort_values(ascending=False)


def top_factors(contributions: pd.Series, n: int = 3) -> pd.DataFrame:
    """The n strongest factors for one loan, with the direction of each."""
    strongest = contributions.abs().sort_values(ascending=False).index[:n]
    values = contributions[strongest]
    return pd.DataFrame({
        "factor": strongest,
        "contribution": values.round(3).to_numpy(),
        "effect": np.where(values > 0, "raises risk", "lowers risk"),
    })
