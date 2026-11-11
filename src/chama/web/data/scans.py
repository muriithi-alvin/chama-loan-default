"""Uploads, jobs, drafts, name matches, the edit record and pipeline runs."""
from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _rows(conn: Connection, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def _row(conn: Connection, sql: str, **params) -> dict | None:
    row = conn.execute(text(sql), params).first()
    return dict(row._mapping) if row else None


# ---- Uploads -------------------------------------------------------------------

UPLOAD_COLUMNS = """u.id, u.chama_id, u.uploaded_by, u.photo_path, u.checksum, u.idempotency_key, u.status,
    u.problem, u.provider, u.model, u.seconds, u.page_no, u.meeting_date, u.accepted_by, u.accepted_at,
    u.created_at, u.source,
    (SELECT count(*) FROM app.upload_photos p WHERE p.upload_id = u.id) AS parts"""


def upload(conn: Connection, upload_id: int, chama_id: str, lock: bool = False) -> dict | None:
    return _row(conn, f"SELECT {UPLOAD_COLUMNS} FROM app.uploads u WHERE u.id = :i AND u.chama_id = :c"
                + (" FOR UPDATE" if lock else ""), i=upload_id, c=chama_id)


def upload_row(conn: Connection, upload_id: int) -> dict:
    """An upload by its number alone: for the worker, never for a page."""
    return _row(conn, f"SELECT {UPLOAD_COLUMNS} FROM app.uploads u WHERE u.id = :i", i=upload_id)


def upload_by_key(conn: Connection, key: str) -> dict | None:
    return _row(conn, f"SELECT {UPLOAD_COLUMNS} FROM app.uploads u WHERE u.idempotency_key = :k", k=key)


def upload_by_checksum(conn: Connection, chama_id: str, checksum: str) -> dict | None:
    return _row(conn, f"SELECT {UPLOAD_COLUMNS} FROM app.uploads u WHERE u.chama_id = :c AND u.checksum = :s",
                c=chama_id, s=checksum)


def add_upload(conn: Connection, chama_id: str, user_id: int, photo_path: str | None, checksum: str | None,
               key: str, provider: str | None, source: str = "photo", status: str = "queued") -> int:
    return conn.execute(text(
        "INSERT INTO app.uploads (chama_id, uploaded_by, photo_path, checksum, idempotency_key, provider, source, "
        "status) VALUES (:c, :u, :p, :s, :k, :v, :o, :t) RETURNING id"),
        {"c": chama_id, "u": user_id, "p": photo_path, "s": checksum, "k": key, "v": provider, "o": source,
         "t": status}).scalar_one()


def add_photo_part(conn: Connection, upload_id: int, part: int, photo_path: str, checksum: str) -> None:
    conn.execute(text("INSERT INTO app.upload_photos (upload_id, part, photo_path, checksum) VALUES (:u, :n, :p, :s)"),
                 {"u": upload_id, "n": part, "p": photo_path, "s": checksum})


def photo_parts(conn: Connection, upload: dict) -> list[str]:
    """The upload's photos in order: its parts (D-039), or the one photo of an older upload."""
    paths = [r[0] for r in conn.execute(text(
        "SELECT photo_path FROM app.upload_photos WHERE upload_id = :u ORDER BY part"), {"u": upload["id"]})]
    return paths or ([upload["photo_path"]] if upload.get("photo_path") else [])


def source_of_scan(conn: Connection, chama_id: str, upload_id: int) -> str | None:
    """photo or typed, for an accepted page's scan file."""
    return conn.execute(text("SELECT source FROM app.uploads WHERE id = :i AND chama_id = :c"),
                        {"i": upload_id, "c": chama_id}).scalar()


def set_upload(conn: Connection, upload_id: int, **values) -> None:
    columns = ", ".join(f"{k} = :{k}" for k in values)
    conn.execute(text(f"UPDATE app.uploads SET {columns} WHERE id = :upload_id"),
                 {**values, "upload_id": upload_id})


def uploads(conn: Connection, chama_id: str) -> list[dict]:
    return _rows(conn, f"""
        SELECT {UPLOAD_COLUMNS}, coalesce(uu.display_name, uu.position, uu.role) AS uploaded_by_name,
               r.id AS run_id, r.status AS run_status,
               (SELECT count(*) FROM private.row_edits e WHERE e.upload_id = u.id) AS edits
        FROM app.uploads u
        JOIN app.users uu ON uu.id = u.uploaded_by
        LEFT JOIN app.pipeline_runs r ON r.upload_id = u.id
        WHERE u.chama_id = :c ORDER BY u.created_at DESC
    """, c=chama_id)


def next_page_no(conn: Connection, chama_id: str) -> int:
    """The page number after the last one recorded or accepted for this chama."""
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:c))"), {"c": "page:" + chama_id})
    return conn.execute(text("""
        SELECT greatest(
            (SELECT coalesce(max(page_no), 0) FROM analytics.meetings WHERE chama_id = :c),
            (SELECT coalesce(max(page_no), 0) FROM app.uploads WHERE chama_id = :c)) + 1
    """), {"c": chama_id}).scalar_one()


