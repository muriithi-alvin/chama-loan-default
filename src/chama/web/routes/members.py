"""A member's own pages (MEM-1, MEM-3): their records only, never scores."""
from __future__ import annotations

from fastapi import APIRouter

from chama.web import auth
from chama.web.db import Conn
from chama.web.services import early_warning

router = APIRouter(prefix="/api")


@router.get("/my/summary")
def my_summary(conn: Conn, user: auth.Member) -> dict:
    # the member code comes from the account, never from the address (R4)
    return early_warning.my_summary(conn, user.chama_id, user.member_code)
