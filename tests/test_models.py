"""Model tests on made-up rows for both targets; no real Chama data is used."""
import numpy as np
import pandas as pd
import pytest

from chama.models.data import LOAN_DEFAULT, MISSED_REPAYMENT, TARGETS, add_derived, xy
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
from chama.models.train import target_settings

SETTINGS = {
    "test_years": [2021, 2022, 2023],
    "min_training_events": 5,
    "member_folds": 4,
    "random_state": 0,
}


def made_up(target, n=240, seed=0):
    """Rows 2016-2023 for 12 members; recent missed repayments raise the risk."""
    rng = np.random.default_rng(seed)
    months = pd.to_datetime("2016-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 8 * 365, n)), "D")
    months = months.to_period("M").to_timestamp()
    signal = rng.uniform(0, 1, n)
    event = (rng.uniform(0, 1, n) < 0.05 + 0.4 * signal).astype(int)
    df = pd.DataFrame({target.time: months, "member_code": [f"M-{i % 12:08d}" for i in range(n)]})
    for col in target.log_features:
        df[col] = rng.uniform(0, 2, n)          # log-scaled values are never negative
    for col in target.numeric_features:
        df[col] = rng.normal(size=n)
    for col in target.categorical_features:
        df[col] = rng.choice(["normal", "emergency", "school_fees"], n)
    df["recent_missed_share"] = signal
    df.loc[rng.uniform(0, 1, n) < 0.2, target.numeric_features[1]] = np.nan
    for key in target.keys:
        if key not in df.columns:
            df[key] = [f"{key}-{i}" for i in range(n)]
    df[target.label] = pd.array(event, dtype="Int64")
    df["in_training"] = True
    df["outcome_month"] = df[target.time] + pd.DateOffset(months=6)
    # the latest rows have no known outcome yet
    df.loc[df.index[-5:], ["in_training", target.label, "outcome_month"]] = [False, pd.NA, pd.NaT]
    return df


@pytest.mark.parametrize("target", TARGETS.values(), ids=list(TARGETS))
@pytest.mark.parametrize("imbalance", IMBALANCE)
@pytest.mark.parametrize("model", MODELS)
def test_every_target_model_and_strategy_gives_scores_between_0_and_1(target, model, imbalance):
    df = made_up(target)
    X, y = xy(df[df["in_training"]], target)
    y = y.astype(int)
    fitted = make_model(target, model, imbalance, y, random_state=0).fit(X, y)
    scores = fitted.predict_proba(X)[:, 1]
    assert scores.shape == (len(X),)
    assert np.all((scores >= 0) & (scores <= 1))


@pytest.mark.parametrize("imbalance", ["class_weight", "kmeans_smote", "cluster_centroids"])
def test_prior_correction_keeps_the_order_and_restores_the_real_share(imbalance):
    df = made_up(LOAN_DEFAULT)
    X, y = xy(df[df["in_training"]], LOAN_DEFAULT)
    y = y.astype(int)
    fitted = make_model(LOAN_DEFAULT, "logistic_regression", imbalance, y, random_state=0).fit(X, y)
    corrected = fitted.predict_proba(X)[:, 1]
    balanced = super(type(fitted), fitted).predict_proba(X)[:, 1]
    # same order: sorting by the balanced score sorts the corrected one too
    assert np.all(np.diff(corrected[np.argsort(balanced)]) >= -1e-12)
    # trained as if half the rows were events, the balanced scores sit far above
    # the real share; corrected, they come back close to it
    assert abs(corrected.mean() - y.mean()) < abs(balanced.mean() - y.mean())
    assert abs(corrected.mean() - y.mean()) < 0.1


@pytest.mark.parametrize("target", TARGETS.values(), ids=list(TARGETS))
def test_walk_forward_learns_only_from_outcomes_known_before_the_test_year(target):
    df = made_up(target)
    for year, train, test in forward_splits(df, target, SETTINGS["test_years"], 5):
        start = pd.Timestamp(year=year, month=1, day=1)
        assert (train[target.time] < start).all()
        assert (train["outcome_month"] < start).all()
        assert (test[target.time].dt.year == year).all()
        assert train["in_training"].all() and test["in_training"].all()


def test_a_year_with_too_few_known_events_is_skipped():
    years = [y for y, _, _ in forward_splits(made_up(LOAN_DEFAULT), LOAN_DEFAULT, [2016, 2022], 5)]
    assert years == [2022]


@pytest.mark.parametrize("target", TARGETS.values(), ids=list(TARGETS))
def test_walk_forward_scores_each_test_row_once(target):
    df = made_up(target)
    pred = walk_forward(df, target, "logistic_regression", "none", SETTINGS)
    tested = df[df["in_training"] & df[target.time].dt.year.isin(SETTINGS["test_years"])]
    key = target.keys[0]
    assert sorted(pred[key]) == sorted(tested[key])
    assert set(pred["actual"]) <= {0, 1}


def test_held_out_members_are_never_in_their_own_training_fold():
    df = made_up(MISSED_REPAYMENT)
    pred = member_folds(df, MISSED_REPAYMENT, "logistic_regression", "none", SETTINGS)
    assert pred.groupby("member_code")["fold"].nunique().max() == 1
    assert len(pred) == df["in_training"].sum()


def test_metrics_for_a_perfect_ranking():
    pred = pd.DataFrame({"actual": [0, 0, 0, 1, 1], "score": [0.1, 0.2, 0.3, 0.8, 0.9]})
    m = metrics(pred, n_boot=50)
    assert m["roc_auc"] == 1.0 and m["pr_auc"] == 1.0
    assert m["event_share"] == pytest.approx(0.4)


def test_risk_bands_and_their_table():
    bands = {"medium": 0.15, "high": 0.30}
    assert list(risk_band([0.05, 0.15, 0.29, 0.30, 0.9], bands)) == [
        "low", "medium", "medium", "high", "high"]
    pred = pd.DataFrame({"actual": [0, 0, 1, 1], "score": [0.05, 0.2, 0.2, 0.5]})
    table = band_table(pred, bands).set_index("band")
    assert table.loc["medium", "rows"] == 2
    assert table.loc["high", "share_of_events"] == 0.5


@pytest.mark.parametrize("model", MODELS)
def test_shap_gives_one_contribution_per_row_and_prepared_feature(model):
    df = made_up(LOAN_DEFAULT)
    X, y = xy(df[df["in_training"]], LOAN_DEFAULT)
    y = y.astype(int)
    fitted = make_model(LOAN_DEFAULT, model, "none", y, random_state=0).fit(X, y)
    contributions = shap_values(fitted, X.head(10), background=X)
    assert contributions.shape == prepared(fitted, X.head(10)).shape
    factors = top_factors(contributions.iloc[0], n=3)
    assert len(factors) == 3
    assert set(factors["effect"]) <= {"raises risk", "lowers risk"}


def test_debt_relative_to_the_new_loan_replaces_raw_amounts():
    df = add_derived(pd.DataFrame({"outstanding_at_issue": [50_000, 0, 10_000],
                                   "amount": [100_000, 20_000, 0]}))
    assert df["outstanding_vs_amount"].tolist()[:2] == [0.5, 0.0]
    assert np.isnan(df["outstanding_vs_amount"].iloc[2])      # no amount: left empty
    assert "amount" not in LOAN_DEFAULT.features
    assert "outstanding_at_issue" not in LOAN_DEFAULT.features


def test_each_target_gets_the_shared_settings_and_its_own():
    config = {"modelling": {"random_state": 1, "models": ["xgboost"],
                            "targets": {"loan_default": {"test_years": [2020]},
                                        "missed_repayment": {"test_years": [2019, 2020]}}}}
    settings = target_settings(config, "missed_repayment")
    assert settings["random_state"] == 1 and settings["models"] == ["xgboost"]
    assert settings["test_years"] == [2019, 2020]
    assert "targets" not in settings
