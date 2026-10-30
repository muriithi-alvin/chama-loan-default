"""The held-out chama test (D-029), with made-up rows and a stand-in model."""
import numpy as np
import pandas as pd
import pytest

from chama import StepFailed
from chama.models.data import MISSED_REPAYMENT
from chama.models.held_out import evaluate, run

SETTINGS = {"bootstrap_samples": 50, "random_state": 42, "band_shares": {"high": 0.2, "medium": 0.3}}


def rows(n=60, missed_every=4, known=True):
    """n member-meetings; every `missed_every`-th one missed a repayment."""
    df = pd.DataFrame({f: np.zeros(n) for f in MISSED_REPAYMENT.features})
    df["missed_last_3_meetings"] = [(i % missed_every == 0) * 2 for i in range(n)]
    df[MISSED_REPAYMENT.label] = pd.array([int(i % missed_every == 0) for i in range(n)], dtype="Int64")
    df["in_training"] = known
    df["member_month_id"] = range(n)
    df["member_code"] = [f"M-{i % 7}" for i in range(n)]
    df["page_no"] = [i // 7 for i in range(n)]
    df["meeting_month"] = pd.Timestamp("2024-01-01")
    return df


class StandIn:
    """Scores a row by its recent misses, as a trained model roughly would."""
    def predict_proba(self, X):
        s = X["missed_last_3_meetings"].to_numpy() / 3 * 0.8 + 0.1
        return np.column_stack([1 - s, s])


def test_the_order_is_measured_like_the_walk_forward_test():
    result = evaluate(rows(), StandIn(), {"medium": 0.2, "high": 0.5}, SETTINGS)
    m = result["metrics"]
    assert m["rows"] == 60 and m["events"] == 15
    assert m["roc_auc"] == pytest.approx(1.0)
    high = result["bands_trained_cutoffs"].set_index("band").loc["high"]
    assert high["event_rate"] == 1.0
    assert set(result["pred"].columns) >= {"member_code", "actual", "score"}


def test_too_few_missed_repayments_are_refused_with_a_reason():
    with pytest.raises(StepFailed, match="too few to test on"):
        evaluate(rows(n=12, missed_every=6), StandIn(), {"medium": 0.2, "high": 0.5}, SETTINGS)


def test_rows_whose_outcome_is_not_known_yet_are_left_out():
    df = pd.concat([rows(), rows(n=10, known=False)], ignore_index=True)
    assert evaluate(df, StandIn(), {"medium": 0.2, "high": 0.5}, SETTINGS)["metrics"]["rows"] == 60


def test_a_chama_the_model_may_have_learned_from_is_refused():
    config = {"chamas": [{"id": "chama_b"}]}
    with pytest.raises(StepFailed, match="not marked test_only"):
        run(None, config, "chama_b")