def last_meeting_month(conn: Connection, chama_id: str):
    return conn.execute(text(
        "SELECT max(coalesce(meeting_date, meeting_month)) FROM analytics.meetings WHERE chama_id = :c"),
        {"c": chama_id}).scalar()


def last_accepted_meeting(conn: Connection, chama_id: str, other_than: int | None = None):
    """The latest meeting date of an accepted page, whether or not its run has finished."""
    return conn.execute(text(
        "SELECT max(meeting_date) FROM app.uploads WHERE chama_id = :c AND status = 'accepted' "
        "AND id <> coalesce(CAST(:u AS bigint), 0)"), {"c": chama_id, "u": other_than}).scalar()


def runs_waiting(conn: Connection, chama_id: str) -> int:
    """Accepted pages whose records update has not finished yet."""
    return conn.execute(text("SELECT count(*) FROM app.pipeline_runs WHERE chama_id = :c "
                             "AND status IN ('queued', 'running')"), {"c": chama_id}).scalar_one()


# ---- Jobs ------------------------------------------------------------------------

JOB_COLUMNS = ("id, kind, upload_id, status, step, error_code, error_message, attempts, run_after, "
               "locked_at, created_at, finished_at")


def add_job(conn: Connection, kind: str, upload_id: int) -> int:
    """The upload's job of this kind, queued again if it exists (one per kind, X10)."""
    return conn.execute(text(
        "INSERT INTO app.jobs (kind, upload_id) VALUES (:k, :u) "
        "ON CONFLICT (upload_id, kind) DO UPDATE SET status = 'queued', run_after = now(), "
        "error_code = NULL, error_message = NULL, finished_at = NULL, attempts = 0 "
        "RETURNING id"), {"k": kind, "u": upload_id}).scalar_one()


def job(conn: Connection, job_id: int) -> dict | None:
    return _row(conn, f"SELECT {JOB_COLUMNS} FROM app.jobs WHERE id = :i", i=job_id)


def job_for(conn: Connection, upload_id: int, kind: str) -> dict | None:
    return _row(conn, f"SELECT {JOB_COLUMNS} FROM app.jobs WHERE upload_id = :u AND kind = :k",
                u=upload_id, k=kind)


def claim_job(conn: Connection) -> dict | None:
    """Take the oldest waiting job; another worker skips it (no Redis needed)."""
    return _row(conn, f"""
        UPDATE app.jobs SET status = 'running', locked_at = now(), attempts = attempts + 1
        WHERE id = (SELECT id FROM app.jobs WHERE status = 'queued' AND run_after <= now()
                    ORDER BY run_after, id FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING {JOB_COLUMNS}
    """)


