"""Export tests. Rows and names here are made up; no real Chama data is used."""
import json

import pandas as pd
import pytest

from chama import StepFailed
from chama.features.export import (
    EXPORT_COLUMNS,
    FILE_NAME,
    MANIFEST_NAME,
    check_columns,
    check_no_names,
    write,
)

CONFIG = {"default_statuses": ["topped_up", "overdue", "lost_track"], "history_months": 12}


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
    for col in EXPORT_COLUMNS:
        if col not in df.columns:
            df[col] = 1.0
    return df[EXPORT_COLUMNS]


def test_all_cleared_columns_pass():
    check_columns(features())


def test_a_column_not_cleared_stops_the_export():
    df = features().assign(remarks="paid by cash")
    with pytest.raises(StepFailed, match="remarks"):
        check_columns(df)


def test_a_missing_column_stops_the_export():
    with pytest.raises(StepFailed, match="amount"):
        check_columns(features().drop(columns="amount"))


def test_a_member_name_in_any_value_stops_the_export():
    df = features()
    df.loc[1, "status"] = "lost_track kamau"
    with pytest.raises(StepFailed, match="status"):
        check_no_names(df, ["John Kamau"])


def test_codes_and_statuses_are_not_mistaken_for_names():
    check_no_names(features(), ["John Kamau", "Mary Wanjiku"])


def test_writes_parquet_and_manifest(tmp_path):
    data_path, manifest_path = write(features(), tmp_path / "drive", CONFIG)

    assert data_path.name == FILE_NAME
    back = pd.read_parquet(data_path)
    assert list(back.columns) == EXPORT_COLUMNS
    assert len(back) == 3

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_path.name == MANIFEST_NAME
    assert manifest["rows"] == 3
    assert manifest["training_rows"] == 2
    assert manifest["defaults"] == 1
    assert manifest["members"] == 2
    assert manifest["default_statuses"] == CONFIG["default_statuses"]
