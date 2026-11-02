"""Scan review rules that need no database: dates, drafts, flags, upload checks."""
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
    upload = {"chama_id": "chama_demo"}
    rows = [{"tbl": "meetings", "cells": {"meeting_date": "3/5/2026"}},
            {"tbl": "statements", "cells": {"member_name": "Kawira Mutembel"}}]
    new_name = [{"raw": "kawira mutembel", "member": None, "is_new": False}]
    problems = scans.accept_problems(None, upload, rows, new_name)
    assert [p["field"] for p in problems] == ["names"]
    matched = [{"raw": "kawira mutembel", "member": "Kawira Mutembei", "is_new": False}]
    assert scans.accept_problems(None, upload, rows, matched) == []


@pytest.mark.parametrize("content_type, data, code", [
    ("application/pdf", b"%PDF", "file_type"),
    ("image/jpeg", b"", "file_empty"),
    ("image/jpeg", b"x" * (20 * 1024 * 1024 + 1), "file_size"),
    ("image/jpeg", b"not really a photo", "unusable_image"),
], ids=["pdf", "empty", "over-20-MB", "not-an-image"])
def test_uploads_are_refused_next_to_the_photo_field(monkeypatch, content_type, data, code):
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: None)
    monkeypatch.setattr(scans.scans, "upload_by_checksum", lambda conn, chama, checksum: None)
    with pytest.raises(ApiError) as e:
        scans.save_upload(None, "chama_demo", 1, data, content_type, "key1", {"max_image_edge_px": 2576,
                          "jpeg_quality": 85}, "groq")
    assert e.value.code == code
    assert e.value.field == "photo"


def test_the_same_form_sent_twice_returns_the_first_upload(monkeypatch):
    first = {"id": 7, "chama_id": "chama_demo"}
    monkeypatch.setattr(scans.scans, "upload_by_key", lambda conn, key: first)
    upload, created = scans.save_upload(None, "chama_demo", 1, b"anything", "image/jpeg", "key1", {}, "groq")
    assert upload is first and created is False