def finish_job(conn: Connection, job_id: int, status: str, error_code: str | None = None,
               error_message: str | None = None) -> None:
    conn.execute(text("UPDATE app.jobs SET status = :s, error_code = :c, error_message = :m, "
                      "finished_at = now(), step = NULL WHERE id = :i"),
                 {"s": status, "c": error_code, "m": error_message, "i": job_id})


def retry_job_later(conn: Connection, job_id: int, seconds: int, message: str) -> None:
    conn.execute(text("UPDATE app.jobs SET status = 'queued', run_after = now() + make_interval(secs => :s), "
                      "error_message = :m WHERE id = :i"), {"s": seconds, "m": message, "i": job_id})


def set_job_step(conn: Connection, job_id: int, step: str) -> None:
    conn.execute(text("UPDATE app.jobs SET step = :s WHERE id = :i"), {"s": step, "i": job_id})


def release_stuck_jobs(conn: Connection, minutes: int = 30) -> int:
    """Jobs left 'running' by a worker that stopped: queue them again."""
    return conn.execute(text(
        "UPDATE app.jobs SET status = 'queued', run_after = now() WHERE status = 'running' "
        "AND locked_at < now() - make_interval(mins => :m)"), {"m": minutes}).rowcount


def scores_on_page(conn: Connection, chama_id: str, page_no: int) -> list[dict]:
    """The newest band and reasons of each member scored at this meeting."""
    return [dict(r._mapping) for r in conn.execute(text("""
        SELECT DISTINCT ON (member_code) member_code, band, reasons FROM app.risk_scores
        WHERE chama_id = :c AND page_no = :p ORDER BY member_code, scored_at DESC
    """), {"c": chama_id, "p": page_no})]


def members_on_page(conn: Connection, chama_id: str, page_no: int) -> list[str]:
    return [r[0] for r in conn.execute(text(
        "SELECT DISTINCT member_code FROM analytics.statements WHERE chama_id = :c AND page_no = :p "
        "AND member_code IS NOT NULL ORDER BY 1"), {"c": chama_id, "p": page_no})]


def heartbeat(conn: Connection, worker: str, model_run_id: str | None, loaded: bool) -> None:
    conn.execute(text("""
        INSERT INTO app.worker_status (worker, model_run_id, model_loaded_at, last_seen_at)
        VALUES (:w, :r, CASE WHEN :l THEN now() END, now())
        ON CONFLICT (worker) DO UPDATE SET last_seen_at = now(), model_run_id = EXCLUDED.model_run_id,
            model_loaded_at = coalesce(app.worker_status.model_loaded_at, EXCLUDED.model_loaded_at)
    """), {"w": worker, "r": model_run_id, "l": loaded})


# ---- Drafts --------------------------------------------------------------------------


def clear_draft(conn: Connection, upload_id: int) -> None:
    """Remove a draft that was never edited, before reading the photo again."""
    conn.execute(text("DELETE FROM private.draft_flags WHERE upload_id = :u"), {"u": upload_id})
    conn.execute(text("DELETE FROM private.name_matches WHERE upload_id = :u"), {"u": upload_id})
    conn.execute(text("DELETE FROM private.draft_rows WHERE upload_id = :u AND id NOT IN "
                      "(SELECT row_id FROM private.row_edits WHERE upload_id = :u AND row_id IS NOT NULL)"),
                 {"u": upload_id})


def add_draft_row(conn: Connection, upload_id: int, table: str, position: int, cells: dict,
                  added: bool = False) -> int:
    return conn.execute(text(
        "INSERT INTO private.draft_rows (upload_id, tbl, position, cells, added) "
        "VALUES (:u, :t, :p, CAST(:c AS jsonb), :a) RETURNING id"),
        {"u": upload_id, "t": table, "p": position, "c": json.dumps(cells), "a": added}).scalar_one()


def draft_rows(conn: Connection, upload_id: int, include_deleted: bool = False) -> list[dict]:
    return _rows(conn, """
        SELECT id, tbl, position, cells, added, deleted FROM private.draft_rows
        WHERE upload_id = :u AND (:d OR NOT deleted) ORDER BY tbl, position, id
    """, u=upload_id, d=include_deleted)


