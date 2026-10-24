"""The names shown on pages, and the fictional names of demo mode (G5).

Pages show a member's agreed (canonical) name from private.member_codes. With
DEMO_MODE on, every real chama's members are shown with a fixed fictional
Kenyan name chosen from their member code instead, so the same member always
gets the same name and no real name reaches a projector. A demo chama (one
marked `demo: true` in config/pipeline.yaml, see demo.py) already has
fictional names in its records, so they are shown as they are.

No fictional name shares a word with a real member's name, so a fictional
name can never be mistaken for, or reveal, a real one.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from chama.anonymisation.pseudonymise import normalise_name
from chama.web.settings import is_demo_chama, web_settings

# Made up for the demo; any likeness to a real person is chance.
FICTIONAL_NAMES = (
    "Wanjiru Kamau", "Halima Omar", "Mueni Wambua", "Chebet Rotich", "Akinyi Otieno",
    "Nyokabi Mwangi", "Zawadi Mutua", "Neema Kiprono", "Atieno Ouma", "Nafula Wekesa",
    "Kawira Mutembei", "Moraa Nyaboke", "Adhiambo Okoth", "Wairimu Njoroge", "Jeptoo Kosgei",
    "Mwikali Musyoka", "Rehema Salim", "Nekesa Barasa", "Nkatha Gitonga", "Kemunto Onsongo",
    "Waithera Gichuru", "Syokau Kilonzo", "Amina Hassan", "Chepkoech Langat", "Awino Odhiambo",
    "Njeri Kariuki", "Kalekye Mbithi", "Nanjala Simiyu", "Muthoni Ndegwa", "Ndinda Kioko",
)


def name_words(names: Iterable[str]) -> set[str]:
    return {w for n in names for w in normalise_name(n).split() if len(w) > 1}


def fictional_names(codes: Iterable[str], real_names: Iterable[str]) -> dict[str, str]:
    """{member code: fictional name}, the same for a code every time.

    Names sharing a word with any of `real_names` are never used.
    """
    taken = name_words(real_names)
    pool = [n for n in FICTIONAL_NAMES if not name_words([n]) & taken]
    chosen: dict[str, str] = {}
    used: set[str] = set()
    for code in sorted(set(codes)):
        name = f"Member {code[-4:].upper()}"
        if pool:
            start = int(hashlib.sha256(code.encode("utf-8")).hexdigest(), 16) % len(pool)
            for k in range(len(pool)):
                candidate = pool[(start + k) % len(pool)]
                if candidate not in used:
                    name = candidate
                    break
        used.add(name)
        chosen[code] = name
    return chosen


def real_names(conn: Connection) -> list[str]:
    """Every agreed name and spelling of the real (not demo) chamas."""
    rows = conn.execute(text(
        "SELECT chama_id, canonical_name AS name FROM private.member_codes "
        "UNION SELECT chama_id, raw_name FROM private.member_aliases"
    ))
    return [r.name for r in rows if not is_demo_chama(r.chama_id)]


def member_names(conn: Connection, chama_id: str) -> dict[str, str]:
    """{member code: the name to show} for one chama."""
    rows = conn.execute(
        text("SELECT member_code, canonical_name FROM private.member_codes WHERE chama_id = :c"),
        {"c": chama_id},
    ).all()
    if web_settings().demo_mode and not is_demo_chama(chama_id):
        return fictional_names([r.member_code for r in rows], real_names(conn))
    return {r.member_code: r.canonical_name for r in rows}


def display_name(names: dict[str, str], code: str | None) -> str:
    if not code:
        return "Unknown member"
    return names.get(code) or f"Member {code[-4:].upper()}"
