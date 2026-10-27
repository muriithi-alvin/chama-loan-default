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
