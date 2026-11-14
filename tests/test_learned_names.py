"""Names the model misread and the official corrected by retyping (D-046).

After Accept, such a misreading is kept as one of the member's spellings, so
the next page with the same misreading is matched by itself. A matched
spelling was already kept (pipeline_run.save_names); this covers the cell the
official typed over instead of matching.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from chama.web.services import scans as scan_service
from chama.web.services.pipeline_run import corrected_readings, retyped_names

MEMBERS = {"wanjiru kamau": "Wanjiru Kamau", "grace kanja": "Grace Kanja", "w kamau": "Wanjiru Kamau"}
KNOWN = set(MEMBERS)


def test_a_misreading_the_official_retyped_is_kept_for_that_member():
    learned = corrected_readings([("Wanjru Kamua", "Wanjiru Kamau"), ("Grase  Kanja.", "grace kanja")],
                                 MEMBERS, KNOWN)
    assert learned == {"wanjru kamua": "Wanjiru Kamau", "grase kanja": "Grace Kanja"}


def test_nothing_is_learned_from_a_line_the_model_gave_the_wrong_name():
    # another member's known name, a total in the name column, an unchanged name, an empty cell
    assert corrected_readings([("Wanjiru Kamau", "Grace Kanja"), ("W Kamau", "Grace Kanja"),
                               ("TOTAL 23,000", "Grace Kanja"), ("Grace Kanja", "Grace Kanja"),
                               (None, "Grace Kanja"), ("", "Grace Kanja")], MEMBERS, KNOWN) == {}


def test_nothing_is_learned_when_the_new_name_is_nobodys():
    assert corrected_readings([("Wanjru Kamua", "Someone Else")], MEMBERS, KNOWN) == {}


def test_a_reading_corrected_to_two_members_on_one_page_is_left_out():
    members = {**MEMBERS, "grace kamau": "Grace Kamau"}
    assert corrected_readings([("Grace Kamua", "Grace Kanja"), ("Grace Kamua", "Grace Kamau")], members,
                              set(members)) == {}
    # the same reading corrected to the same member twice is fine
    assert corrected_readings([("Wanjru Kamua", "Wanjiru Kamau")] * 2, MEMBERS, KNOWN) == \
        {"wanjru kamua": "Wanjiru Kamau"}


@pytest.fixture(scope="module")
def engine(fresh_db):
    with fresh_db.begin() as conn:
        conn.execute(text("INSERT INTO app.users (email, role, chama_id, display_name) VALUES "
                          "('t@example.com', 'official', 'chama_demo', 'Treasurer')"))
    return fresh_db


def _line(conn, upload: int, position: int, name: str, added: bool = False) -> int:
    from chama.web.data import scans

    return scans.add_draft_row(conn, upload, "statements", position, {"member_name": name}, added=added)


def test_the_first_reading_of_each_retyped_line_comes_from_the_edit_record(engine):
    from chama.web.data import scans

    with engine.begin() as conn:
        upload = conn.execute(text(
            "INSERT INTO app.uploads (chama_id, uploaded_by, photo_path, checksum, idempotency_key, status) "
            "VALUES ('chama_demo', 1, 'x.jpg', 'learn', 'learn-key', 'ready') RETURNING id")).scalar_one()
        retyped = _line(conn, upload, 0, "Wanjru Kamua")
        twice = _line(conn, upload, 1, "Grase Kanja")
        deleted = _line(conn, upload, 2, "Hellen Otieno")
        by_hand = _line(conn, upload, 3, "", added=True)
        untouched = _line(conn, upload, 4, "Anne Kiende")
        for row, old, new in [(retyped, "Wanjru Kamua", "Wanjiru Kamau"), (twice, "Grase Kanja", "Grace Kanj"),
                              (twice, "Grace Kanj", "Grace Kanja"), (deleted, "Hellen Otieno", "Helen Otieno"),
                              (by_hand, None, "Mary Wambui")]:
            cells = {"member_name": new}
            conn.execute(text("UPDATE private.draft_rows SET cells = CAST(:c AS jsonb) WHERE id = :i"),
                         {"c": json.dumps(cells), "i": row})
            scans.record_edit(conn, upload, row, "statements", "member_name", "edit", old, new, 1)
        scans.record_edit(conn, upload, untouched, "statements", "repayment", "edit", "500", "5000", 1)
        scans.delete_draft_row(conn, deleted)
    with engine.connect() as conn:
        found = sorted(retyped_names(conn, upload))
    # the model's own reading (the first edit's old value), with the name as it is now
    assert found == [("Grase Kanja", "Grace Kanja"), ("Wanjru Kamua", "Wanjiru Kamau")]


def test_a_learned_misreading_is_matched_by_itself_on_the_next_page(engine, monkeypatch):
    from chama.web.data import scans

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO private.member_aliases (chama_id, raw_name, canonical_name) VALUES "
                          "('chama_demo', 'wanjiru kamau', 'Wanjiru Kamau'), "
                          "('chama_demo', 'wanjru kamua', 'Wanjiru Kamau')"))     # learned from an earlier page
        upload = conn.execute(text(
            "INSERT INTO app.uploads (chama_id, uploaded_by, photo_path, checksum, idempotency_key, status) "
            "VALUES ('chama_demo', 1, 'y.jpg', 'next', 'next-key', 'ready') RETURNING id")).scalar_one()
        _line(conn, upload, 0, "Wanjru Kamua")
        monkeypatch.setattr(scan_service, "check_page", lambda frames: [])
        scan_service.refresh_checks(conn, upload, "chama_demo")
        matches = scans.name_matches(conn, upload)
    assert [(m["raw_name"], m["canonical_name"]) for m in matches] == [("wanjru kamua", "Wanjiru Kamau")]
