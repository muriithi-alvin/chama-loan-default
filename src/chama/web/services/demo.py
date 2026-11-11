"""The interface copy of a chama: its typed pages under the copy's own id (D-028, D-036).

`python -m chama.pipeline demo-chama` writes a copy of a chama's raw Excel
files (data/raw/chama_demo/) that the pipeline treats as an ordinary chama, so
its bands and reasons come out as the real chama's, while a page scanned or
typed into it never touches the real records. The copy's settings in
config/pipeline.yaml say how it is made:

- `names: real` (Humble Sister, D-036): the members keep their agreed names,
  which the chama's officials allowed on screen, except the members listed
  under `renames`. Every spelling in the source's reviewed names is kept,
  pointing at the copy's name, so a photo of a real page is matched at once.
- `names: fictional` (the default, D-028): every member gets a fixed made-up
  name, and the copy is checked for every word of every real name.
- `records_until: YYYY-MM`: pages after that month are left out, for the
  officials to enter in the interface.

In both, free-text columns (remarks, notes, the meeting host) are emptied, as
they can mention people outside the chama; only the date is kept from the
next-meeting note. Photos are not copied; pages refer to <copy id>_pNNN.jpg
so page numbers stay the same. A copy made earlier is moved aside, never
deleted, to data/interim/replaced/.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime

import pandas as pd

from chama import StepFailed
from chama.anonymisation import aliases as alias_files
from chama.anonymisation.anonymise import date_only, find_names
from chama.anonymisation.pseudonymise import member_code, normalise_name, resolve_name
from chama.config import PROJECT_ROOT, shown_path
from chama.ingestion.excel_loader import raw_files, read_workbook
from chama.ingestion.raw_format import expected_columns, sheet_names
from chama.web.services.names import fictional_names

FREE_TEXT = {
    "statements": ["remarks"],
    "meetings": ["host", "notes"],
    "new_loans": ["remarks"],
    "attendance": ["remarks"],
}
_MONTH_WORDS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}
_MONTH_WORDS.update({m[:3]: i for m, i in list(_MONTH_WORDS.items())})
_MONTH_WORDS.update({"sept": 9})


def demo_frames(frames: dict[str, pd.DataFrame], renamed: dict[str, str], source_id: str,
                demo_id: str) -> dict[str, pd.DataFrame]:
    """One workbook's tables with the copy's names and no free text.

    `renamed` maps each normalised spelling to the member's name in the copy.
    """
    out = {}
    for table, df in frames.items():
        df = df.reindex(columns=expected_columns(table)).copy()
        if "member_name" in df:
            unknown = sorted({normalise_name(n) for n in df["member_name"].dropna()}
                             - set(renamed) - {""})
            if unknown:
                raise StepFailed(f"[{source_id}] {len(unknown)} spellings have no reviewed alias. "
                                 "Run the pipeline's name review first.")
            df["member_name"] = [renamed.get(normalise_name(n)) if isinstance(n, str) else None
                                 for n in df["member_name"]]
        for column in FREE_TEXT.get(table, []):
            df[column] = None
        if "next_meeting" in df:
            df["next_meeting"] = df["next_meeting"].map(date_only)
        df["source_photo"] = df["source_photo"].str.replace(
            f"^{source_id}_", f"{demo_id}_", regex=True)
        out[table] = df
    return out


def meeting_month(written, book_year: int) -> tuple[int, int] | None:
    """(year, month) of a meeting date as written: "AUGUST 2024", "6th october 2024",
    "3/8/25". The workbook's year is used when the text gives none."""
    from chama.web.services.scans import parse_meeting_date

    if not isinstance(written, str) or not written.strip():
        return None
    full = parse_meeting_date(written)
    if full:
        return full.year, full.month
    text = written.strip().lower()
    month = next((n for w, n in _MONTH_WORDS.items() if re.search(rf"\b{w}\b", text)), None)
    year = re.search(r"\b(20\d\d)\b", text)
    return (int(year.group(1)) if year else book_year, month) if month else None


def pages_until(meetings: pd.DataFrame, book_year: int, until: tuple[int, int] | None) -> set[str]:
    """The source photos (one per page) of the meetings in or before `until`."""
    if until is None:
        return set(meetings["source_photo"].dropna())
    kept = set()
    for row in meetings.to_dict("records"):
        if book_year != until[0]:
            if book_year < until[0]:
                kept.add(row["source_photo"])
            continue
        when = meeting_month(row.get("meeting_date"), book_year)
        if when is None:
            raise StepFailed(f"Page {row['source_photo']} has no month in its date "
                             f"({row.get('meeting_date')!r}), so records_until cannot place it.")
        if when <= until:
            kept.add(row["source_photo"])
    return kept


def _until(value) -> tuple[int, int] | None:
    if value in (None, ""):
        return None
    found = re.fullmatch(r"(\d{4})-(\d{1,2})", str(value).strip())
    if not found or not 1 <= int(found.group(2)) <= 12:
        raise StepFailed(f"records_until must be a month such as 2024-07, not {value!r}.")
    return int(found.group(1)), int(found.group(2))


