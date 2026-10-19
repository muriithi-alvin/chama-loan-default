"""Model tests on made-up loans; no real Chama data is used."""
import numpy as np
import pandas as pd
import pytest

from chama.models.data import FEATURES, TARGET, xy
from chama.models.estimators import IMBALANCE, MODELS, make_model
from chama.models.evaluate import (
    band_table,
    forward_splits,
    member_folds,
    metrics,
    risk_band,
    walk_forward,
)
from chama.models.explain import prepared, shap_values, top_factors

SETTINGS = {
    "test_years": [2021, 2022, 2023],
    "min_training_defaults": 5,
    "member_folds": 4,
    "random_state": 0,
}


def made_up_loans(n=240, seed=0):
    """Loans 2016-2023 for 12 members; missed repayments raise the default risk."""
    rng = np.random.default_rng(seed)
    issued = pd.to_datetime("2016-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 8 * 365, n)), "D")
    issued = issued.to_period("M").to_timestamp()
    missed = rng.uniform(0, 1, n)
    defaulted = (rng.uniform(0, 1, n) < 0.05 + 0.4 * missed).astype(int)
    df = pd.DataFrame({
        "loan_id": [f"c-p{i:03d}-1" for i in range(n)],
        "member_code": [f"M-{i % 12:08d}" for i in range(n)],
        "loan_type": rng.choice(["normal", "emergency", "school_fees"], n),
        "issued_month": issued,
        "issue_year": issued.year,
        "status": np.where(defaulted == 1, "lost_track", "repaid_on_time"),
        "amount": rng.uniform(5_000, 200_000, n),
        "outstanding_at_issue": rng.uniform(0, 100_000, n),
        "recent_missed_share": missed,
        "is_rollover": rng.uniform(0, 1, n) < 0.1,
    })
    for col in FEATURES:
        if col not in df.columns:
            df[col] = rng.normal(size=n)
    df.loc[rng.uniform(0, 1, n) < 0.2, "amount_vs_own_max"] = np.nan   # no earlier loan
    df.loc[df["issue_year"] < 2017, "recent_contribution_rate"] = np.nan
    df[TARGET] = pd.array(defaulted, dtype="Int64")
    df["in_training"] = True
    df["outcome_month"] = df["issued_month"] + pd.DateOffset(months=6)
    # the latest loans are still open
    df.loc[df.index[-5:], ["in_training", TARGET, "outcome_month"]] = [False, pd.NA, pd.NaT]
    return df


@pytest.mark.parametrize("imbalance", IMBALANCE)
@pytest.mark.parametrize("model", MODELS)
def test_every_model_and_strategy_gives_scores_between_0_and_1(model, imbalance):
    df = made_up_loans()
    X, y = xy(df[df["in_training"]])
    fitted = make_model(model, imbalance, y.astype(int), random_state=0).fit(X, y.astype(int))
    scores = fitted.predict_proba(X)[:, 1]
    assert scores.shape == (len(X),)
    assert np.all((scores >= 0) & (scores <= 1))


@pytest.mark.parametrize("imbalance", ["class_weight", "kmeans_smote", "cluster_centroids"])
def test_prior_correction_keeps_the_order_and_restores_the_real_share(imbalance):
    df = made_up_loans()
    X, y = xy(df[df["in_training"]])
    y = y.astype(int)
    fitted = make_model("logistic_regression", imbalance, y, random_state=0).fit(X, y)
    corrected = fitted.predict_proba(X)[:, 1]
    balanced = super(type(fitted), fitted).predict_proba(X)[:, 1]
    # same order: sorting by the balanced score sorts the corrected one too
    assert np.all(np.diff(corrected[np.argsort(balanced)]) >= -1e-12)
    # trained as if half defaulted, the balanced scores sit far above the real share;
    # corrected, they come back close to it
    assert abs(corrected.mean() - y.mean()) < abs(balanced.mean() - y.mean())
    assert abs(corrected.mean() - y.mean()) < 0.1


def test_resampling_changes_training_loans_only():
    df = made_up_loans()
    X, y = xy(df[df["in_training"]])
    fitted = make_model("logistic_regression", "kmeans_smote", y.astype(int)).fit(X, y.astype(int))
    assert len(fitted.predict_proba(X)) == len(X)


def test_walk_forward_learns_only_from_outcomes_known_before_the_test_year():
    df = made_up_loans()
    for year, train, test in forward_splits(df, SETTINGS["test_years"], 5):
        start = pd.Timestamp(year=year, month=1, day=1)
        assert (train["issued_month"] < start).all()
        assert (train["outcome_month"] < start).all()
        assert (test["issue_year"] == year).all()
        assert train["in_training"].all() and test["in_training"].all()


def test_a_year_with_too_few_known_defaults_is_skipped():
    years = [year for year, _, _ in forward_splits(made_up_loans(), [2016, 2022], 5)]
    assert years == [2022]


def test_walk_forward_scores_each_test_loan_once():
    df = made_up_loans()
    pred = walk_forward(df, "logistic_regression", "none", SETTINGS)
    tested = df[df["in_training"] & df["issue_year"].isin(SETTINGS["test_years"])]
    assert sorted(pred["loan_id"]) == sorted(tested["loan_id"])


def test_held_out_members_are_never_in_their_own_training_fold():
    df = made_up_loans()
    pred = member_folds(df, "logistic_regression", "none", SETTINGS)
    assert pred.groupby("member_code")["fold"].nunique().max() == 1
    assert len(pred) == df["in_training"].sum()


def test_metrics_for_a_perfect_ranking():
    pred = pd.DataFrame({TARGET: [0, 0, 0, 1, 1], "score": [0.1, 0.2, 0.3, 0.8, 0.9]})
    m = metrics(pred, n_boot=50)
    assert m["roc_auc"] == 1.0 and m["pr_auc"] == 1.0
    assert m["default_share"] == pytest.approx(0.4)


def test_risk_bands_and_their_table():
    bands = {"medium": 0.15, "high": 0.30}
    assert list(risk_band([0.05, 0.15, 0.29, 0.30, 0.9], bands)) == [
        "low", "medium", "medium", "high", "high"]
    pred = pd.DataFrame({TARGET: [0, 0, 1, 1], "score": [0.05, 0.2, 0.2, 0.5]})
    table = band_table(pred, bands).set_index("band")
    assert table.loc["medium", "loans"] == 2
    assert table.loc["high", "share_of_defaults"] == 0.5


@pytest.mark.parametrize("model", MODELS)
def test_shap_gives_one_contribution_per_loan_and_prepared_feature(model):
    df = made_up_loans()
    X, y = xy(df[df["in_training"]])
    fitted = make_model(model, "none", y.astype(int), random_state=0).fit(X, y.astype(int))
    contributions = shap_values(fitted, X.head(10), background=X)
    assert contributions.shape == prepared(fitted, X.head(10)).shape
    factors = top_factors(contributions.iloc[0], n=3)
    assert len(factors) == 3
    assert set(factors["effect"]) <= {"raises risk", "lowers risk"}
