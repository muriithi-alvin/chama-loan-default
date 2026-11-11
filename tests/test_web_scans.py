"""Scan review rules that need no database: dates, drafts, flags, upload checks, a meeting in
several photos (D-039) and the typed page (D-038)."""
from datetime import date

import pandas as pd
import pytest

from chama.web.errors import ApiError
from chama.web.services import scans


@pytest.mark.parametrize("written, expected", [
    ("4/10/2026", date(2026, 10, 4)),
    ("4/10/26", date(2026, 10, 4)),
    ("4th October 2026", date(2026, 10, 4)),
    ("4 Oct 2026", date(2026, 10, 4)),
    ("8th/March/2015", date(2015, 3, 8)),
    ("September 1st 2024", date(2024, 9, 1)),
    ("31/2/2026", None),
    ("May 2016", None),
    ("", None),
    (None, None),
])
def test_meeting_dates_are_read_like_the_pipeline_reads_them(written, expected):
    assert scans.parse_meeting_date(written) == expected


def frames():
    return {
        "meetings": pd.DataFrame([{"meeting_date": "4/10/2026", "contribution_total": "12,000", "unclear": None}]),
        "statements": pd.DataFrame([
            {"member_name": "Zawadi Mutua", "loan_before": "40,000", "repayment": "5,000", "loan_after": "35,000"},
            {"member_name": "Neema", "loan_before": "4O,000", "repayment": "", "loan_after": "40,000", "unclear": "Y"},
        ]),
        "new_loans": pd.DataFrame(columns=["member_name", "amount"]),
    }


def test_cells_keep_every_raw_column_as_text():
    cells = scans.cells_from_frames(frames())
    assert set(cells) == {"meetings", "statements", "new_loans"}
    first = cells["statements"][0]
    assert first["member_name"] == "Zawadi Mutua" and first["remarks"] is None and "unclear" in first
    assert cells["new_loans"] == []


def test_flags_point_at_the_draft_row_and_use_plain_labels():
    cells = scans.cells_from_frames(frames())
    rows = [{"id": 100 + i, "tbl": t, "cells": c} for t in ("meetings", "statements", "new_loans")
            for i, c in enumerate(cells[t])]
    draft, index = scans.draft_frames(rows)
    assert index[("statements", 1)] == 101
    from chama.extraction.checks import check_page

    found = check_page(draft)
    unreadable = next(f for f in found if f.rule == "unreadable_amount")
    assert scans.friendly(unreadable, draft) == "Balance before: '4O,000' is not an amount"
    assert any(f.rule == "marked_unclear" and f.row == 1 for f in found)


def test_name_suggestions_come_from_the_chamas_members():
    members = ["Zawadi Mutua", "Neema Kiprono", "Halima Omar"]
    found = scans.suggestions("neema kiprno", members)
    assert found[0]["name"] == "Neema Kiprono"
    assert scans.suggestions("xyz", members) == []


def test_accept_waits_until_every_name_is_matched(monkeypatch):
    monkeypatch.setattr(scans.scans, "last_meeting_month", lambda conn, chama: date(2026, 4, 1))
    monkeypatch.setattr(scans.scans, "last_accepted_meeting", lambda conn, chama, upload=None: None)
    upload = {"chama_id": "chama_demo", "id": 9}
    rows = [{"tbl": "meetings", "cells": {"meeting_date": "3/5/2026"}},
            {"tbl": "statements", "cells": {"member_name": "Alvin Wyse"}}]
    new_name = [{"raw": "alvin wyse", "member": None, "is_new": False}]
    problems = scans.accept_problems(None, upload, rows, new_name)
    assert [p["field"] for p in problems] == ["names"]
    matched = [{"raw": "alvin wyse", "member": "Alvin Wise", "is_new": False}]
    assert scans.accept_problems(None, upload, rows, matched) == []