def copy_names(settings: dict, spellings: dict[str, str], source_id: str, key: bytes) -> tuple[dict, list]:
    """({normalised spelling: name in the copy}, the copy's member names)."""
    canonical = sorted(set(spellings.values()))
    if settings.get("names", "fictional") == "real":
        renames = settings.get("renames") or {}
        missing = sorted(set(renames) - set(canonical))
        if missing:
            raise StepFailed(f"renames lists {', '.join(missing)}, not a member of {source_id} "
                             f"(members: {', '.join(canonical)}).")
        clash = set(renames.values()) & (set(canonical) - set(renames))
        if clash:
            raise StepFailed(f"{', '.join(sorted(clash))} is already a member's name; choose another.")
        to = {name: renames.get(name, name) for name in canonical}
    elif settings.get("names", "fictional") == "fictional":
        code_of = {name: member_code(name, source_id, key) for name in canonical}
        fictional = fictional_names(code_of.values(), sorted(set(canonical) | set(spellings)))
        to = {name: fictional[code_of[name]] for name in canonical}
    else:
        raise StepFailed(f"names must be real or fictional, not {settings.get('names')!r}.")
    renamed = {raw: to[resolve_name(raw, spellings)] for raw in spellings}
    for name, new in to.items():
        renamed.setdefault(normalise_name(name), new)
        renamed.setdefault(normalise_name(new), new)
    return renamed, sorted(set(to.values()))


def _set_aside(demo_id: str, demo_dir, photos_dir) -> str | None:
    """Move an earlier copy's workbooks, scans, photos and names to data/interim/replaced/."""
    old = [p for p in demo_dir.glob("*.xlsx")] + [p for p in (demo_dir / "scans").glob("*.xlsx")]
    old += [p for p in photos_dir.glob("*.jpg")] if photos_dir.is_dir() else []
    names = alias_files.review_file(demo_id)
    old += [names] if names.exists() else []
    if not old:
        return None
    to = PROJECT_ROOT / "data" / "interim" / "replaced" / f"{demo_id}-{datetime.now().astimezone():%Y%m%d-%H%M%S}"
    for path in old:
        part = "scans" if path.parent.name == "scans" else "photos" if path.suffix == ".jpg" else ""
        (to / part).mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(to / part / path.name))
    return str(shown_path(to))


def build_demo_chama(config: dict, key: bytes, source_id: str | None = None,
                     demo_id: str = "chama_demo") -> None:
    chamas = {c["id"]: c for c in config["chamas"]}
    if demo_id not in chamas or not chamas[demo_id].get("demo"):
        raise StepFailed(f"Add {demo_id} to chamas in config/pipeline.yaml with demo: true first.")
    settings = chamas[demo_id]
    source_id = source_id or settings.get("copy_of") or "chama_b"
    if source_id not in chamas or chamas[source_id].get("demo"):
        raise StepFailed(f"{source_id} is not a real chama in config/pipeline.yaml.")
    real = settings.get("names", "fictional") == "real"
    until = _until(settings.get("records_until"))

    review = alias_files.review_file(source_id)
    if not review.exists():
        raise StepFailed(f"No reviewed names for {source_id}: {shown_path(review)} is missing.")
    spellings = alias_files.read_review_file(review, only_reviewed=True)
    renamed, members = copy_names(settings, spellings, source_id, key)

    source_dir = PROJECT_ROOT / chamas[source_id]["raw_dir"]
    demo_dir = PROJECT_ROOT / settings["raw_dir"]
    files = [p for p in raw_files(source_dir) if p.parent == source_dir]   # typed pages, not scans
    if not files:
        raise StepFailed(f"No Excel files in {shown_path(source_dir)}.")

    books, pages = {}, 0
    for path in files:
        frames, _ = read_workbook(path, source_id)
        year = int(path.stem) if path.stem.isdigit() else 0
        kept = pages_until(frames["meetings"], year, until)
        if not kept:
            continue
        if until:
            frames = {t: df[df["source_photo"].isin(kept)] for t, df in frames.items()}
        pages += len(kept)
        books[path.name] = demo_frames(frames, renamed, source_id, demo_id)
    if not books:
        raise StepFailed(f"No pages of {source_id} are in or before records_until.")
    if not real:
        leaks = {}
        known = sorted(set(spellings.values()) | set(spellings))
        for name, frames in books.items():
            for column, count in find_names(frames, known).items():
                leaks[f"{name} {column}"] = count
        if leaks:
            detail = ", ".join(f"{place} ({n})" for place, n in leaks.items())
            raise StepFailed(f"Real names would be left in the demo copy: {detail}. Nothing was written.")

    moved = _set_aside(demo_id, demo_dir, PROJECT_ROOT / settings["photos_dir"])
    demo_dir.mkdir(parents=True, exist_ok=True)
    sheets = sheet_names()
    for name, frames in books.items():
        with pd.ExcelWriter(demo_dir / name, engine="openpyxl") as writer:
            for table, df in frames.items():
                df.to_excel(writer, sheet_name=sheets[table], index=False)

    # Real names: every known spelling, so photos of real pages match at once.
    # Fictional: only the made-up names, so no real spelling reaches the copy.
    names = pd.DataFrame([{"raw_name": raw, "canonical_name": name, "status": "reviewed", "score": 1.0,
                           "similar_to": "", "occurrences": 0, "first_photo": ""}
                          for raw, name in sorted(renamed.items(), key=lambda kv: (kv[1], kv[0]))
                          if real or raw == normalise_name(name)])
    alias_files.write_review_file(names, alias_files.review_file(demo_id))
    if moved:
        print(f"[{demo_id}] the earlier copy (with its scanned pages) was moved to {moved}")
    kind = "their real names" if real else "fictional names"
    shown = f", records to {until[0]}-{until[1]:02d}" if until else ""
    print(f"[{demo_id}] {len(books)} workbooks, {pages} pages written to {shown_path(demo_dir)}{shown}; "
          f"{len(members)} members with {kind}")
    for old, new in (settings.get("renames") or {}).items() if real else []:
        print(f"[{demo_id}] {old} is shown as {new} in this copy only")
    print(f"[{demo_id}] reviewed names: {shown_path(alias_files.review_file(demo_id))}")
    print("Next: python -m chama.pipeline all, then python -m chama.pipeline score")
