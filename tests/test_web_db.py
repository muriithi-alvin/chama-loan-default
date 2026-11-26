"""Rules the database itself enforces (X10, OFF-13, T9), on a separate test database.

Uses `chama_test` on the same PostgreSQL server as .env (created if missing),
never the real `chama` database. Skipped when PostgreSQL is not running.
"""
from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from chama.db import SQL_DIR

TEST_DB = "chama_test"


def _url(database: str) -> str:
    user, password = os.getenv("POSTGRES_USER", "chama"), os.getenv("POSTGRES_PASSWORD", "")
    host, port = os.getenv("POSTGRES_HOST", "localhost"), os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture(scope="module")
def engine():
    try:
        admin = create_engine(_url(os.getenv("POSTGRES_DB", "chama")), isolation_level="AUTOCOMMIT",
                              connect_args={"connect_timeout": 3})
        with admin.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": TEST_DB}).first()
            if not exists:
                conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    except OperationalError:
        pytest.skip("PostgreSQL is not running (docker compose up -d)")
    eng = create_engine(_url(TEST_DB))
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS app, private, analytics CASCADE"))
        for path in sorted(SQL_DIR.glob("*.sql")):
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
        conn.execute(text("CREATE TABLE analytics.meetings (chama_id text, page_no int, meeting_month date, "
                          "meeting_date date, date_source text, source_photo text, source_file text)"))
        conn.execute(text("INSERT INTO analytics.meetings VALUES ('chama_demo', 149, '2026-04-01', '2026-04-12', "
                          "'written', 'chama_demo_p149.jpg', '2026.xlsx')"))
        conn.execute(text("INSERT INTO app.users (email, role, chama_id, display_name) VALUES "
                          "('grace@example.com', 'official', 'chama_demo', 'Grace Achieng')"))
    yield eng
    eng.dispose()


def new_upload(conn, checksum: str, key: str) -> int:
    return conn.execute(text(
        "INSERT INTO app.uploads (chama_id, uploaded_by, photo_path, checksum, idempotency_key) "
        "VALUES ('chama_demo', 1, 'x.jpg', :s, :k) RETURNING id"), {"s": checksum, "k": key}).scalar_one()


def test_the_edit_record_cannot_be_changed_or_deleted(engine):
    with engine.begin() as conn:
        upload = new_upload(conn, "edit-test", "edit-key")
        conn.execute(text("INSERT INTO private.row_edits (upload_id, tbl, col, action, old_value, new_value, "
                          "edited_by) VALUES (:u, 'statements', 'repayment', 'edit', '500', '5000', 1)"),
                     {"u": upload})
    for statement in ("UPDATE private.row_edits SET new_value = '1'", "DELETE FROM private.row_edits",
                      "TRUNCATE private.row_edits CASCADE"):
        with pytest.raises(DBAPIError, match="insert-only"), engine.begin() as conn:
            conn.execute(text(statement))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT new_value FROM private.row_edits")).scalar_one() == "5000"


def test_the_same_photo_or_form_cannot_make_a_second_upload(engine):
    with engine.begin() as conn:
        new_upload(conn, "photo-a", "key-a")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        new_upload(conn, "photo-a", "key-b")       # same photo
    with pytest.raises(IntegrityError), engine.begin() as conn:
        new_upload(conn, "photo-b", "key-a")       # same form


def test_one_pipeline_run_and_one_job_of_each_kind_per_upload(engine):
    from chama.web.data import scans

    with engine.begin() as conn:
        upload = new_upload(conn, "run-test", "run-key")
        first, created = scans.add_run(conn, upload, "chama_demo")
        again, created_again = scans.add_run(conn, upload, "chama_demo")
        job = scans.add_job(conn, "run_pipeline", upload)
        job_again = scans.add_job(conn, "run_pipeline", upload)
    assert created and not created_again and first == again
    assert job == job_again
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM app.pipeline_runs WHERE upload_id = :u"),
                            {"u": upload}).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM app.pipeline_steps ps JOIN app.pipeline_runs r "
                                 "ON r.id = ps.run_id WHERE r.upload_id = :u"), {"u": upload}).scalar_one() == 5