def test_pages_are_added_in_order_even_before_the_last_update_finishes(monkeypatch):
    monkeypatch.setattr(scans.scans, "last_meeting_month", lambda conn, chama: date(2024, 7, 1))
    monkeypatch.setattr(scans.scans, "last_accepted_meeting", lambda conn, chama, upload=None: date(2024, 8, 4))
    assert scans._date_problems(None, "chama_demo", date(2024, 9, 1), 10) == []
    late = scans._date_problems(None, "chama_demo", date(2024, 8, 25), 10)
    assert late and "August 2024 has already been accepted" in late[0]
    assert "already in the records" in scans._date_problems(None, "chama_demo", date(2024, 7, 28), 10)[0]


JPEG = b"\xff\xd8 not decoded here"


@pytest.mark.parametrize("photos, code", [
    ([(b"%PDF", "application/pdf")], "file_type"),
    ([(b"", "image/jpeg")], "file_empty"),
    ([(b"x" * (20 * 1024 * 1024 + 1), "image/jpeg")], "file_size"),
    ([(b"not really a photo", "image/jpeg")], "unusable_image"),
    ([], "file_empty"),
    ([(b"a", "image/jpeg"), (b"b", "image/jpeg"), (b"c", "image/jpeg"), (b"d", "image/jpeg")], "too_many"),
    ([(b"same", "image/jpeg"), (b"same", "image/jpeg")], "same_photo"),
], ids=["pdf", "empty", "over-20-MB", "not-an-image", "none", "four-photos", "same-photo-twice"])
def test_uploads_are_refused_next_to_the_photo_field(monkeypatch, photos, code):
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: None)
    monkeypatch.setattr(scans.scans, "upload_by_checksum", lambda conn, chama, checksum: None)
    with pytest.raises(ApiError) as e:
        scans.save_upload(None, "chama_demo", 1, photos, "key1", {"max_image_edge_px": 2576, "jpeg_quality": 85},
                          "groq")
    assert e.value.code == code
    assert e.value.field == "photo"


def test_a_problem_with_one_part_says_which_photo(monkeypatch):
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: None)
    with pytest.raises(ApiError) as e:
        scans.save_upload(None, "chama_demo", 1, [(b"a", "image/jpeg"), (b"%PDF", "application/pdf")], "key1", {},
                          "groq")
    assert e.value.message.startswith("Photo 2 of 2: Choose a JPEG")


def test_the_same_form_sent_twice_returns_the_first_upload(monkeypatch):
    first = {"id": 7, "chama_id": "chama_demo"}
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: first)
    upload, created = scans.save_upload(None, "chama_demo", 1, [(b"anything", "image/jpeg")], "key1", {}, "groq")
    assert upload is first and created is False


def test_the_same_photos_in_the_same_order_are_one_upload(monkeypatch):
    seen = []
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: None)
    monkeypatch.setattr(scans.scans, "upload_by_checksum", lambda conn, chama, checksum: seen.append(checksum) or {"id": 1})
    for photos in ([(b"a", "image/jpeg")], [(b"a", "image/jpeg"), (b"b", "image/jpeg")],
                   [(b"b", "image/jpeg"), (b"a", "image/jpeg")]):
        scans.save_upload(None, "chama_demo", 1, photos, "key1", {}, "groq")
    import hashlib

    assert seen[0] == hashlib.sha256(b"a").hexdigest()      # one photo: its own checksum, as before
    assert len(set(seen)) == 3


def part(date_written, lines, loans=(), notes=None, total=None):
    return {
        "meetings": pd.DataFrame([{"meeting_date": date_written, "contribution_total": total, "notes": notes,
                                   "unclear": None, "source_photo": "upload"}]),
        "statements": pd.DataFrame([{"member_name": n, "loan_before": b} for n, b in lines]),
        "new_loans": pd.DataFrame([{"member_name": n, "amount": a} for n, a in loans],
                                  columns=["member_name", "amount"]),
    }


