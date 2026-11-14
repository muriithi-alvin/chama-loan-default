"""Scan routes (OFF-8 to OFF-13; S-6 for /api/uploads and /api/jobs). Officials only.

Every change needs the session's CSRF token (auth.current_session), and the
upload, its draft, its run and its photo are looked up within the
signed-in chama only.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
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
        "source": upload.get("source") or "photo",
        "parts": upload.get("parts") or (1 if upload.get("photo_path") else 0),
        "created_at": upload["created_at"],
        "accepted_at": upload["accepted_at"],
        "attempts": job["attempts"] if job else 0,
        "step": job["step"] if job and job["status"] == "running" else None,   # "reading photo 2 of 3"
        "run_id": run["id"] if run else None,
        "run_status": run["status"] if run else None,
    }


@router.post("/uploads")
async def upload_photo(conn: Conn, user: auth.Official,
                       photos: Annotated[list[UploadFile] | None, File()] = None,
                       photo: Annotated[UploadFile | None, File()] = None,
                       idempotency_key: Annotated[str, Form()] = "") -> dict:
    """One meeting's page in up to 3 photos (`photos`, in order), or one (`photo`)."""
    sent = [f for f in (photos or []) + ([photo] if photo else []) if f is not None]
    if len(sent) > scans.MAX_PARTS:
        raise ApiError(422, "too_many", f"Send at most {scans.MAX_PARTS} photos of one meeting.", field="photo")
    parts = [(await f.read(MAX_FILE_BYTES + 1), f.content_type) for f in sent]
    config = load_config()
    provider, _ = provider_settings(config["extraction"])
    upload, created = scans.save_upload(conn, user.chama_id, user.id, parts, idempotency_key,
                                        config["extraction"], provider)
    return {"upload": _upload_view(upload, data.job_for(conn, upload["id"], "read_photo"), None),
            "created": created}


class TypedPage(BaseModel):
    meeting_date: date
    idempotency_key: str = ""


@router.get("/typed")
def typed_info(conn: Conn, user: auth.Official) -> dict:
    """For the Type-a-page form: the last recorded meeting and its members (D-038)."""
    return scans.typed_start_info(conn, user.chama_id)


@router.post("/typed")
def typed_start(body: TypedPage, conn: Conn, user: auth.Official) -> dict:
    """A page to type in, filled with the members and the balances they carried."""
    upload, created = scans.start_typed(conn, user.chama_id, user.id, body.meeting_date, body.idempotency_key)
    return {"upload": _upload_view(upload, None, None), "created": created}


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
def upload_photo_file(upload_id: int, conn: Conn, user: auth.Official,
                      part: Annotated[int, Query(ge=1, le=3)] = 1) -> FileResponse:
    upload = scans.require(conn, upload_id, user.chama_id)
    files = scans.photo_files(conn, upload)
    refusal = scans.photo_refusal(upload, files)
    if refusal:
        raise ApiError(404, "no_photo", refusal)
    if part > len(files):
        raise ApiError(404, "no_photo", f"This scan has {len(files)} photo{'s' if len(files) > 1 else ''}.")
    return FileResponse(files[part - 1], media_type="image/jpeg", headers=PRIVATE)


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
        scored = {s["member_code"]: s for s in data.scores_on_page(conn, user.chama_id, upload["page_no"] or 0)}
        order = {"high": 0, "medium": 1, "low": 2}
        for code in data.members_on_page(conn, user.chama_id, upload["page_no"] or 0):
            score = scored.get(code)
            reasons = (score or {}).get("reasons") or []
            reason = next((r for r in reasons if r.get("effect") == "raises risk"), reasons[0] if reasons else None)
            words = reason and ((user.language == "sw" and reason.get("sentence_sw")) or reason["sentence"])
            changed.append({"code": code, "name": display_name(names, code),
                            "band": score["band"] if score else None,
                            "reason": words or None})
        changed.sort(key=lambda m: (order.get(m["band"], 3), m["name"]))
    return {**found, "page_no": upload["page_no"], "source": upload["source"], "steps": steps,
            "changed_members": changed}


@router.get("/edits")
def edits(conn: Conn, user: auth.Official, upload: int | None = None) -> dict:
    if upload is not None and data.upload(conn, upload, user.chama_id) is None:
        raise ApiError(404, "not_found", "That scan was not found.")
    return {"edits": data.edits(conn, user.chama_id, upload)}