def test_double_accept_starts_one_run(engine, monkeypatch):
    """T9: two Accept presses give the same run and the same page number."""
    from chama.web.data import scans as data
    from chama.web.services import scans

    with engine.begin() as conn:
        upload = new_upload(conn, "accept-test", "accept-key")
        data.set_upload(conn, upload, status="ready")
        data.add_draft_row(conn, upload, "meetings", 0, {"meeting_date": "3/5/2026"})
        data.add_draft_row(conn, upload, "statements", 0, {"member_name": "Zawadi Mutua", "loan_before": "100"})
        conn.execute(text("INSERT INTO private.name_matches (upload_id, raw_name, canonical_name) "
                          "VALUES (:u, 'zawadi mutua', 'Zawadi Mutua')"), {"u": upload})
    with engine.begin() as conn:
        first = scans.accept(conn, upload, "chama_demo", 1)
    with engine.begin() as conn:
        second = scans.accept(conn, upload, "chama_demo", 1)
    assert first["created"] and not second["created"]
    assert first["run_id"] == second["run_id"] and first["page_no"] == second["page_no"] == 150


def test_accept_refuses_a_meeting_already_in_the_records(engine):
    from chama.web.data import scans as data
    from chama.web.errors import ApiError
    from chama.web.services import scans

    with engine.begin() as conn:
        upload = new_upload(conn, "old-page", "old-key")
        data.set_upload(conn, upload, status="ready")
        data.add_draft_row(conn, upload, "meetings", 0, {"meeting_date": "12/4/2026"})
        data.add_draft_row(conn, upload, "statements", 0, {"member_name": "Zawadi Mutua"})
    with pytest.raises(ApiError) as e, engine.begin() as conn:
        scans.accept(conn, upload, "chama_demo", 1)
    assert e.value.field == "meeting_date" and "already in the records" in e.value.message


def test_jobs_are_taken_once(engine):
    from chama.web.data import scans

    with engine.begin() as conn:
        upload = new_upload(conn, "job-test", "job-key")
        scans.add_job(conn, "read_photo", upload)
        conn.execute(text("UPDATE app.jobs SET status = 'done' WHERE upload_id <> :u"), {"u": upload})
    with engine.begin() as conn:
        taken = scans.claim_job(conn)
    with engine.begin() as conn:
        assert scans.claim_job(conn) is None
    assert taken["upload_id"] == upload and taken["attempts"] == 1
    assert json.dumps(taken, default=str)


def test_a_deactivated_account_can_be_given_another_member(engine):
    from chama import StepFailed
    from chama.web.services import accounts

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO private.member_codes VALUES ('chama_demo', 'a', 'M-a'), "
                          "('chama_demo', 'b', 'M-b')"))
    accounts.add_user(engine, "amani@example.com", "member", "chama_demo", "M-a", None, None)
    with pytest.raises(StepFailed, match="Deactivate it first"):
        accounts.add_user(engine, "amani@example.com", "member", "chama_demo", "M-b", None, None)
    accounts.deactivate_user(engine, "amani@example.com")
    assert accounts.add_user(engine, "amani@example.com", "member", "chama_demo", "M-b", None, None).startswith(
        "Reopened")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT member_code, active FROM app.users WHERE email = 'amani@example.com'")).all()
    assert rows == [("M-b", True)]


def test_the_release_adds_its_treasurer_and_member_with_their_phones(engine, monkeypatch):
    from chama.config import load_config
    from chama.deploy import MEMBER_NAME, OFFICIAL_NAME, add_accounts

    monkeypatch.setenv("RELEASE_OFFICIAL_EMAIL", "release.official@example.com")
    monkeypatch.setenv("RELEASE_MEMBER_EMAIL", "release.member@example.com")
    monkeypatch.setenv("RELEASE_OFFICIAL_PHONE", "0711 000 001")
    monkeypatch.delenv("RELEASE_MEMBER_PHONE", raising=False)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO private.member_codes VALUES ('chama_demo', :n, 'M-release')"), {"n": MEMBER_NAME})
    add_accounts(load_config(), engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT role, chama_id, member_code, display_name, position, phone FROM app.users "
                                 "WHERE email LIKE 'release.%' ORDER BY role")).all()
    assert rows == [("member", "chama_demo", "M-release", None, None, None),
                    ("official", "chama_demo", None, OFFICIAL_NAME, "treasurer", "+254711000001")]


