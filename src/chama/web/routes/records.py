"""Records routes: meetings and their photos (OFF-5, OFF-6). Officials only."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from chama.web import auth
from chama.web.data import records as records_data
from chama.web.db import Conn
from chama.web.errors import ApiError, not_found
from chama.web.services import records

router = APIRouter(prefix="/api")

PRIVATE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


@router.get("/meetings")
def meetings(conn: Conn, user: auth.Official) -> dict:
    return {"meetings": records.meetings(conn, user.chama_id)}


@router.get("/meetings/{page_no}")
def meeting(page_no: int, conn: Conn, user: auth.Official) -> dict:
    page = records.meeting_page(conn, user.chama_id, page_no)
    if page is None:
        raise not_found(f"Ledger page {page_no}")
    return page


@router.get("/meetings/{page_no}/photo")
def meeting_photo(page_no: int, conn: Conn, user: auth.Official) -> FileResponse:
    page = records_data.meeting(conn, user.chama_id, page_no)
    if page is None:
        raise not_found(f"Ledger page {page_no}")
    refusal = records.photo_refusal(user.chama_id, page, records.entered_uploads(conn, user.chama_id))
    if refusal:
        raise ApiError(404, "no_photo", refusal)
    path = records.photo_file(user.chama_id, page["source_photo"])
    return FileResponse(path, media_type="image/jpeg", headers=PRIVATE)
