"""Anonymisation tests. Names here are made up; no real Chama data is used."""
import pandas as pd
import pytest

from chama import StepFailed
from chama.anonymisation.anonymise import (
    anonymise_chama,
    code_table,
    date_only,
    find_names,
    staging_columns,
)
from chama.ingestion.raw_format import expected_columns

KEY = b"test-key-only"
ALIASES = {"john kamau": "John Kamau", "j kamau": "John Kamau", "mary wanjiku": "Mary Wanjiku"}


def raw_table(table, rows):
    """A raw table as the loader leaves it: every expected column plus lineage."""
    df = pd.DataFrame(rows).reindex(columns=expected_columns(table))
    df["chama_id"] = "chama_test"
    df["source_file"] = "2014.xlsx"
    df["source_row"] = range(2, len(df) + 2)
    return df


def raw_frames():
    return {
        "statements": raw_table(
            "statements",
            [
                {"member_name": "John Kamau", "loan_before": "40,000", "due": "Jan 2015",
                 "remarks": "J. Kamau wrote above", "source_photo": "p001.jpg"},
                {"member_name": "J. Kamau", "loan_before": "35000", "source_photo": "p002.jpg"},
                {"member_name": "Mary Wanjiku", "loan_before": "-", "source_photo": "p002.jpg"},
            ],
        ),
        "meetings": raw_table(
            "meetings",
            [{"host": "Mary Wanjiku's house", "notes": "Loans: John Kamau 60 000",
              "next_meeting": "Mary Wanjiku's 9th Feb", "source_photo": "p001.jpg"}],
        ),
        "new_loans": raw_table(
            "new_loans",
            [{"member_name": "John Kamau", "amount": "60 000", "source_photo": "p001.jpg"},
             {"member_name": None, "amount": "5000/=", "remarks": "name cut off"}],
        ),
    }


def test_spellings_of_one_member_get_one_code():
    staging = anonymise_chama(raw_frames(), "chama_test", ALIASES, KEY)
    codes = list(staging["statements"]["member_code"])
    assert codes[0] == codes[1] != codes[2]
    assert all(c.startswith("M-") for c in codes)


def test_no_name_or_free_text_reaches_staging():
    staging = anonymise_chama(raw_frames(), "chama_test", ALIASES, KEY)
    for table, df in staging.items():
        assert list(df.columns) == staging_columns(table)
        assert not {"member_name", "remarks", "notes", "host"} & set(df.columns)
    assert find_names(staging, list(ALIASES) + list(ALIASES.values())) == {}


def test_next_meeting_keeps_only_the_date():
    staging = anonymise_chama(raw_frames(), "chama_test", ALIASES, KEY)
    assert staging["meetings"].loc[0, "next_meeting_date"] == "9th Feb"


def test_values_and_lineage_are_kept_as_written():
    st = anonymise_chama(raw_frames(), "chama_test", ALIASES, KEY)["statements"]
    assert list(st["loan_before"]) == ["40,000", "35000", "-"]
    assert list(st["source_photo"]) == ["p001.jpg", "p002.jpg", "p002.jpg"]


def test_a_loan_with_no_name_keeps_an_empty_code():
    loans = anonymise_chama(raw_frames(), "chama_test", ALIASES, KEY)["new_loans"]
    assert pd.isna(loans.loc[1, "member_code"])


def test_stops_when_a_spelling_has_not_been_reviewed():
    aliases = {k: v for k, v in ALIASES.items() if k != "j kamau"}
    with pytest.raises(StepFailed, match="1 name spellings"):
        anonymise_chama(raw_frames(), "chama_test", aliases, KEY)


def test_name_check_finds_a_name_in_a_kept_column():
    staging = anonymise_chama(raw_frames(), "chama_test", ALIASES, KEY)
    staging["statements"].loc[0, "due"] = "ask Kamau"
    assert find_names(staging, ALIASES.values()) == {"statements.due": 1}


def test_name_check_ignores_month_names():
    staging = {"statements": pd.DataFrame({"due": ["June 2014"]})}
    assert find_names(staging, ["June Akinyi"]) == {}


def test_one_code_per_member():
    codes = code_table(ALIASES, "chama_test", KEY)
    assert sorted(codes["canonical_name"]) == ["John Kamau", "Mary Wanjiku"]
    assert codes["member_code"].is_unique


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Mary Wanjiku's 9th Feb", "9th Feb"),
        ("John Kamau on 9th March 2014", "9th March 2014"),
        ("next: 3/8/2014 at the hall", "3/8/2014"),
        ("Mary to confirm", None),
        (None, None),
    ],
)
def test_date_only(text, expected):
    assert date_only(text) == expected