def test_the_footer_status_gives_members_no_score_details(engine):
    from chama.web.data.users import User
    from chama.web.routes.session import records_status

    official = User(1, "grace@example.com", "official", "chama_demo", None, "Grace Achieng", "treasurer", True)
    member = User(2, "neema@example.com", "member", "chama_demo", "M-1", None, None, True)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app.risk_scores (chama_id, member_code, page_no, meeting_month, band, "
                          "reasons, model_run_id, model_name) VALUES ('chama_demo', 'M-1', 149, '2026-04-01', "
                          "'high', '[]', 'fc6ae3fed3a1', 'random_forest')"))
        for_official = records_status(conn, official)
        for_member = records_status(conn, member)
    assert for_official["records_to"]["page_no"] == 149
    assert for_official["model_label"] == "random forest fc6ae3fe"
    assert set(for_member) == {"records_to"}


# ---- D-037: phones and sign-ins waiting for a code ---------------------------------------


def test_an_account_needs_an_email_or_a_phone_and_a_phone_is_one_account(engine):
    from chama import StepFailed
    from chama.web.services import accounts

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO private.member_codes VALUES ('chama_demo', 'p', 'M-p'), "
                          "('chama_demo', 'q', 'M-q') ON CONFLICT DO NOTHING"))
    assert "phone +254722000001" in accounts.add_user(engine, "p@example.com", "member", "chama_demo", "M-p", None,
                                                       None, phone="0722000001")
    assert accounts.add_user(engine, None, "member", "chama_demo", "M-q", None, None, phone="0722000002").startswith(
        "Added member +254722000002")
    with pytest.raises(StepFailed, match="already the phone of another account"):
        accounts.add_user(engine, "other@example.com", "member", "chama_demo", "M-q", None, None, phone="0722000001")
    with pytest.raises(StepFailed, match="--email, --phone or both"):
        accounts.add_user(engine, None, "member", "chama_demo", "M-q", None, None)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO app.users (role, chama_id) VALUES ('official', 'chama_demo')"))
    assert "deactivated" in accounts.deactivate_user(engine, "0722000002").lower()


def test_a_waiting_sign_in_is_used_once(engine):
    from datetime import datetime, timedelta, timezone

    from chama.web.data import users

    with engine.begin() as conn:
        user = conn.execute(text("SELECT id FROM app.users ORDER BY id LIMIT 1")).scalar_one()
        later = datetime.now(timezone.utc) + timedelta(minutes=10)
        users.start_step(conn, "h-old", user, "password", "sb-1", later)
        users.start_step(conn, "h-new", user, "password", "sb-1", later)      # a new sign-in replaces the old
        assert users.step(conn, "h-old") is None
        assert users.count_attempt(conn, "h-new") == 1
        users.end_step(conn, "h-new")
        assert users.step(conn, "h-new") is None
        users.start_step(conn, "h-gone", user, "phone", None, datetime.now(timezone.utc) - timedelta(seconds=1))
        assert users.step(conn, "h-gone") is None                               # expired


# ---- D-038, D-039: a typed page has no photo; a scan's photos are its parts ------------


def test_a_typed_page_needs_no_photo_but_a_scan_does(engine):
    from chama.web.data import scans as data

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app.uploads (chama_id, uploaded_by, idempotency_key, source, status) "
                          "VALUES ('chama_demo', 1, 'typed-1', 'typed', 'ready')"))
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO app.uploads (chama_id, uploaded_by, idempotency_key) "
                          "VALUES ('chama_demo', 1, 'no-photo')"))
    with engine.begin() as conn:
        upload = new_upload(conn, "parts-test", "parts-key")
        for part in (2, 1):
            conn.execute(text("INSERT INTO app.upload_photos VALUES (:u, :p, :path, :s)"),
                         {"u": upload, "p": part, "path": f"part{part}.jpg", "s": f"sum{part}"})
        found = data.upload(conn, upload, "chama_demo")
        assert found["parts"] == 2 and data.photo_parts(conn, found) == ["part1.jpg", "part2.jpg"]
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO app.upload_photos VALUES (:u, 4, 'x.jpg', 'x')"), {"u": upload})


