"""Export tests. Rows and names here are made up; no real Chama data is used."""
import json

import pandas as pd
import pytest

from chama import StepFailed
from chama.features.export import TABLES, check_columns, check_no_names, write

CONFIG = {"default_statuses": ["topped_up", "overdue", "lost_track"], "history_months": 12,
          "warning_horizon_meetings": 3}
LOANS = TABLES["loan_features"]


def features():
    """Three loans with every exported column: two finished, one open."""
    df = pd.DataFrame(
        {
            "loan_id": ["c-p001-1", "c-p002-1", "c-p003-1"],
            "chama_id": "c",
            "member_code": ["M-aaaa1111", "M-aaaa1111", "M-bbbb2222"],
            "issued_month": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
            "issue_source": "new_loans_list",
            "loan_type": ["normal", "emergency", "normal"],
            "status": ["repaid_on_time", "lost_track", "open"],
            "defaulted": pd.array([0, 1, None], dtype="Int64"),
            "in_training": [True, True, False],
            "outcome_month": pd.to_datetime(["2020-06-01", "2020-05-01", None]),
        }
    )
    for col in LOANS.columns:
        if col not in df.columns:
            df[col] = 1.0
    return df[list(LOANS.columns)]


def test_both_modelling_tables_are_exported():
    assert set(TABLES) == {"loan_features", "member_months"}
    for table in TABLES.values():
        assert {"member_code", table.label, table.time, "in_training", "outcome_month"} <= set(
            table.columns)


def test_all_cleared_columns_pass():
    check_columns(features(), LOANS)


def test_a_column_not_cleared_stops_the_export():
    df = features().assign(remarks="paid by cash")
    with pytest.raises(StepFailed, match="remarks"):
        check_columns(df, LOANS)


def test_a_missing_column_stops_the_export():
    with pytest.raises(StepFailed, match="amount"):
        check_columns(features().drop(columns="amount"), LOANS)


def test_a_member_name_in_any_value_stops_the_export():
    df = features()
    df.loc[1, "status"] = "lost_track kamau"
    with pytest.raises(StepFailed, match="status"):
        check_no_names(df, ["John Kamau"])


def test_codes_and_statuses_are_not_mistaken_for_names():
    check_no_names(features(), ["John Kamau", "Mary Wanjiku"])


def test_writes_parquet_and_manifest(tmp_path):
    data_path, manifest_path = write(features(), tmp_path / "drive", CONFIG, LOANS)

    assert data_path.name == "loan_features.parquet"
    back = pd.read_parquet(data_path)
    assert list(back.columns) == list(LOANS.columns)
    assert len(back) == 3

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_path.name == "loan_features_manifest.json"
    assert manifest["rows"] == 3
    assert manifest["training_rows"] == 2
    assert manifest["label"] == "defaulted"
    assert manifest["events"] == 1
    assert manifest["members"] == 2
    assert manifest["default_statuses"] == CONFIG["default_statuses"]
    assert manifest["warning_horizon_meetings"] == 3


def test_demo_and_test_only_chamas_never_reach_the_modelling_tables():
    from chama.features.export import not_for_training

    config = {"chamas": [{"id": "chama_a", "test_only": True}, {"id": "chama_b"},
                         {"id": "chama_demo", "demo": True}]}
    assert not_for_training(config) == ("chama_a", "chama_demo")
