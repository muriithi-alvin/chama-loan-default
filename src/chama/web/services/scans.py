"""Scan a page, review it, accept it (OFF-8 to OFF-10, S-2, S-3).

1. Upload: the photo is checked, re-saved upright without location data
   (EXIF) and kept in PHOTO_DIR; a `read_photo` job is queued. The same photo
   twice, or the same form sent twice, returns the first upload (X10).
2. Read (the worker): the vision model reads the page into the raw layout
   (chama.extraction); the rows become a draft, chama.extraction.checks flags
   the lines to look at, and each spelling of a name gets a match or
   suggestions from the chama's reviewed names (aliases.name_similarity).
3. Review: the official corrects cells, adds or deletes rows and matches
   every name. Each change is saved at once and written to the edit record.
4. Accept: once every name is matched and the meeting date is after the last
   recorded meeting, the page gets the next ledger page number and one
   pipeline run is queued (pipeline_run.py).
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Connection

from chama.anonymisation.aliases import SIMILAR_THRESHOLD, name_similarity
from chama.anonymisation.pseudonymise import normalise_name
from chama.extraction.checks import check_page
from chama.extraction.images import MAX_FILE_BYTES, UnusableImage, prepare_image
from chama.extraction.schema import PAGE_TABLES
from chama.ingestion.raw_format import SHEETS
from chama.web.data import scans
from chama.web.errors import ApiError, not_found
from chama.web.settings import is_demo_chama, web_settings

ACCEPTED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# The columns the review screen shows, in order, with plain labels.
COLUMNS: dict[str, list[tuple[str, str]]] = {
    "statements": [("line_no", "No."), ("member_name", "Name"), ("monthly", "Monthly"),
                   ("loan_before", "Balance before"), ("repayment", "Repaid"), ("interest", "Interest"),
                   ("loan_after", "Balance after"), ("due", "Due"), ("loan_type", "Type mark"),
                   ("remarks", "Remarks")],
    "meetings": [("meeting_date", "Meeting date"), ("contribution_total", "Contributions total"),
                 ("brought_forward", "Brought forward"), ("total_collection", "Total collection"),
                 ("cash", "Cash"), ("banked", "Banked"), ("next_meeting", "Next meeting"),
                 ("host", "Host"), ("notes", "Notes"), ("column_headers", "Column headings")],
    "new_loans": [("loan_date", "Date"), ("member_name", "Name"), ("amount", "Amount"),
                  ("loan_type", "Type"), ("remarks", "Remarks")],
}
LABELS = {t: dict(cols) for t, cols in COLUMNS.items()}
NAME_TABLES = ("statements", "new_loans")


# ---- Upload --------------------------------------------------------------------


def save_upload(conn: Connection, chama_id: str, user_id: int, data: bytes, content_type: str | None,
                key: str, settings: dict, provider: str) -> tuple[dict, bool]:
    """(upload, created). Checks the file, strips its location data, queues reading."""
    if not key or len(key) > 100 or not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ApiError(422, "no_key", "The form is missing its safety key. Reload the page and try again.")
    existing = scans.upload_by_key(conn, key)
    if existing:
        if existing["chama_id"] != chama_id:
            raise ApiError(409, "key_used", "This form was already used. Reload the page and try again.")
        return existing, False
    if content_type not in ACCEPTED_TYPES:
        raise ApiError(422, "file_type", "Choose a JPEG, PNG or WebP photo.", field="photo")
    if len(data) > MAX_FILE_BYTES:
        raise ApiError(422, "file_size", "The photo is larger than 20 MB. Take it again or choose a smaller one.",
                       field="photo")
    if not data:
        raise ApiError(422, "file_empty", "The file is empty. Choose the photo again.", field="photo")
    checksum = hashlib.sha256(data).hexdigest()
    same = scans.upload_by_checksum(conn, chama_id, checksum)
    if same:
        return same, False
    try:
        jpeg = prepare_image(data, settings["max_image_edge_px"], settings["jpeg_quality"])
    except UnusableImage as e:
        raise ApiError(422, "unusable_image", str(e), field="photo") from e

    folder = web_settings().photo_dir / chama_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}.jpg"
    path.write_bytes(jpeg)
    upload_id = scans.add_upload(conn, chama_id, user_id, str(path), checksum, key, provider)
    scans.add_job(conn, "read_photo", upload_id)
    return scans.upload(conn, upload_id, chama_id), True


def photo_refusal(upload: dict) -> str | None:
    """In demo mode only a demo chama's scans (written with fictional names) are shown (G5)."""
    if web_settings().demo_mode and not is_demo_chama(upload["chama_id"]):
        return "The photo of this page is not shown here, to keep members' names private."
    return None if photo_path(upload) else "The photo is no longer on the server."


