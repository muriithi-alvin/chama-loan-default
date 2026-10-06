"""Name-matching tests. Names here are made up; no real Chama data is used."""
import pandas as pd
import pytest

from chama import StepFailed
from chama.anonymisation.aliases import (
    MATCH_THRESHOLD,
    name_counts,
    name_similarity,
    read_review_file,
    suggest_aliases,
    write_review_file,
)


def names(**occurrences):
    """name_counts()-style frame: names(john_kamau=3) -> 'john kamau' seen 3 times."""
    return pd.DataFrame(
        {
            "raw_name": [n.replace("_", " ") for n in occurrences],
            "occurrences": list(occurrences.values()),
            "first_photo": "p001.jpg",
        }
    )


@pytest.mark.parametrize(
    "a, b",
    [
        ("John Kamau", "J. Kamau"),  # initial
        ("John Kamau", "Kamau John"),  # swapped order
        ("Mary Wanjiku", "Mary Wanjiko"),  # spelling slip
        ("John Kamau", "Kamau"),  # a name missing
    ],
)
def test_likely_spellings_of_one_person_match(a, b):
    assert name_similarity(a, b) >= MATCH_THRESHOLD


@pytest.mark.parametrize("a, b", [("John Kamau", "Peter Otieno"), ("John Kamau", "John Kariuki")])
def test_different_people_do_not_match(a, b):
    assert name_similarity(a, b) < MATCH_THRESHOLD


def test_counts_spellings_and_first_photo():
    statements = pd.DataFrame(
        {
            "member_name": ["John Kamau", "john  kamau", None, "Mary Wanjiku"],
            "source_photo": ["p002.jpg", "p001.jpg", "p001.jpg", "p003.jpg"],
        }
    )
    counts = name_counts([statements]).set_index("raw_name")
    assert counts.loc["john kamau", "occurrences"] == 2
    assert counts.loc["john kamau", "first_photo"] == "p001.jpg"
    assert len(counts) == 2  # the blank name is ignored


def test_variants_are_grouped_under_the_fullest_spelling():
    result = suggest_aliases(names(j_kamau=5, john_kamau=2, kamau_john=1, mary_wanjiku=4))
    by_spelling = result.set_index("raw_name")
    assert set(by_spelling.loc[["j kamau", "john kamau", "kamau john"], "canonical_name"]) == {
        "John Kamau"
    }
    assert by_spelling.loc["john kamau", "status"] == "new"
    assert by_spelling.loc["j kamau", "status"] == "check"
    assert by_spelling.loc["mary wanjiku", "status"] == "new"


def test_a_close_but_separate_member_is_pointed_out():
    result = suggest_aliases(names(john_kamau=5, john_kariuki=3)).set_index("raw_name")
    assert result.loc["john kariuki", "status"] == "new"
    assert result.loc["john kariuki", "similar_to"].startswith("John Kamau (")


def test_reviewed_names_are_kept_and_new_spellings_join_them():
    reviewed = {"john kamau": "John Kamau", "j kamau": "John Kamau"}
    result = suggest_aliases(names(john_kamau=3, j_kamau=1, jon_kamau=1), reviewed)
    by_spelling = result.set_index("raw_name")
    assert by_spelling.loc["j kamau", "status"] == "reviewed"
    assert by_spelling.loc["jon kamau", "canonical_name"] == "John Kamau"
    assert by_spelling.loc["jon kamau", "status"] == "check"


def test_review_file_round_trip(tmp_path):
    path = write_review_file(suggest_aliases(names(john_kamau=2, j_kamau=1)), tmp_path / "a.csv")
    assert read_review_file(path) == {"john kamau": "John Kamau", "j kamau": "John Kamau"}


def test_review_file_with_a_blank_name_is_refused(tmp_path):
    path = tmp_path / "a.csv"
    pd.DataFrame({"raw_name": ["john kamau", "j kamau"], "canonical_name": ["John Kamau", ""]}).to_csv(
        path, index=False
    )
    with pytest.raises(StepFailed, match="rows \\[3\\]"):
        read_review_file(path)


def test_review_file_giving_one_spelling_two_names_is_refused(tmp_path):
    path = tmp_path / "a.csv"
    pd.DataFrame(
        {"raw_name": ["J. Kamau", "j kamau"], "canonical_name": ["John Kamau", "James Kamau"]}
    ).to_csv(path, index=False)
    with pytest.raises(StepFailed, match="two different names"):
        read_review_file(path)