def test_a_typed_page_opens_with_the_last_meetings_members_and_balances(engine):
    from datetime import date

    from chama.web.services import scans as service

    with engine.begin() as conn:
        # earlier tests leave runs queued and pages accepted; this one starts after them
        conn.execute(text("UPDATE app.pipeline_runs SET status = 'done'"))
        conn.execute(text("UPDATE app.uploads SET meeting_date = NULL"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS analytics.statements (chama_id text, page_no int, "
                          "line_on_page int, line_no int, member_code text, line_kind text, loan_type text, "
                          "monthly_amount numeric, monthly_note text, loan_before numeric, repayment numeric, "
                          "interest_rate_pct numeric, interest_amount numeric, loan_after numeric, "
                          "closing_balance numeric, due_month date, unclear boolean, issues text)"))
        conn.execute(text("INSERT INTO private.member_codes VALUES ('chama_demo', 'Gladys Onchiri', 'M-gladys'), "
                          "('chama_demo', 'Anne Kiende', 'M-anne') ON CONFLICT DO NOTHING"))
        conn.execute(text("INSERT INTO private.member_aliases (chama_id, raw_name, canonical_name) VALUES "
                          "('chama_demo', 'gladys onchiri', 'Gladys Onchiri'), "
                          "('chama_demo', 'anne kiende', 'Anne Kiende') ON CONFLICT DO NOTHING"))
        conn.execute(text("INSERT INTO analytics.statements (chama_id, page_no, line_on_page, member_code, loan_type, "
                          "loan_after, closing_balance) VALUES ('chama_demo', 149, 1, 'M-gladys', NULL, 40000, 40000), "
                          "('chama_demo', 149, 2, 'M-anne', NULL, 0, 0)"))
        upload, created = service.start_typed(conn, "chama_demo", 1, date(2026, 5, 3), "typed-start-1")
        again, created_again = service.start_typed(conn, "chama_demo", 1, date(2026, 5, 3), "typed-start-1")
        assert created and not created_again and again["id"] == upload["id"]
        draft = service.draft_view(conn, upload["id"], "chama_demo")
        with pytest.raises(service.ApiError, match="already in the records"):
            service.start_typed(conn, "chama_demo", 1, date(2026, 4, 20), "typed-start-2")
    assert draft["source"] == "typed" and draft["status"] == "ready"
    assert draft["photo"] == {"available": False, "reason": "This page was typed in, so there is no photo of it.",
                              "parts": 0}
    lines = [r["cells"] for r in draft["rows"] if r["table"] == "statements"]
    assert [(c["member_name"], c["loan_before"]) for c in lines] == [("Gladys Onchiri", "40,000"), ("Anne Kiende", None)]
    meeting = next(r["cells"] for r in draft["rows"] if r["table"] == "meetings")
    assert meeting["meeting_date"] == "3/5/2026"
    assert all(n["member"] for n in draft["names"])          # the agreed names match at once


def test_a_restarted_worker_is_not_ready_until_its_model_loads(engine, monkeypatch):
    from chama.web.data import scans as data
    from chama.web.routes import health

    monkeypatch.setattr(health, "engine", lambda: engine)
    with engine.begin() as conn:
        data.heartbeat(conn, "worker@test", "fc6ae3fed3a1", True)        # the last run, loaded
        data.heartbeat(conn, "worker@test", None, False)                 # restarted, still loading
    ready, parts = health.health_report()
    assert not ready and parts["model"] == "not loaded" and parts["worker"] == "ready"
    with engine.begin() as conn:
        data.heartbeat(conn, "worker@test", "fc6ae3fed3a1", True)
    ready, parts = health.health_report()
    assert ready and parts["model"] == "ready (run fc6ae3fe)"