def photo_path(upload: dict) -> Path | None:
    path = Path(upload["photo_path"]).resolve()
    root = web_settings().photo_dir.resolve()
    return path if root in path.parents and path.is_file() else None


# ---- Draft from the model's reading ----------------------------------------------


def cells_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[dict]]:
    out = {}
    for table in PAGE_TABLES:
        columns = list(SHEETS[table][1]) + ["unclear"]
        df = frames.get(table, pd.DataFrame(columns=columns))
        out[table] = [{c: (None if pd.isna(row.get(c)) else str(row.get(c))) for c in columns}
                      for row in df.to_dict("records")]
    return out


def write_draft(conn: Connection, upload_id: int, frames: dict[str, pd.DataFrame], chama_id: str) -> None:
    scans.clear_draft(conn, upload_id)
    for table, rows in cells_from_frames(frames).items():
        for position, cells in enumerate(rows):
            scans.add_draft_row(conn, upload_id, table, position, cells)
    refresh_checks(conn, upload_id, chama_id)


def draft_frames(rows: list[dict]) -> tuple[dict[str, pd.DataFrame], dict[tuple[str, int], int]]:
    """The current draft as raw-layout tables, and (table, position in table) -> row id."""
    frames, index = {}, {}
    for table in PAGE_TABLES:
        mine = [r for r in rows if r["tbl"] == table]
        columns = list(SHEETS[table][1]) + ["unclear"]
        frames[table] = pd.DataFrame([r["cells"] for r in mine], columns=columns)
        for i, r in enumerate(mine):
            index[(table, i)] = r["id"]
    return frames, index


def friendly(flag, frames) -> str:
    if flag.rule == "unreadable_amount" and flag.column:
        value = frames[flag.table].iloc[flag.row][flag.column]
        return f"{LABELS[flag.table].get(flag.column, flag.column)}: '{value}' is not an amount"
    return flag.message


def refresh_checks(conn: Connection, upload_id: int, chama_id: str) -> None:
    """Run the checks on the draft as it is now, and keep the name list in step."""
    rows = scans.draft_rows(conn, upload_id)
    frames, index = draft_frames(rows)
    flags = [{"row_id": index[(f.table, f.row)], "col": f.column, "rule": f.rule, "level": f.severity,
              "message": friendly(f, frames)} for f in check_page(frames)]
    scans.replace_flags(conn, upload_id, flags)

    reviewed = scans.chama_aliases(conn, chama_id)
    spellings = {}
    for r in rows:
        if r["tbl"] in NAME_TABLES:
            raw = normalise_name(r["cells"].get("member_name") or "")
            if raw:
                spellings[raw] = reviewed.get(raw)
    scans.sync_names(conn, upload_id, spellings)


def suggestions(raw: str, members: list[str], n: int = 3) -> list[dict]:
    scored = sorted(((name_similarity(raw, m), m) for m in members), reverse=True)
    return [{"name": m, "score": round(s, 2)} for s, m in scored[:n] if s >= SIMILAR_THRESHOLD]


# ---- The review screen ---------------------------------------------------------------


def require(conn: Connection, upload_id: int, chama_id: str, lock: bool = False) -> dict:
    upload = scans.upload(conn, upload_id, chama_id, lock=lock)
    if upload is None:
        raise not_found("That scan")
    return upload


def require_editable(conn: Connection, upload_id: int, chama_id: str) -> dict:
    upload = require(conn, upload_id, chama_id, lock=True)
    if upload["status"] != "ready":
        raise ApiError(409, "not_editable", {
            "accepted": "This page has been accepted; changes now go through a new scan.",
            "discarded": "This scan was discarded.",
        }.get(upload["status"], "The page is still being read. Wait until it is ready for review."))
    return upload


