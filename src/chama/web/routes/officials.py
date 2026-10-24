"""Officials' early-warning routes (OFF-1 to OFF-3; S-6 for /api/members).

Each route depends on auth.official: the chama always comes from the
signed-in account, and a member code from another chama gets "not allowed".
"""
from __future__ import annotations

from fastapi import APIRouter

from chama.web import auth
from chama.web.data import records
from chama.web.db import Conn
from chama.web.errors import not_allowed
from chama.web.services import early_warning

router = APIRouter(prefix="/api")


@router.get("/overview")
def overview(conn: Conn, user: auth.Official) -> dict:
    return early_warning.overview(conn, user.chama_id)


@router.get("/scores/latest")
def latest_scores(conn: Conn, user: auth.Official) -> dict:
    """For the overview's check every 60 s: when the newest scores were saved."""
    return {"scored_at": records.last_scored_at(conn, user.chama_id),
            "page_no": records.latest_scored_page(conn, user.chama_id)}


@router.get("/members")
def members(conn: Conn, user: auth.Official) -> dict:
    return early_warning.members_list(conn, user.chama_id)


@router.get("/members/{code}")
def member(code: str, conn: Conn, user: auth.Official) -> dict:
    if not records.is_member_of(conn, user.chama_id, code):
        raise not_allowed()   # another chama's member, or no such code: the same answer
    return early_warning.member_page(conn, user.chama_id, code)