def draft_row(conn: Connection, upload_id: int, row_id: int) -> dict | None:
    return _row(conn, "SELECT id, tbl, position, cells, added, deleted FROM private.draft_rows "
                      "WHERE upload_id = :u AND id = :i FOR UPDATE", u=upload_id, i=row_id)


def set_draft_cells(conn: Connection, row_id: int, cells: dict) -> None:
    conn.execute(text("UPDATE private.draft_rows SET cells = CAST(:c AS jsonb), updated_at = now() "
                      "WHERE id = :i"), {"c": json.dumps(cells), "i": row_id})


def delete_draft_row(conn: Connection, row_id: int) -> None:
    conn.execute(text("UPDATE private.draft_rows SET deleted = true, updated_at = now() WHERE id = :i"),
                 {"i": row_id})


def max_position(conn: Connection, upload_id: int, table: str) -> int:
    return conn.execute(text("SELECT coalesce(max(position), -1) FROM private.draft_rows "
                             "WHERE upload_id = :u AND tbl = :t"), {"u": upload_id, "t": table}).scalar_one()


def replace_flags(conn: Connection, upload_id: int, flags: list[dict]) -> None:
    conn.execute(text("DELETE FROM private.draft_flags WHERE upload_id = :u"), {"u": upload_id})
    if flags:
        conn.execute(text(
            "INSERT INTO private.draft_flags (upload_id, row_id, col, rule, level, message) "
            "VALUES (:u, :row_id, :col, :rule, :level, :message)"),
            [{**f, "u": upload_id} for f in flags])


def flags(conn: Connection, upload_id: int) -> list[dict]:
    return _rows(conn, "SELECT row_id, col, rule, level, message FROM private.draft_flags "
                       "WHERE upload_id = :u ORDER BY id", u=upload_id)


# ---- Names ---------------------------------------------------------------------------


def name_matches(conn: Connection, upload_id: int) -> list[dict]:
    return _rows(conn, "SELECT raw_name, canonical_name, is_new FROM private.name_matches "
                       "WHERE upload_id = :u ORDER BY raw_name", u=upload_id)


def sync_names(conn: Connection, upload_id: int, spellings: dict[str, str | None]) -> None:
    """Keep one row per spelling on the page: add new ones (with a known
    member when the spelling is already reviewed), drop ones no longer there."""
    conn.execute(text("DELETE FROM private.name_matches WHERE upload_id = :u AND NOT (raw_name = ANY(:n))"),
                 {"u": upload_id, "n": list(spellings)})
    for raw, known in spellings.items():
        conn.execute(text(
            "INSERT INTO private.name_matches (upload_id, raw_name, canonical_name) VALUES (:u, :r, :c) "
            "ON CONFLICT (upload_id, raw_name) DO NOTHING"), {"u": upload_id, "r": raw, "c": known})


def set_name(conn: Connection, upload_id: int, raw: str, canonical: str | None, is_new: bool) -> bool:
    return conn.execute(text(
        "UPDATE private.name_matches SET canonical_name = :c, is_new = :n "
        "WHERE upload_id = :u AND raw_name = :r"),
        {"c": canonical, "n": is_new, "u": upload_id, "r": raw}).rowcount == 1


def canonical_names(conn: Connection, chama_id: str) -> dict[str, str]:
    """{member code: agreed name}, as the records know them (never demo mode's)."""
    return {r.member_code: r.canonical_name for r in conn.execute(text(
        "SELECT member_code, canonical_name FROM private.member_codes WHERE chama_id = :c"), {"c": chama_id})}


def chama_aliases(conn: Connection, chama_id: str) -> dict[str, str]:
    return {r.raw_name: r.canonical_name for r in conn.execute(text(
        "SELECT raw_name, canonical_name FROM private.member_aliases WHERE chama_id = :c"), {"c": chama_id})}


# ---- The edit record (insert only) ----------------------------------------------------


