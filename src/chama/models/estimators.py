"""The three models and the ways of handling the class imbalance.

Every model is an imbalanced-learn pipeline: preparation, then (optionally) a
resampler, then the classifier. The resampler runs only when the pipeline is
fitted, so it changes the training loans and never the loans being scored.

Settings are deliberately cautious for a small data set (a few hundred loans,
a dozen members): shallow trees, many samples per leaf, strong regularisation.

Imbalance strategies (decision D-020), compared on the same tests:
  none               learn from the loans as they are
  class_weight       count each default as much as all repaid loans together
  kmeans_smote       group the training loans with k-means and add synthetic
                     defaults inside the groups where defaults occur
  cluster_centroids  shrink the repaid loans to one real loan per k-means group
                     until the classes are equal
Weighting and resampling raise the scores of every loan, so their scores read
less directly as probabilities; the Brier score and calibration plot show this.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from imblearn.over_sampling import KMeansSMOTE
from imblearn.pipeline import Pipeline
from imblearn.under_sampling import ClusterCentroids
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from chama.models.data import CATEGORICAL_FEATURES, LOG_FEATURES, NUMERIC_FEATURES

MODELS = ["logistic_regression", "random_forest", "xgboost"]
IMBALANCE = ["none", "class_weight", "kmeans_smote", "cluster_centroids"]


def preparation() -> ColumnTransformer:
    """Fill gaps, log-scale amounts, standardise, and one-hot the loan type.

    Missing values get the training median plus a 0/1 column saying the value
    was missing (for example "no earlier loan of this type"). Scaling does not
    change the trees, but k-means and SMOTE need comparable distances.
    """
    log_scaled = Pipeline([
        ("fill", SimpleImputer(strategy="median")),
        ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
        ("scale", StandardScaler()),
    ])
    numeric = Pipeline([
        ("fill", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    return ColumnTransformer(
        [
            ("log", log_scaled, LOG_FEATURES),
            ("num", numeric, NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             CATEGORICAL_FEATURES),
        ],
        verbose_feature_names_out=False,
    )


def classifier(name: str, weighted: bool, y_train: pd.Series, random_state: int):
    if name == "logistic_regression":
        return LogisticRegression(
            C=0.3, class_weight="balanced" if weighted else None, max_iter=2000
        )
    if name == "random_forest":
        return RandomForestClassifier(
            n_estimators=500, max_depth=4, min_samples_leaf=5, max_features="sqrt",
            class_weight="balanced_subsample" if weighted else None,
            random_state=random_state, n_jobs=-1,
        )
    if name == "xgboost":
        defaults = int(y_train.sum())
        return XGBClassifier(
            n_estimators=300, max_depth=2, learning_rate=0.05, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=3, reg_lambda=5.0,
            scale_pos_weight=(len(y_train) - defaults) / defaults if weighted and defaults else 1.0,
            eval_metric="logloss", random_state=random_state, n_jobs=1,
        )
    raise ValueError(f"Unknown model {name!r}; choose from {', '.join(MODELS)}")


def resampler(imbalance: str, y_train: pd.Series, random_state: int):
    """The k-means resampler for a strategy, or None."""
    if imbalance == "kmeans_smote":
        defaults = int(y_train.sum())
        return KMeansSMOTE(
            # few, large groups: with a few dozen defaults, small groups would
            # hold too few defaults to interpolate between
            kmeans_estimator=KMeans(
                n_clusters=max(2, min(5, defaults // 10)), n_init=10, random_state=random_state
            ),
            cluster_balance_threshold=0.0,
            k_neighbors=max(1, min(3, defaults - 1)),
            random_state=random_state,
        )
    if imbalance == "cluster_centroids":
        # "hard" voting keeps real loans (the nearest to each centroid)
        return ClusterCentroids(
            estimator=KMeans(n_init=10, random_state=random_state),
            voting="hard", random_state=random_state,
        )
    if imbalance in ("none", "class_weight"):
        return None
    raise ValueError(f"Unknown imbalance strategy {imbalance!r}; choose from {', '.join(IMBALANCE)}")


def make_model(name: str, imbalance: str, y_train: pd.Series, random_state: int = 42) -> Pipeline:
    """An unfitted pipeline for one model and one imbalance strategy."""
    steps = [("prep", preparation())]
    sampler = resampler(imbalance, y_train, random_state)
    if sampler is not None:
        steps.append(("resample", sampler))
    steps.append(("model", classifier(name, imbalance == "class_weight", y_train, random_state)))
    return Pipeline(steps)
