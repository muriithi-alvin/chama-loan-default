"""Step 3 - Anonymisation: copy the raw tables to `staging` with member codes.

Each name is linked to its member through private.member_aliases (reviewed by
a person, see aliases.py) and replaced by that member's code (pseudonymise.py).

Free-text columns (remarks, notes, the meeting host) are not copied: they
mention people by name, including people who are not members, so no name list
can clean them reliably. They stay in `raw` for checking against the paper
(decision D-008). Only the date is kept from `next_meeting`.

Nothing is written unless every spelling has a reviewed alias, and the result
is checked for member names before it is saved.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

from chama import StepFailed
from chama.anonymisation.pseudonymise import member_code, normalise_name, resolve_name

# Columns copied to staging for each raw table (free text left out).
KEPT_COLUMNS = {
    "statements": [
        "meeting_date", "line_no", "member_name", "monthly", "loan_before",
        "repayment", "interest", "loan_after", "due", "loan_type",
    ],
    "meetings": [
        "meeting_date", "column_headers", "contribution_total", "brought_forward",
        "total_collection", "cash", "banked", "next_meeting",
    ],
    "new_loans": ["loan_date", "member_name", "amount", "loan_type"],
    "attendance": ["meeting_date", "member_name", "status"],
}
# Where each row came from, so any value can be traced back to its photo.
LINEAGE_COLUMNS = ["source_photo", "unclear", "chama_id", "source_file", "source_row"]
RENAMED = {"member_name": "member_code", "next_meeting": "next_meeting_date"}

_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
]
MONTH_WORDS = set(_MONTH_NAMES) | {m[:3] for m in _MONTH_NAMES} | {"sept"}
_MONTH = "|".join(sorted(MONTH_WORDS, key=len, reverse=True))
_DATE = re.compile(
    rf"\b\d{{1,2}}\s*(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTH})\b\.?(?:\s*,?\s*\d{{4}})?"
    rf"|\b(?:{_MONTH})\b\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s*,?\s*\d{{4}})?"
    rf"|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b",
    re.IGNORECASE,
)


def staging_columns(table: str) -> list[str]:
    """Columns of a staging table, in order."""
    return [RENAMED.get(c, c) for c in KEPT_COLUMNS[table]] + LINEAGE_COLUMNS


def date_only(value) -> str | None:
    """Keep just the date from text such as "<host>'s 9th Feb" -> "9th Feb"."""
    if not isinstance(value, str):
        return None
    match = _DATE.search(value)
    return match.group(0).strip() if match else None


def unmatched_names(frames: dict[str, pd.DataFrame], aliases: dict[str, str]) -> list[str]:
    """Spellings that have no reviewed alias yet."""
    found: set[str] = set()
    for df in frames.values():
        if "member_name" in df:
            found |= {normalise_name(n) for n in df["member_name"].dropna()}
    found.discard("")
    return sorted(found - set(aliases))


def code_table(aliases: dict[str, str], chama_id: str, key: bytes) -> pd.DataFrame:
    """One row per member with its code, for private.member_codes."""
    canonical: dict[str, str] = {}
    for name in aliases.values():
        canonical.setdefault(normalise_name(name), name)
    names = sorted(canonical.values())
    codes = pd.DataFrame(
        {
            "chama_id": chama_id,
            "canonical_name": names,
            "member_code": [member_code(n, chama_id, key) for n in names],
        }
    )
    if codes["member_code"].duplicated().any():
        raise StepFailed(f"[{chama_id}] two members got the same code; increase CODE_LENGTH")
    return codes


def anonymise_table(
    df: pd.DataFrame, table: str, chama_id: str, aliases: dict[str, str], key: bytes
) -> pd.DataFrame:
    """Staging version of one raw table for one Chama: codes, no free text."""
    out = df.reindex(columns=KEPT_COLUMNS[table] + LINEAGE_COLUMNS).copy()
    if "member_name" in out:
        out["member_name"] = [
            member_code(resolve_name(n, aliases), chama_id, key)
            if isinstance(n, str) and normalise_name(n)
            else None
            for n in out["member_name"]
        ]
    if "next_meeting" in out:
        out["next_meeting"] = out["next_meeting"].map(date_only)
    return out.rename(columns=RENAMED).reset_index(drop=True)


def anonymise_chama(
    frames: dict[str, pd.DataFrame], chama_id: str, aliases: dict[str, str], key: bytes
) -> dict[str, pd.DataFrame]:
    """Staging tables for one Chama. Stops if any spelling has no reviewed alias."""
    missing = unmatched_names(frames, aliases)
    if missing:
        raise StepFailed(
            f"[{chama_id}] {len(missing)} name spellings are not in private.member_aliases. "
            "Run suggest-aliases, review the file, then load-aliases."
        )
    return {
        table: anonymise_table(df, table, chama_id, aliases, key)
        for table, df in frames.items()
        if table in KEPT_COLUMNS
    }


def find_names(frames: dict[str, pd.DataFrame], names: Iterable[str]) -> dict[str, int]:
    """Count the values in each column that contain a word of a member's name.

    Returns {"table.column": count}; empty means no name was found. Words
    shorter than 3 letters and month names (which appear in dates) are ignored.
    """
    words = {w for n in names for w in normalise_name(n).split() if len(w) >= 3} - MONTH_WORDS
    skip = {"member_code", *LINEAGE_COLUMNS}
    found: dict[str, int] = {}
    for table, df in frames.items():
        for col in df.columns:
            if col in skip:
                continue
            hits = sum(
                isinstance(v, str) and bool(words & set(re.findall(r"[a-z]+", v.lower())))
                for v in df[col]
            )
            if hits:
                found[f"{table}.{col}"] = hits
    return found


# ---- Database ---------------------------------------------------------------


def read_raw(engine) -> dict[str, pd.DataFrame]:
    """Every raw table that staging is built from."""
    from sqlalchemy import text

    from chama.db import table_exists

    frames = {}
    with engine.connect() as conn:
        for table in KEPT_COLUMNS:
            if table_exists(conn, f"raw.{table}"):
                frames[table] = pd.read_sql(text(f"SELECT * FROM raw.{table}"), conn)
    return frames


def write_staging(engine, staging: dict[str, pd.DataFrame], codes: pd.DataFrame) -> None:
    """Replace the staging tables and private.member_codes in one transaction.

    Rows are deleted rather than tables dropped, so views built on staging
    (for example by dbt) keep working.
    """
    from sqlalchemy import BigInteger, Text, text

    from chama.db import add_missing_columns, table_exists

    with engine.begin() as conn:
        for table, df in staging.items():
            if table_exists(conn, f"staging.{table}"):
                add_missing_columns(conn, "staging", table, df.columns)
                conn.execute(text(f"DELETE FROM staging.{table}"))
            # Values are still text as written; the clean step gives them types.
            types = {c: BigInteger() if c == "source_row" else Text() for c in df.columns}
            df.to_sql(table, conn, schema="staging", if_exists="append", index=False, dtype=types)
        conn.execute(text("DELETE FROM private.member_codes"))
        codes.to_sql("member_codes", conn, schema="private", if_exists="append", index=False)


# ---- Pipeline step ----------------------------------------------------------


def run(engine, key: bytes) -> None:
    from chama.anonymisation.aliases import saved_aliases

    raw = read_raw(engine)
    if not raw:
        raise StepFailed("No raw tables found. Run ingest first.")
    aliases = saved_aliases(engine)
    chama_ids = sorted(set().union(*(set(df["chama_id"]) for df in raw.values())))

    parts: dict[str, list[pd.DataFrame]] = {}
    codes = []
    for cid in chama_ids:
        frames = {t: df[df["chama_id"] == cid] for t, df in raw.items()}
        chama_aliases = aliases.get(cid, {})
        for table, df in anonymise_chama(frames, cid, chama_aliases, key).items():
            parts.setdefault(table, []).append(df)
        codes.append(code_table(chama_aliases, cid, key))

    # Every staging table is written, empty if no workbook has that sheet, so
    # the dbt models that read them always find them.
    staging = {
        t: pd.concat(parts.get(t, []) + [pd.DataFrame(columns=staging_columns(t))], ignore_index=True)
        .reindex(columns=staging_columns(t))
        for t in KEPT_COLUMNS
    }
    all_names = [n for a in aliases.values() for pair in a.items() for n in pair]
    leaks = find_names(staging, all_names)
    if leaks:
        detail = ", ".join(f"{col} ({n} values)" for col, n in leaks.items())
        raise StepFailed(f"Member names found in staging columns: {detail}. Nothing was saved.")

    write_staging(engine, staging, pd.concat(codes, ignore_index=True))
    for table, df in staging.items():
        print(f"staging.{table}: {len(df)} rows")
    members = sum(len(c) for c in codes)
    print(f"private.member_codes: {members} members | name check: no names found in staging")
