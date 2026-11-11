"""app.users, app.sessions and app.signin_steps."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class User:
    id: int
    email: str | None
    role: str                 # official, member or admin
    chama_id: str
    member_code: str | None
    display_name: str | None
    position: str | None
    active: bool
    identity_id: str | None = None
    phone: str | None = None              # +2547...: phone sign-in and officials' second step (D-037)
    phone_identity_id: str | None = None

    @property
    def is_official(self) -> bool:
        return self.role in ("official", "admin")


_COLUMNS = ("id, email, role, chama_id, member_code, display_name, position, active, identity_id, phone, "
            "phone_identity_id")


def _user(row) -> User | None:
    return User(**row._mapping) if row else None


def by_email(conn: Connection, email: str) -> User | None:
    row = conn.execute(text(f"SELECT {_COLUMNS} FROM app.users WHERE lower(email) = lower(:e)"),
                       {"e": email.strip()}).first()
    return _user(row)


def by_phone(conn: Connection, phone: str) -> User | None:
    row = conn.execute(text(f"SELECT {_COLUMNS} FROM app.users WHERE phone = :p"), {"p": phone}).first()
    return _user(row)


def by_id(conn: Connection, user_id: int) -> User | None:
    row = conn.execute(text(f"SELECT {_COLUMNS} FROM app.users WHERE id = :i"), {"i": user_id}).first()
    return _user(row)


def all_users(conn: Connection) -> list[User]:
    rows = conn.execute(text(f"SELECT {_COLUMNS} FROM app.users ORDER BY chama_id, role, email"))
    return [_user(r) for r in rows]


def add(conn: Connection, email: str | None, role: str, chama_id: str, member_code: str | None,
        display_name: str | None, position: str | None, phone: str | None = None) -> int:
    return conn.execute(
        text("INSERT INTO app.users (email, role, chama_id, member_code, display_name, position, phone) "
             "VALUES (:e, :r, :c, :m, :n, :p, :t) RETURNING id"),
        {"e": email.strip() if email else None, "r": role, "c": chama_id, "m": member_code, "n": display_name,
         "p": position, "t": phone},
    ).scalar_one()


def reopen(conn: Connection, user_id: int, role: str, chama_id: str, member_code: str | None,
           display_name: str | None, position: str | None, phone: str | None = None) -> None:
    """Give a deactivated account its new role and record, and open it again."""
    conn.execute(
        text("UPDATE app.users SET role = :r, chama_id = :c, member_code = :m, display_name = :n, "
             "position = :p, phone = coalesce(:t, phone), active = true WHERE id = :i"),
        {"r": role, "c": chama_id, "m": member_code, "n": display_name, "p": position, "t": phone, "i": user_id},
    )


def set_active(conn: Connection, user_id: int, active: bool) -> None:
    conn.execute(text("UPDATE app.users SET active = :a WHERE id = :i"), {"a": active, "i": user_id})
    if not active:
        end_sessions(conn, user_id)


def link_identity(conn: Connection, user_id: int, identity_id: str) -> None:
    conn.execute(text("UPDATE app.users SET identity_id = :s WHERE id = :i AND identity_id IS NULL"),
                 {"s": identity_id, "i": user_id})


def link_phone_identity(conn: Connection, user_id: int, identity_id: str) -> None:
    conn.execute(text("UPDATE app.users SET phone_identity_id = :s WHERE id = :i AND phone_identity_id IS NULL"),
                 {"s": identity_id, "i": user_id})


# ---- Sign-ins waiting for a texted code -----------------------------------------


def start_step(conn: Connection, token_hash: str, user_id: int, method: str, identity_id: str | None,
               expires_at: datetime) -> None:
    conn.execute(text("UPDATE app.signin_steps SET used_at = now() WHERE user_id = :u AND used_at IS NULL"),
                 {"u": user_id})       # one waiting sign-in per account: the newest
    conn.execute(
        text("INSERT INTO app.signin_steps (token_hash, user_id, method, identity_id, expires_at) "
             "VALUES (:h, :u, :m, :i, :x)"),
        {"h": token_hash, "u": user_id, "m": method, "i": identity_id, "x": expires_at})


def step(conn: Connection, token_hash: str) -> dict | None:
    """A sign-in still waiting for its code: not used, not expired."""
    row = conn.execute(text(
        "SELECT token_hash, user_id, method, identity_id, attempts FROM app.signin_steps "
        "WHERE token_hash = :h AND used_at IS NULL AND expires_at > now() FOR UPDATE"), {"h": token_hash}).first()
    return dict(row._mapping) if row else None


def count_attempt(conn: Connection, token_hash: str) -> int:
    return conn.execute(text("UPDATE app.signin_steps SET attempts = attempts + 1 WHERE token_hash = :h "
                             "RETURNING attempts"), {"h": token_hash}).scalar_one()


def end_step(conn: Connection, token_hash: str) -> None:
    conn.execute(text("UPDATE app.signin_steps SET used_at = now() WHERE token_hash = :h AND used_at IS NULL"),
                 {"h": token_hash})


# ---- Sessions ----------------------------------------------------------------


def start_session(conn: Connection, token_hash: str, user_id: int, csrf_token: str,
                  expires_at: datetime) -> None:
    conn.execute(
        text("INSERT INTO app.sessions (token_hash, user_id, csrf_token, expires_at) "
             "VALUES (:h, :u, :c, :x)"),
        {"h": token_hash, "u": user_id, "c": csrf_token, "x": expires_at},
    )


def session(conn: Connection, token_hash: str):
    """(user, csrf_token) for a live session, else None."""
    row = conn.execute(
        text(f"SELECT s.csrf_token, {', '.join('u.' + c.strip() for c in _COLUMNS.split(','))} "
             "FROM app.sessions s JOIN app.users u ON u.id = s.user_id "
             "WHERE s.token_hash = :h AND s.ended_at IS NULL AND s.expires_at > now() "
             "AND u.active"),
        {"h": token_hash},
    ).first()
    if not row:
        return None
    values = dict(row._mapping)
    csrf = values.pop("csrf_token")
    return User(**values), csrf


def end_session(conn: Connection, token_hash: str) -> None:
    conn.execute(text("UPDATE app.sessions SET ended_at = now() WHERE token_hash = :h "
                      "AND ended_at IS NULL"), {"h": token_hash})


def end_sessions(conn: Connection, user_id: int) -> None:
    conn.execute(text("UPDATE app.sessions SET ended_at = now() WHERE user_id = :u "
                      "AND ended_at IS NULL"), {"u": user_id})
