"""Fictional names for demo mode (G5) and the demo chama copy (D-028)."""
import pandas as pd

from chama.web.services import demo, names


def test_fictional_names_are_fixed_per_code_and_distinct():
    codes = [f"M-{i:08x}" for i in range(12)]
    first = names.fictional_names(codes, ["Jane Doe"])
    again = names.fictional_names(list(reversed(codes)), ["Jane Doe"])
    assert first == again
    assert len(set(first.values())) == len(codes)


def test_no_fictional_name_shares_a_word_with_a_real_name():
    real = ["Wanjiru Njoroge", "Halima Achieng", "m. otieno"]
    chosen = names.fictional_names([f"M-{i}" for i in range(20)], real)
    words = names.name_words(real)
    for name in chosen.values():
        assert not names.name_words([name]) & words, name


def test_more_members_than_names_still_get_a_label():
    codes = [f"M-{i:08x}" for i in range(len(names.FICTIONAL_NAMES) + 3)]
    chosen = names.fictional_names(codes, [])
    assert len(set(chosen.values())) == len(codes)


def test_demo_frames_rename_members_and_drop_free_text():
    frames = {
        "statements": pd.DataFrame({
            "member_name": ["J. Kamau", "Jane Wairimu", None],
            "remarks": ["paid via Peter", None, "x"],
            "source_photo": ["chama_b_p012.jpg"] * 3,
        }),
        "meetings": pd.DataFrame({
            "host": ["Jane's home"], "notes": ["NB Peter"], "next_meeting": ["at Mary's 9th Feb"],
            "source_photo": ["chama_b_p012.jpg"],
        }),
    }
    renamed = {"j kamau": "Zawadi Mutua", "jane wairimu": "Neema Kiprono"}
    out = demo.demo_frames(frames, renamed, "chama_b", "chama_demo")
    assert list(out["statements"]["member_name"][:2]) == ["Zawadi Mutua", "Neema Kiprono"]
    assert out["statements"]["remarks"].isna().all()
    assert out["meetings"]["host"].isna().all() and out["meetings"]["notes"].isna().all()
    assert out["meetings"]["next_meeting"].iloc[0] == "9th Feb"
    assert out["statements"]["source_photo"].iloc[0] == "chama_demo_p012.jpg"


# ---- Humble Sister's interface copy (D-036): real names, two renamed, pages to a month ----

SPELLINGS = {"beth wamae": "Beth Wamae", "beth wangari": "Beth Wamae", "esther m": "Esther Mwangi",
             "esther mwangi": "Esther Mwangi", "anne kiende": "Anne Kiende", "annie kiende": "Anne Kiende"}
REAL = {"names": "real", "renames": {"Beth Wamae": "Alvin Muriithi", "Esther Mwangi": "Alvin Wise"}}


def test_the_copy_keeps_real_names_except_the_two_renamed():
    renamed, members = demo.copy_names(REAL, SPELLINGS, "chama_b", b"key")
    assert members == ["Alvin Muriithi", "Alvin Wise", "Anne Kiende"]
    assert renamed["beth wangari"] == "Alvin Muriithi" and renamed["esther m"] == "Alvin Wise"
    assert renamed["annie kiende"] == "Anne Kiende"
    assert renamed["alvin muriithi"] == "Alvin Muriithi"     # the new name is a spelling too, for typed pages


def test_a_rename_must_name_a_member_and_not_take_anothers_name():
    import pytest

    from chama import StepFailed

    with pytest.raises(StepFailed, match="not a member"):
        demo.copy_names({"names": "real", "renames": {"Nobody Here": "Alvin Wise"}}, SPELLINGS, "chama_b", b"k")
    with pytest.raises(StepFailed, match="already a member"):
        demo.copy_names({"names": "real", "renames": {"Beth Wamae": "Anne Kiende"}}, SPELLINGS, "chama_b", b"k")


def test_a_fictional_copy_still_hides_every_real_name():
    renamed, members = demo.copy_names({}, SPELLINGS, "chama_b", b"key")
    assert not names.name_words(members) & names.name_words(SPELLINGS.values())
    assert set(renamed.values()) == set(members)


def test_meeting_months_are_read_as_the_ledger_writes_them():
    assert demo.meeting_month("AUGUST 2024", 2024) == (2024, 8)
    assert demo.meeting_month("September 1st 2024", 2024) == (2024, 9)
    assert demo.meeting_month("FEB 2024", 2024) == (2024, 2)
    assert demo.meeting_month("3/8/25", 2025) == (2025, 8)
    assert demo.meeting_month("Dec", 2016) == (2016, 12)
    assert demo.meeting_month(None, 2025) is None and demo.meeting_month("no date", 2025) is None


def test_records_until_keeps_pages_in_or_before_the_month():
    meetings = pd.DataFrame({"meeting_date": ["JUNE 2024", "JULY 2024", "AUGUST 2024", "September 1st 2024"],
                             "source_photo": ["p126.jpg", "p127.jpg", "p128.jpg", "p129.jpg"]})
    assert demo.pages_until(meetings, 2024, (2024, 7)) == {"p126.jpg", "p127.jpg"}
    assert demo.pages_until(meetings, 2023, (2024, 7)) == set(meetings["source_photo"])   # an earlier year
    assert demo.pages_until(meetings, 2025, (2024, 7)) == set()                            # a later year
    assert demo.pages_until(meetings, 2024, None) == set(meetings["source_photo"])


def test_a_page_without_a_month_in_the_cut_off_year_is_named():
    import pytest

    from chama import StepFailed

    with pytest.raises(StepFailed, match="p130.jpg"):
        demo.pages_until(pd.DataFrame({"meeting_date": [None], "source_photo": ["p130.jpg"]}), 2024, (2024, 7))