def test_a_meeting_in_several_photos_is_read_as_one_page():
    merged = scans.merge_parts([
        part("4/8/2024", [("Anne Kiende", "235,000"), ("Alvin Wise", "40,000")]),
        part(None, [("Grace Kanja", "30,000")], loans=[("Anne Mata", "50,000")], total="3,150"),
        part("5/8/2024", [("Jane Kembo", None)]),
    ])
    assert list(merged["statements"]["member_name"]) == ["Anne Kiende", "Alvin Wise", "Grace Kanja", "Jane Kembo"]
    assert list(merged["new_loans"]["member_name"]) == ["Anne Mata"]
    meeting = merged["meetings"].iloc[0]
    assert len(merged["meetings"]) == 1
    assert meeting["meeting_date"] == "4/8/2024" and meeting["contribution_total"] == "3,150"
    assert "photo 3 gives meeting date as 5/8/2024" in meeting["notes"]


def test_one_photo_is_left_as_it_was_read():
    one = part("4/8/2024", [("Anne Kiende", "235,000")])
    assert scans.merge_parts([one]) is one


def test_a_line_seen_on_two_photos_gets_a_hint():
    page = scans.merge_parts([part("4/8/2024", [("Anne Kiende", "235,000")]),
                              part(None, [("Anne kiende", "235,000"), ("Anne Kiende", "15,000")])])
    rows = [{"id": 10 + i, "tbl": t, "cells": c} for t in ("meetings", "statements", "new_loans")
            for i, c in enumerate(scans.cells_from_frames(page)[t])]
    draft, index = scans.draft_frames(rows)
    hints = scans._repeated_lines(draft, index)
    assert [(h["row_id"], h["rule"], h["level"]) for h in hints] == [(11, "same_line_twice", "hint")]


LAST_PAGE = [   # analytics.statements of the last recorded meeting, as records.meeting_lines gives them
    {"member_code": "M-anne", "loan_type": None, "loan_after": 235000, "closing_balance": 235000},
    {"member_code": "M-jane", "loan_type": None, "loan_after": 0, "closing_balance": 0},       # cleared
    {"member_code": "M-anne", "loan_type": "school_fees", "loan_after": 15000, "closing_balance": 15000},
    {"member_code": "M-jane", "loan_type": "school_fees", "loan_after": 0, "closing_balance": 0},
    {"member_code": "M-serina", "loan_type": None, "loan_after": None, "closing_balance": None},  # no loan
    {"member_code": None, "loan_type": None, "loan_after": None, "closing_balance": None},
]
NAMES = {"M-anne": "Anne Kiende", "M-jane": "Jane Kembo", "M-serina": "Serina Murefu"}


def test_a_typed_page_starts_with_every_member_and_the_balance_they_carried():
    lines = scans.typed_lines(LAST_PAGE, NAMES)
    assert [(c["line_no"], c["member_name"], c["loan_before"], c["loan_type"]) for c in lines] == [
        ("1", "Anne Kiende", "235,000", None),
        ("2", "Jane Kembo", None, None),          # still on the page to pay her monthly, with no loan
        ("3", "Anne Kiende", "15,000", "SF"),     # her second loan, still running
        ("4", "Serina Murefu", None, None),
    ]
    assert all(c["monthly"] is None and c["repayment"] is None and c["loan_after"] is None for c in lines)
    assert set(lines[0]) >= {"member_name", "monthly", "loan_before", "repayment", "interest", "loan_after", "unclear"}


def test_a_typed_page_is_not_started_for_a_future_meeting_or_while_an_update_runs(monkeypatch):
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: None)
    monkeypatch.setattr(scans.scans, "runs_waiting", lambda conn, chama: 0)
    with pytest.raises(ApiError) as e:
        scans.start_typed(None, "chama_demo", 1, date(2999, 1, 1), "key1")
    assert e.value.code == "future" and e.value.field == "meeting_date"
    monkeypatch.setattr(scans.scans, "runs_waiting", lambda conn, chama: 1)
    with pytest.raises(ApiError) as e:
        scans.start_typed(None, "chama_demo", 1, date(2024, 8, 4), "key1")
    assert e.value.code == "waiting"


def test_a_typed_page_has_no_photo_to_show():
    assert scans.photo_refusal({"source": "typed", "chama_id": "chama_demo"}, []) == (
        "This page was typed in, so there is no photo of it.")
