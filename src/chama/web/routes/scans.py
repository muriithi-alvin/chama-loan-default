"""Scan routes (OFF-8 to OFF-13; S-6 for /api/uploads and /api/jobs). Officials only.

Every change needs the session's CSRF token (auth.current_session), and the
upload, its draft, its run and its photo are looked up within the
signed-in chama only.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from chama.config import load_config
from chama.extraction.extractor import provider_settings
from chama.extraction.images import MAX_FILE_BYTES
from chama.web import auth
from chama.web.data import scans as data
from chama.web.db import Conn
from chama.web.errors import ApiError, not_found
from chama.web.services import scans
from chama.web.services.names import display_name, member_names

router = APIRouter(prefix="/api")

PRIVATE = {"Cache-Control": "private, no-store"}


def _upload_view(upload: dict, job: dict | None, run: dict | None) -> dict:
    status = upload["status"]
    if status == "queued" and job and job["status"] == "running":
        status = "reading"
    return {
        "id": upload["id"],
        "status": status,
        "problem": upload["problem"],
        "provider": upload["provider"],
        "model": upload["model"],
        "seconds": upload["seconds"],
        "page_no": upload["page_no"],
        "meeting_date": upload["meeting_date"],
        "created_at": upload["created_at"],
        "accepted_at": upload["accepted_at"],
        "attempts": job["attempts"] if job else 0,
        "run_id": run["id"] if run else None,
        "run_status": run["status"] if run else None,
    }


@router.post("/uploads")
async def upload_photo(conn: Conn, user: auth.Official,
                       photo: Annotated[UploadFile, File()],
                       idempotency_key: Annotated[str, Form()] = "") -> dict:
    data_bytes = await photo.read(MAX_FILE_BYTES + 1)
    config = load_config()
    provider, _ = provider_settings(config["extraction"])
    upload, created = scans.save_upload(conn, user.chama_id, user.id, data_bytes, photo.content_type,
                                        idempotency_key, config["extraction"], provider)
    return {"upload": _upload_view(upload, data.job_for(conn, upload["id"], "read_photo"), None),
            "created": created}


@router.get("/uploads")
def uploads(conn: Conn, user: auth.Official) -> dict:
    return {"uploads": [{
        **_upload_view(u, None, {"id": u["run_id"], "status": u["run_status"]} if u["run_id"] else None),
        "uploaded_by": u["uploaded_by_name"],
        "edits": u["edits"],
    } for u in data.uploads(conn, user.chama_id)]}


@router.get("/uploads/{upload_id}")
def upload_status(upload_id: int, conn: Conn, user: auth.Official) -> dict:
    upload = scans.require(conn, upload_id, user.chama_id)
    return _upload_view(upload, data.job_for(conn, upload_id, "read_photo"), data.run_for(conn, upload_id))


@router.get("/uploads/{upload_id}/photo")
def upload_photo_file(upload_id: int, conn: Conn, user: auth.Official) -> FileResponse:
    upload = scans.require(conn, upload_id, user.chama_id)
    refusal = scans.photo_refusal(upload)
    if refusal:
        raise ApiError(404, "no_photo", refusal)
    return FileResponse(scans.photo_path(upload), media_type="image/jpeg", headers=PRIVATE)


@router.post("/uploads/{upload_id}/retry")
def retry(upload_id: int, conn: Conn, user: auth.Official) -> dict:
    return scans.retry(conn, upload_id, user.chama_id)


@router.get("/uploads/{upload_id}/draft")
def draft(upload_id: int, conn: Conn, user: auth.Official) -> dict:
    return scans.draft_view(conn, upload_id, user.chama_id)


class CellChange(BaseModel):
    column: str
    value: str | None = None


@router.patch("/uploads/{upload_id}/rows/{row_id}")
def edit_cell(upload_id: int, row_id: int, body: CellChange, conn: Conn, user: auth.Official) -> dict:
    scans.edit_cell(conn, upload_id, user.chama_id, row_id, body.column, body.value, user.id)
    return scans.draft_view(conn, upload_id, user.chama_id)


class NewRow(BaseModel):
    table: str


@router.post("/uploads/{upload_id}/rows")
def add_row(upload_id: int, body: NewRow, conn: Conn, user: auth.Official) -> dict:
    row_id = scans.add_row(conn, upload_id, user.chama_id, body.table, user.id)
    return {"row_id": row_id, **scans.draft_view(conn, upload_id, user.chama_id)}


@router.delete("/uploads/{upload_id}/rows/{row_id}")
def delete_row(upload_id: int, row_id: int, conn: Conn, user: auth.Official) -> dict:
    scans.delete_row(conn, upload_id, user.chama_id, row_id, user.id)
    return scans.draft_view(conn, upload_id, user.chama_id)


class NameMatch(BaseModel):
    raw: str
    member: str | None = None
    is_new: bool = False


@router.put("/uploads/{upload_id}/names")
def match_name(upload_id: int, body: NameMatch, conn: Conn, user: auth.Official) -> dict:
    scans.match_name(conn, upload_id, user.chama_id, body.raw, body.member, body.is_new, user.id)
    return scans.draft_view(conn, upload_id, user.chama_id)


@router.post("/uploads/{upload_id}/accept")
def accept(upload_id: int, conn: Conn, user: auth.Official) -> dict:
    return scans.accept(conn, upload_id, user.chama_id, user.id)


@router.post("/uploads/{upload_id}/discard")
def discard(upload_id: int, conn: Conn, user: auth.Official) -> dict:
    scans.discard(conn, upload_id, user.chama_id)
    return {"discarded": True}


@router.get("/jobs/{job_id}")
def job(job_id: int, conn: Conn, user: auth.Official) -> dict:
    found = data.job(conn, job_id)
    if found is None or data.upload(conn, found["upload_id"], user.chama_id) is None:
        raise not_found("That job")
    return {k: found[k] for k in ("id", "kind", "upload_id", "status", "step", "error_message", "attempts",
                                  "created_at", "finished_at")}


@router.get("/runs/{run_id}")
def run(run_id: int, conn: Conn, user: auth.Official) -> dict:
    found = data.run(conn, run_id, user.chama_id)
    if found is None:
        raise not_found("That pipeline run")
    upload = data.upload(conn, found["upload_id"], user.chama_id)
    steps = data.run_steps(conn, run_id)
    changed = []
    if found["status"] == "done":
        names = member_names(conn, user.chama_id)
        changed = [{"code": code, "name": display_name(names, code)}
                   for code in data.members_on_page(conn, user.chama_id, upload["page_no"] or 0)]
    return {**found, "page_no": upload["page_no"], "steps": steps, "changed_members": changed}


@router.get("/edits")
def edits(conn: Conn, user: auth.Official, upload: int | None = None) -> dict:
    if upload is not None and data.upload(conn, upload, user.chama_id) is None:
        raise ApiError(404, "not_found", "That scan was not found.")
    return {"edits": data.edits(conn, user.chama_id, upload)}