def draft_view(conn: Connection, upload_id: int, chama_id: str) -> dict:
    upload = require(conn, upload_id, chama_id)
    rows = scans.draft_rows(conn, upload_id)
    flags = scans.flags(conn, upload_id)
    reviewed = scans.chama_aliases(conn, chama_id)
    members = sorted(set(reviewed.values()))
    names = [{
        "raw": m["raw_name"],
        "member": m["canonical_name"],
        "is_new": m["is_new"],
        "known_spelling": m["raw_name"] in reviewed,
        "suggestions": [] if m["raw_name"] in reviewed else suggestions(m["raw_name"], members),
    } for m in scans.name_matches(conn, upload_id)]
    return {
        "upload_id": upload_id,
        "status": upload["status"],
        "photo": {"available": photo_refusal(upload) is None, "reason": photo_refusal(upload)},
        "columns": {t: [{"key": k, "label": label} for k, label in cols] for t, cols in COLUMNS.items()},
        "rows": [{"id": r["id"], "table": r["tbl"], "cells": r["cells"], "added": r["added"],
                  "flags": [f for f in flags if f["row_id"] == r["id"]]} for r in rows],
        "names": names,
        "members": members,
        "ready_to_accept": accept_problems(conn, upload, rows, names) == [],
        "problems": accept_problems(conn, upload, rows, names),
    }


def edit_cell(conn: Connection, upload_id: int, chama_id: str, row_id: int, column: str, value: str | None,
              user_id: int) -> None:
    require_editable(conn, upload_id, chama_id)
    row = scans.draft_row(conn, upload_id, row_id)
    if row is None or row["deleted"]:
        raise not_found("That row")
    allowed = set(LABELS[row["tbl"]]) | {"unclear"}
    if column not in allowed:
        raise ApiError(422, "column", "That column cannot be changed here.")
    value = (value or "").strip() or None
    if column == "unclear":
        value = "Y" if value in ("Y", "y", "true", "1") else None
    old = row["cells"].get(column)
    if old == value:
        return
    cells = {**row["cells"], column: value}
    scans.set_draft_cells(conn, row_id, cells)
    scans.record_edit(conn, upload_id, row_id, row["tbl"], column, "edit", old, value, user_id)
    refresh_checks(conn, upload_id, chama_id)


def add_row(conn: Connection, upload_id: int, chama_id: str, table: str, user_id: int) -> int:
    require_editable(conn, upload_id, chama_id)
    if table not in ("statements", "new_loans"):
        raise ApiError(422, "table", "Rows can be added to the member lines or the new loans.")
    columns = list(SHEETS[table][1]) + ["unclear"]
    position = scans.max_position(conn, upload_id, table) + 1
    row_id = scans.add_draft_row(conn, upload_id, table, position, dict.fromkeys(columns), added=True)
    scans.record_edit(conn, upload_id, row_id, table, None, "add_row", None, None, user_id)
    refresh_checks(conn, upload_id, chama_id)
    return row_id


def delete_row(conn: Connection, upload_id: int, chama_id: str, row_id: int, user_id: int) -> None:
    require_editable(conn, upload_id, chama_id)
    row = scans.draft_row(conn, upload_id, row_id)
    if row is None or row["deleted"]:
        raise not_found("That row")
    if row["tbl"] == "meetings":
        raise ApiError(422, "meeting_row", "The page's date and totals cannot be deleted; correct them instead.")
    scans.delete_draft_row(conn, row_id)
    summary = row["cells"].get("member_name") or ""
    scans.record_edit(conn, upload_id, row_id, row["tbl"], None, "delete_row", summary, None, user_id)
    refresh_checks(conn, upload_id, chama_id)


def match_name(conn: Connection, upload_id: int, chama_id: str, raw: str, member: str | None, is_new: bool,
               user_id: int) -> None:
    require_editable(conn, upload_id, chama_id)
    members = set(scans.chama_aliases(conn, chama_id).values())
    if is_new:
        member = None
    elif member not in members:
        raise ApiError(422, "member", "Choose one of the chama's members, or mark the name as a new member.",
                       field="member")
    old = next((m for m in scans.name_matches(conn, upload_id) if m["raw_name"] == raw), None)
    if old is None:
        raise not_found("That name")
    if not scans.set_name(conn, upload_id, raw, member, is_new):
        raise not_found("That name")
    before = "new member" if old["is_new"] else old["canonical_name"]
    scans.record_edit(conn, upload_id, None, "names", raw, "match_name", before,
                      "new member" if is_new else member, user_id)


# ---- Accept -----------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9


def parse_meeting_date(text: str | None) -> date | None:
    """A meeting date written as 4/10/2026, 4/10/26, 4th October 2026 or October 4 2026."""
    if not text:
        return None
    value = text.strip().lower().replace(",", " ")

    def make(y: int, m: int, d: int) -> date | None:
        y = y + 2000 if y < 100 else y
        try:
            return date(y, m, d)
        except ValueError:
            return None

    if found := re.fullmatch(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{2}|\d{4})", value):
        d, m, y = (int(g) for g in found.groups())
        return make(y, m, d)
    if found := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s/.-]+(?:of\s+)?([a-z]+)\.?[\s/.-]+(\d{4})", value):
        d, word, y = found.groups()
        return make(int(y), _MONTHS[word], int(d)) if word in _MONTHS else None
    if found := re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})", value):
        word, d, y = found.groups()
        return make(int(y), _MONTHS[word], int(d)) if word in _MONTHS else None
    return None


