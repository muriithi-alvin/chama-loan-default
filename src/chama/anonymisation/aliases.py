"""Step 2 - Name matching: link the different spellings of each member.

The ledgers write the same person in different ways ("J. Kamau", "Kamau John",
"John Kamau"). This step suggests which spellings belong to one member and
writes them to a review file, data/interim/aliases_<chama>.csv. A person
checks the file, corrects `canonical_name` where needed, and loads it into
private.member_aliases. Nothing is merged without that review.

Spellings are stored normalised (see pseudonymise.normalise_name), so
"J. Kamau" and "j kamau" are one row.
"""
from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.anonymisation.pseudonymise import normalise_name
from chama.config import PROJECT_ROOT

# Two spellings scoring at least this are suggested as the same member.
MATCH_THRESHOLD = 0.85
# A new member whose name scores at least this against another member is
# pointed out in `similar_to`, in case they are one person after all.
SIMILAR_THRESHOLD = 0.6
# Raw tables that hold member names.
NAME_TABLES = ["statements", "new_loans", "attendance"]
REVIEW_COLUMNS = [
    "raw_name", "canonical_name", "status", "score", "similar_to", "occurrences", "first_photo",
]


def _word_score(a: str, b: str) -> float:
    """How alike two single names are. An initial matches any name starting with it."""
    if len(a) == 1 or len(b) == 1:
        return 0.9 if a[0] == b[0] else 0.0
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(a: str, b: str) -> float:
    """Score from 0 to 1 for how likely two spellings are the same person.

    Allows for spelling slips (Wanjiku / Wanjiko), initials (J Kamau), swapped
    order (Kamau John) and a missing name (Kamau / John Kamau).
    """
    a, b = normalise_name(a), normalise_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long_ = sorted((a.split(), b.split()), key=len)
    paired = sum(max(_word_score(s, w) for w in long_) for s in short) / len(short)
    if len(short) < len(long_):
        paired *= 0.9  # a name is missing: possible, but needs a closer look
    whole = SequenceMatcher(None, " ".join(sorted(short)), " ".join(sorted(long_))).ratio()
    return round(max(paired, whole), 3)


