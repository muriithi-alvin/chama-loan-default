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