def accept_problems(conn: Connection, upload: dict, rows: list[dict], names: list[dict]) -> list[dict]:
    """What stops Accept, each with the field it is about."""
    problems = []
    unmatched = [n["raw"] for n in names if not n["member"] and not n["is_new"]]
    if unmatched:
        problems.append({"field": "names", "message": f"Match every name to a member first ({len(unmatched)} "
                         f"{'is' if len(unmatched) == 1 else 'are'} not matched yet)."})
    if not any(r["tbl"] == "statements" for r in rows):
        problems.append({"field": "statements", "message": "The page has no member lines."})
    meeting = next((r for r in rows if r["tbl"] == "meetings"), None)
    when = parse_meeting_date(meeting["cells"].get("meeting_date") if meeting else None)
    if when is None:
        problems.append({"field": "meeting_date",
                         "message": "Enter the meeting date as day/month/year, for example 4/10/2026."})
    else:
        last = scans.last_meeting_month(conn, upload["chama_id"])
        if last and (when.year, when.month) <= (last.year, last.month):
            problems.append({"field": "meeting_date", "message":
                             f"A meeting in {last:%B %Y} or later is already in the records. For now only "
                             "pages after the last recorded meeting can be added (open decision 2)."})
    return problems


def accept(conn: Connection, upload_id: int, chama_id: str, user_id: int) -> dict:
    """Accept the page once; a second Accept returns the same run (X10, T9)."""
    upload = require(conn, upload_id, chama_id, lock=True)
    if upload["status"] == "accepted":
        run = scans.run_for(conn, upload_id)
        return {"run_id": run["id"], "page_no": upload["page_no"], "created": False}
    if upload["status"] != "ready":
        raise ApiError(409, "not_ready", "This page cannot be accepted: it is not ready for review.")
    rows = scans.draft_rows(conn, upload_id)
    names = [{"raw": m["raw_name"], "member": m["canonical_name"], "is_new": m["is_new"]}
             for m in scans.name_matches(conn, upload_id)]
    problems = accept_problems(conn, upload, rows, names)
    if problems:
        first = problems[0]
        raise ApiError(422, "not_ready", first["message"], field=first["field"])
    meeting = next(r for r in rows if r["tbl"] == "meetings")
    page_no = scans.next_page_no(conn, chama_id)
    scans.set_upload(conn, upload_id, status="accepted", page_no=page_no, accepted_by=user_id,
                     accepted_at=datetime.now(timezone.utc),
                     meeting_date=parse_meeting_date(meeting["cells"].get("meeting_date")))
    run_id, created = scans.add_run(conn, upload_id, chama_id)
    scans.add_job(conn, "run_pipeline", upload_id)
    return {"run_id": run_id, "page_no": page_no, "created": created}


def discard(conn: Connection, upload_id: int, chama_id: str) -> None:
    upload = require(conn, upload_id, chama_id, lock=True)
    if upload["status"] == "accepted":
        raise ApiError(409, "accepted", "This page has been accepted and cannot be discarded.")
    if upload["status"] in ("queued", "reading"):
        raise ApiError(409, "reading", "The page is still being read. Wait until it is ready, then discard it.")
    scans.set_upload(conn, upload_id, status="discarded")


def retry(conn: Connection, upload_id: int, chama_id: str) -> dict:
    """Run a failed step again on the same upload: never a second upload or run (X10)."""
    upload = require(conn, upload_id, chama_id, lock=True)
    if upload["status"] in ("failed", "discarded"):
        scans.set_upload(conn, upload_id, status="queued", problem=None)
        scans.add_job(conn, "read_photo", upload_id)
        return {"retrying": "read_photo"}
    run = scans.run_for(conn, upload_id)
    if upload["status"] == "accepted" and run and run["status"] == "failed":
        scans.set_run(conn, run["id"], "queued")
        for step in scans.STEPS:
            scans.set_step(conn, run["id"], step, "waiting")
        scans.add_job(conn, "run_pipeline", upload_id)
        return {"retrying": "run_pipeline", "run_id": run["id"]}
    raise ApiError(409, "nothing_to_retry", "There is nothing to try again: this scan has not failed.")