def name_counts(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Every normalised spelling, how often it appears and the first photo it is on."""
    parts = [df[["member_name", "source_photo"]] for df in frames if "member_name" in df]
    columns = ["raw_name", "occurrences", "first_photo"]
    if not parts:
        return pd.DataFrame(columns=columns)
    df = pd.concat(parts, ignore_index=True)
    df = df[df["member_name"].notna()]
    df = df.assign(raw_name=df["member_name"].map(normalise_name))
    df = df[df["raw_name"] != ""]
    counts = df.groupby("raw_name").agg(
        occurrences=("raw_name", "size"), first_photo=("source_photo", "min")
    )
    return counts.reset_index()[columns]


def _fullness(name: str, occurrences: int) -> tuple:
    """Order for choosing a member's name: whole names before initials, then
    more names, then the spelling used most often."""
    words = name.split()
    return (sum(len(w) > 1 for w in words), len(words), occurrences, len(name))


def suggest_aliases(names: pd.DataFrame, reviewed: dict[str, str] | None = None) -> pd.DataFrame:
    """Suggest a canonical name for every spelling, for a person to review.

    names: one row per spelling with `raw_name`, `occurrences` and `first_photo`
        (see name_counts()).
    reviewed: spellings already checked, {normalised spelling: canonical name}.
        They are kept as they are, and new spellings can join their members.

    `status` in the result:
        reviewed - checked and loaded before; unchanged
        new      - no close match; this spelling is a member's name
        check    - looks like another spelling of `canonical_name`; confirm or correct
    `similar_to` names the closest other member of a new spelling, with its
    score, when the two might still be one person.
    """
    reviewed = reviewed or {}
    agreed = {normalise_name(c): c for c in reviewed.values()}
    occurrences = dict(zip(names["raw_name"], names["occurrences"]))
    new = [n for n in names["raw_name"] if n not in reviewed]
    new.sort(key=lambda n: _fullness(n, occurrences[n]), reverse=True)

    # Each group is led by an agreed canonical name or by its fullest spelling.
    groups: dict[str, list[str]] = {leader: [] for leader in agreed}
    for spelling in new:
        scores = {leader: name_similarity(spelling, leader) for leader in groups}
        best = max(scores, key=scores.get, default=None)
        if best is not None and scores[best] >= MATCH_THRESHOLD:
            groups[best].append(spelling)
        else:
            groups[spelling] = [spelling]

    canonical_of = {leader: agreed.get(leader) or leader.title() for leader in groups}

    def similar_to(leader: str) -> str:
        scores = {canonical_of[o]: name_similarity(leader, o) for o in groups if o != leader}
        name = max(scores, key=scores.get, default=None)
        if name is None or scores[name] < SIMILAR_THRESHOLD:
            return ""
        return f"{name} ({scores[name]:.2f})"

    rows = [
        {"raw_name": raw, "canonical_name": canonical, "status": "reviewed"}
        for raw, canonical in reviewed.items()
    ]
    for leader, spellings in groups.items():
        for spelling in spellings:
            own_name = spelling == leader and leader not in agreed
            rows.append(
                {
                    "raw_name": spelling,
                    "canonical_name": canonical_of[leader],
                    "status": "new" if own_name else "check",
                    "score": 1.0 if own_name else name_similarity(spelling, leader),
                    "similar_to": similar_to(leader) if own_name else "",
                }
            )
    result = pd.DataFrame(rows, columns=REVIEW_COLUMNS[:5]).fillna({"similar_to": ""})
    result = result.merge(names, on="raw_name", how="left")
    result["occurrences"] = result["occurrences"].fillna(0).astype(int)
    return result.sort_values(["canonical_name", "status", "raw_name"], ignore_index=True)[
        REVIEW_COLUMNS
    ]


def review_file(chama_id: str) -> Path:
    return PROJECT_ROOT / "data" / "interim" / f"aliases_{chama_id}.csv"


def _shown(path: Path) -> Path:
    """The path relative to the project folder, for messages."""
    return path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path


def write_review_file(suggestions: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    suggestions.to_csv(path, index=False, encoding="utf-8-sig")  # -sig: Excel reads it right
    return path


def read_review_file(path: Path) -> dict[str, str]:
    """A reviewed file as {normalised spelling: canonical name}.

    Stops if a row has no canonical name or one spelling is given two names.
    """
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    df["raw_name"] = df["raw_name"].map(normalise_name)
    df["canonical_name"] = df["canonical_name"].map(lambda c: " ".join(c.split()))
    df = df[df["raw_name"] != ""]

    blank = [i + 2 for i in df.index[df["canonical_name"] == ""]]  # Excel row numbers
    if blank:
        raise StepFailed(f"{path.name}: no canonical_name on rows {blank}")
    names_per_spelling = df.groupby("raw_name")["canonical_name"].nunique()
    clashes = list(names_per_spelling[names_per_spelling > 1].index)
    if clashes:
        raise StepFailed(f"{path.name}: {len(clashes)} spellings are given two different names")
    return dict(zip(df["raw_name"], df["canonical_name"]))


# ---- Database ---------------------------------------------------------------


def raw_names(engine, chama_id: str) -> pd.DataFrame:
    """name_counts() for one Chama's raw tables."""
    from sqlalchemy import text

    from chama.db import table_exists

    frames = []
    with engine.connect() as conn:
        for table in NAME_TABLES:
            if table_exists(conn, f"raw.{table}"):
                sql = text(f"SELECT member_name, source_photo FROM raw.{table} WHERE chama_id = :c")
                frames.append(pd.read_sql(sql, conn, params={"c": chama_id}))
    return name_counts(frames)


def saved_aliases(engine, chama_id: str | None = None) -> dict[str, dict[str, str]]:
    """private.member_aliases as {chama_id: {spelling: canonical name}}."""
    from sqlalchemy import text

    sql = "SELECT chama_id, raw_name, canonical_name FROM private.member_aliases"
    params = {}
    if chama_id:
        sql += " WHERE chama_id = :c"
        params = {"c": chama_id}
    result: dict[str, dict[str, str]] = {}
    with engine.connect() as conn:
        for cid, raw, canonical in conn.execute(text(sql), params):
            result.setdefault(cid, {})[raw] = canonical
    return result


def save_aliases(engine, chama_id: str, aliases: dict[str, str]) -> None:
    """Replace one Chama's rows in private.member_aliases."""
    from sqlalchemy import text

    rows = [{"c": chama_id, "r": raw, "n": name} for raw, name in aliases.items()]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM private.member_aliases WHERE chama_id = :c"), {"c": chama_id})
        if rows:
            conn.execute(
                text(
                    "INSERT INTO private.member_aliases (chama_id, raw_name, canonical_name) "
                    "VALUES (:c, :r, :n)"
                ),
                rows,
            )


# ---- Pipeline steps ---------------------------------------------------------


def run_suggest(config: dict, engine, overwrite: bool = False) -> None:
    for chama in config["chamas"]:
        cid = chama["id"]
        names = raw_names(engine, cid)
        if names.empty:
            print(f"[{cid}] no names in the raw tables - skipped")
            continue
        reviewed = saved_aliases(engine, cid).get(cid, {})
        path = review_file(cid)
        if path.exists() and not overwrite and _has_unloaded_changes(path, reviewed):
            raise StepFailed(
                f"[{cid}] {_shown(path)} has changes that are not loaded yet. "
                "Run load-aliases first, or add --overwrite to replace the file."
            )
        suggestions = suggest_aliases(names, reviewed)
        write_review_file(suggestions, path)
        status = suggestions["status"].value_counts()
        print(
            f"[{cid}] {len(suggestions)} spellings -> {suggestions['canonical_name'].nunique()} "
            f"members | to check: {status.get('check', 0)}, new: {status.get('new', 0)}, "
            f"reviewed before: {status.get('reviewed', 0)}"
        )
        print(f"[{cid}] review file: {_shown(path)}")


def _has_unloaded_changes(path: Path, reviewed: dict[str, str]) -> bool:
    try:
        return read_review_file(path) != reviewed
    except (StepFailed, ValueError, KeyError):
        return True  # half-edited file: treat as unsaved work


def run_load(config: dict, engine) -> None:
    for chama in config["chamas"]:
        cid = chama["id"]
        path = review_file(cid)
        if not path.exists():
            print(f"[{cid}] no review file - skipped")
            continue
        aliases = read_review_file(path)
        save_aliases(engine, cid, aliases)
        members = len({normalise_name(n) for n in aliases.values()})
        print(f"[{cid}] {len(aliases)} spellings -> {members} members saved to private.member_aliases")