def record_edit(conn: Connection, upload_id: int, row_id: int | None, table: str, column: str | None,
                action: str, old: str | None, new: str | None, user_id: int) -> None:
    conn.execute(text(
        "INSERT INTO private.row_edits (upload_id, row_id, tbl, col, action, old_value, new_value, edited_by) "
        "VALUES (:u, :r, :t, :c, :a, :o, :n, :b)"),
        {"u": upload_id, "r": row_id, "t": table, "c": column, "a": action, "o": old, "n": new, "b": user_id})


def edits(conn: Connection, chama_id: str, upload_id: int | None = None) -> list[dict]:
    return _rows(conn, """
        SELECT e.id, e.upload_id, e.row_id, e.tbl, e.col, e.action, e.old_value, e.new_value, e.edited_at,
               coalesce(uu.display_name, uu.position, uu.role) AS edited_by_name, u.page_no
        FROM private.row_edits e
        JOIN app.uploads u ON u.id = e.upload_id
        JOIN app.users uu ON uu.id = e.edited_by
        WHERE u.chama_id = :c AND (CAST(:u AS bigint) IS NULL OR e.upload_id = :u)
        ORDER BY e.edited_at DESC, e.id DESC
        LIMIT 500
    """, c=chama_id, u=upload_id)


# ---- Pipeline runs ------------------------------------------------------------------------

STEPS = ["ingest", "names", "anonymise", "checks", "score"]


def add_run(conn: Connection, upload_id: int, chama_id: str) -> tuple[int, bool]:
    """(run id, created). A second Accept finds the first run (one per upload, X10)."""
    row = conn.execute(text(
        "INSERT INTO app.pipeline_runs (upload_id, chama_id) VALUES (:u, :c) "
        "ON CONFLICT (upload_id) DO NOTHING RETURNING id"), {"u": upload_id, "c": chama_id}).first()
    if row is None:
        existing = conn.execute(text("SELECT id FROM app.pipeline_runs WHERE upload_id = :u"),
                                {"u": upload_id}).scalar_one()
        return existing, False
    conn.execute(text("INSERT INTO app.pipeline_steps (run_id, step, position) VALUES (:r, :s, :p)"),
                 [{"r": row.id, "s": s, "p": i} for i, s in enumerate(STEPS)])
    return row.id, True


def run(conn: Connection, run_id: int, chama_id: str) -> dict | None:
    return _row(conn, "SELECT id, upload_id, chama_id, status, created_at, started_at, finished_at "
                      "FROM app.pipeline_runs WHERE id = :i AND chama_id = :c", i=run_id, c=chama_id)


def run_for(conn: Connection, upload_id: int) -> dict | None:
    return _row(conn, "SELECT id, upload_id, chama_id, status, created_at, started_at, finished_at "
                      "FROM app.pipeline_runs WHERE upload_id = :u", u=upload_id)


def run_steps(conn: Connection, run_id: int) -> list[dict]:
    return _rows(conn, "SELECT step, position, status, started_at, finished_at, error_message "
                       "FROM app.pipeline_steps WHERE run_id = :r ORDER BY position", r=run_id)


def set_run(conn: Connection, run_id: int, status: str) -> None:
    extra = {"running": ", started_at = coalesce(started_at, now()), finished_at = NULL",
             "queued": ", finished_at = NULL"}.get(status, ", finished_at = now()")
    conn.execute(text(f"UPDATE app.pipeline_runs SET status = :s{extra} WHERE id = :i"),
                 {"s": status, "i": run_id})


def set_step(conn: Connection, run_id: int, step: str, status: str, error: str | None = None) -> None:
    times = {"running": "started_at = now(), finished_at = NULL",
             "waiting": "started_at = NULL, finished_at = NULL"}.get(status, "finished_at = now()")
    conn.execute(text(f"UPDATE app.pipeline_steps SET status = :s, error_message = :e, {times} "
                      "WHERE run_id = :r AND step = :t"), {"s": status, "e": error, "r": run_id, "t": step})
