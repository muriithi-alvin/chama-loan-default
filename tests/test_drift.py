"""The drift report's parts (S-7), with made-up rows; Evidently itself is not run."""
import numpy as np
import pandas as pd
import pytest

from chama import StepFailed
from chama.models.data import MISSED_REPAYMENT
from chama.models.drift import drift_table, split


def rows(chama, months, known=True):
    df = pd.DataFrame({f: np.arange(len(months), dtype=float) for f in MISSED_REPAYMENT.features})
    df["chama_id"] = chama
    df["meeting_month"] = pd.to_datetime(months)
    df["in_training"] = known
    return df


def test_recent_rows_are_compared_with_the_earlier_rows_the_model_learned_from():
    months = pd.date_range("2020-01-01", "2025-12-01", freq="MS")
    df = rows("chama_b", months)
    reference, current = split(df, "chama_b", ("chama_b",), months=12, whole_chama=False)
    assert len(current) == 12 and len(reference) == len(months) - 12
    assert list(current.columns) == list(MISSED_REPAYMENT.features)


def test_a_test_only_chama_is_compared_whole_with_the_training_chama():
    df = pd.concat([rows("chama_b", pd.date_range("2018-01-01", periods=60, freq="MS")),
                    rows("chama_a", pd.date_range("2024-01-01", periods=20, freq="MS"), known=False)])
    reference, current = split(df, "chama_a", ("chama_b",), months=12, whole_chama=True)
    assert len(current) == 20 and len(reference) == 60


def test_too_few_rows_are_refused():
    df = rows("chama_b", pd.date_range("2025-01-01", periods=14, freq="MS"))
    with pytest.raises(StepFailed, match="Too few rows"):
        split(df, "chama_b", ("chama_b",), months=12, whole_chama=False)


def test_each_feature_is_marked_drifted_by_its_own_test():
    report = {"metrics": [
        {"metric_name": "DriftedColumnsCount(drift_share=0.5)", "value": {"count": 2.0, "share": 0.67}},
        {"metric_name": "ValueDrift(column=a,method=K-S p_value,threshold=0.05)", "value": 0.001},
        {"metric_name": "ValueDrift(column=b,method=K-S p_value,threshold=0.05)", "value": 0.4},
        {"metric_name": "ValueDrift(column=c,method=Wasserstein distance (normed),threshold=0.1)", "value": 0.3},
    ]}
    table, overall = drift_table(report)
    assert overall == {"drifted_features": 2.0, "drifted_share": 0.67}
    assert dict(zip(table["feature"], table["drifted"])) == {"a": True, "b": False, "c": True}
