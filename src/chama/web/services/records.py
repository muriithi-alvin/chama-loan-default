"""The records pages: meetings list and meeting page (OFF-5, OFF-6).

A page was typed (from the yearly Excel files) or scanned (accepted from the
Scan page, saved as data/raw/<chama>/scans/scan-<upload>.xlsx, see scans.py).

Ledger photos show every member's real name, so a photo is shown only to
officials, never in demo mode for a typed page, and never for a demo chama's
typed pages, whose real photos belong to the chama they were copied from
(G5, open decision 1).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Connection

from chama.config import PROJECT_ROOT
from chama.web.data import records
from chama.web.services.names import display_name, member_names
from chama.web.settings import chamas, is_demo_chama, web_settings

SCAN_PREFIX = "scan-"


def is_scanned(source_file: str | None) -> bool:
    return (source_file or "").startswith(SCAN_PREFIX)


def photo_file(chama_id: str, source_photo: str | None) -> Path | None:
    """The photo of a page, if there is one, inside the chama's photo folder only."""
    if not source_photo:
        return None
    folder = (PROJECT_ROOT / chamas()[chama_id]["photos_dir"]).resolve()
    path = (folder / source_photo).resolve()
    if folder not in path.parents or not path.is_file():
        return None
    return path


def photo_refusal(chama_id: str, meeting: dict) -> str | None:
    """Why this page's photo may not be shown, or None if it may."""
    scanned = is_scanned(meeting["source_file"])
    if not scanned and is_demo_chama(chama_id):
        return "No photo is kept for this page."
    if not scanned and web_settings().demo_mode:
        return "The photo of this page is not shown here, to keep members' names private."
    if photo_file(chama_id, meeting["source_photo"]) is None:
        return "There is no photo of this page on the server."
    return None


def _num(value) -> float | None:
    return None if value is None else float(value)


def meetings(conn: Connection, chama_id: str) -> list[dict]:
    return [{
        "page_no": m["page_no"],
        "meeting_month": m["meeting_month"],
        "meeting_date": m["meeting_date"],
        "date_estimated": m["date_source"] in ("estimated", "written_month"),
        "contribution_total": _num(m["contribution_total"]),
        "total_collection": _num(m["total_collection"]),
        "lines": m["lines"],
        "new_loans": m["new_loans"],
        "source": "scanned" if is_scanned(m["source_file"]) else "typed",
        "has_issues": m["has_issues"],
    } for m in records.meetings_list(conn, chama_id)]


def meeting_page(conn: Connection, chama_id: str, page_no: int) -> dict | None:
    m = records.meeting(conn, chama_id, page_no)
    if not m:
        return None
    names = member_names(conn, chama_id)
    refusal = photo_refusal(chama_id, m)
    return {
        "page_no": m["page_no"],
        "meeting_month": m["meeting_month"],
        "meeting_date": m["meeting_date"],
        "date_estimated": m["date_source"] in ("estimated", "written_month"),
        "source": "scanned" if is_scanned(m["source_file"]) else "typed",
        "footer": {key: _num(m[key]) for key in
                   ("contribution_total", "brought_forward", "total_collection", "cash", "banked")},
        "unclear": bool(m["unclear"]),
        "issues": m["issues"],
        "photo": {"available": refusal is None, "reason": refusal},
        "lines": [{
            "line": line["line_no"] or line["line_on_page"],
            "name": display_name(names, line["member_code"]),
            "code": line["member_code"],
            "kind": line["line_kind"],
            "loan_type": line["loan_type"],
            "monthly": _num(line["monthly_amount"]),
            "monthly_note": line["monthly_note"],
            "balance_before": _num(line["loan_before"]),
            "repaid": _num(line["repayment"]),
            "interest": _num(line["interest_amount"]) if line["interest_amount"] is not None
            else (f"{float(line['interest_rate_pct']):g}%" if line["interest_rate_pct"] is not None else None),
            "balance_after": _num(line["closing_balance"]),
            "due_month": line["due_month"],
            "unclear": bool(line["unclear"]),
            "issues": line["issues"],
        } for line in records.meeting_lines(conn, chama_id, page_no)],
        "new_loans": [{
            "name": display_name(names, n["member_code"]),
            "code": n["member_code"],
            "amount": _num(n["amount"]),
            "loan_type": n["loan_type"],
            "loan_month": n["loan_month"],
        } for n in records.meeting_new_loans(conn, chama_id, page_no)],
        **records.neighbour_pages(conn, chama_id, page_no),
    }
