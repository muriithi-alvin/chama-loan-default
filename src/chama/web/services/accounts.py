"""Accounts for the web interface, set up by the admin from the command line (R3).

    python -m chama.pipeline web-user add --email <email> --role official --chama chama_demo
        --name "Grace Achieng" --position treasurer
    python -m chama.pipeline web-user add --email <email> --role member --chama chama_demo
        --member <code>
    python -m chama.pipeline web-user list
    python -m chama.pipeline web-user deactivate --email <email>

The password is set in Supabase (Authentication > Users > Add user); this
only says which chama, role and member record the email may open.
"""
from __future__ import annotations

from sqlalchemy import text

from chama import StepFailed
from chama.web.data import users
from chama.web.services.names import display_name, member_names
from chama.web.settings import chamas

ROLES = ("official", "member", "admin")
POSITIONS = ("chair", "treasurer", "secretary")


def add_user(engine, email: str, role: str, chama_id: str, member_code: str | None,
             name: str | None, position: str | None) -> str:
    email = email.strip()
    if "@" not in email:
        raise StepFailed(f"{email!r} is not an email address.")
    if role not in ROLES:
        raise StepFailed(f"Role must be one of {', '.join(ROLES)}.")
    if chama_id not in chamas():
        raise StepFailed(f"No chama {chama_id!r} in config/pipeline.yaml "
                         f"(known: {', '.join(chamas())}).")
    if role == "member" and not member_code:
        raise StepFailed("A member account needs --member <code>: the member's record it opens.")
    if role != "member" and member_code:
        raise StepFailed("Only member accounts take --member.")
    if position and position not in POSITIONS:
        raise StepFailed(f"Position must be one of {', '.join(POSITIONS)}.")
    with engine.begin() as conn:
        if users.by_email(conn, email):
            raise StepFailed(f"{email} already has an account. Deactivate it first to change it.")
        if member_code:
            known = conn.execute(text("SELECT 1 FROM private.member_codes WHERE chama_id = :c "
                                      "AND member_code = :m"), {"c": chama_id, "m": member_code}).first()
            if not known:
                raise StepFailed(f"No member {member_code} in {chama_id}. List the codes with "
                                 "python -m chama.pipeline web-user codes --chama " + chama_id)
        users.add(conn, email, role, chama_id, member_code, name if role != "member" else None, position)
    return f"Added {role} {email} for {chama_id}" + (f" (member {member_code})" if member_code else "")


def list_users(engine) -> list[str]:
    with engine.connect() as conn:
        rows = users.all_users(conn)
    if not rows:
        return ["No accounts yet. Add one with: python -m chama.pipeline web-user add --help"]
    lines = []
    for u in rows:
        state = "active" if u.active else "deactivated"
        who = u.member_code or (u.display_name or "") + (f", {u.position}" if u.position else "")
        lines.append(f"{u.id:>3}  {u.email:<34} {u.role:<9} {u.chama_id:<11} {who:<28} {state}")
    return lines


def deactivate_user(engine, email: str) -> str:
    with engine.begin() as conn:
        user = users.by_email(conn, email)
        if not user:
            raise StepFailed(f"No account for {email}.")
        users.set_active(conn, user.id, False)
    return f"Deactivated {email}; their sessions have ended."


def member_code_list(engine, chama_id: str) -> list[str]:
    """Codes with the names shown on the pages (fictional in demo mode)."""
    with engine.connect() as conn:
        names = member_names(conn, chama_id)
    return [f"{code}  {display_name(names, code)}" for code in sorted(names, key=names.get)]
