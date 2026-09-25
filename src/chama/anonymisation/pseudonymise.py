"""Step 2 - Anonymisation: replace member names with stable codes.

How it works:
1. normalise_name() tidies a name so small writing differences don't matter
   ("  J. Kamau " and "j kamau" become "j kamau").
2. The alias table (private.member_aliases) links different spellings of the
   same person to one canonical name. This link is checked by a person.
3. member_code() turns a canonical name into a code using HMAC-SHA256 with a
   secret key. The same name always gives the same code, but the name cannot
   be recovered from the code without the key.
"""
from __future__ import annotations

import hashlib
import hmac
import re

CODE_LENGTH = 8


def normalise_name(name: str) -> str:
    """Lower-case, remove dots and commas, and collapse extra spaces."""
    if name is None:
        return ""
    name = re.sub(r"[.,]", " ", str(name).lower())
    return re.sub(r"\s+", " ", name).strip()


def member_code(canonical_name: str, chama_id: str, key: bytes) -> str:
    """Stable, non-reversible code such as 'M-3f9a1c2b'.

    The chama_id is included so two different people with the same name in
    different Chamas get different codes.
    """
    message = f"{chama_id}|{normalise_name(canonical_name)}".encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"M-{digest[:CODE_LENGTH]}"


def resolve_name(raw_name: str, aliases: dict[str, str]) -> str:
    """Map a raw spelling to its canonical name using the alias table.

    `aliases` maps normalised raw names to canonical names. Unknown names are
    returned as they are (normalised) and should be reviewed.
    """
    key = normalise_name(raw_name)
    return aliases.get(key, key)


def pseudonymise_column(values, chama_id: str, aliases: dict[str, str], key: bytes) -> list[str]:
    """Replace a list/Series of raw names with member codes."""
    return [member_code(resolve_name(v, aliases), chama_id, key) for v in values]
