"""The demo chama: a copy of a real chama's typed pages with fictional names (D-028).

For the review and any projector, `python -m chama.pipeline demo-chama` writes
a copy of a chama's raw Excel files in which every member is renamed to their
fixed fictional name (names.fictional_names). The copy is an ordinary chama to
the pipeline (data/raw/chama_demo/), so its bands and reasons come out exactly
as the real chama's, while a scan accepted into it never touches the real
records. In the copy:

- every spelling of a member becomes that member's one fictional name, so the
  copy's alias file has one reviewed row per member;
- free-text columns (remarks, notes, the meeting host) are emptied, as they
  can mention people; only the date is kept from the next-meeting note;
- photos are not copied: the real photos show real names. Pages refer to
  <demo id>_pNNN.jpg so page numbers stay the same.

The copy is checked for every word of every real name before it is saved.
"""
from __future__ import annotations

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


def demo_frames(frames: dict[str, pd.DataFrame], renamed: dict[str, str], source_id: str,
                demo_id: str) -> dict[str, pd.DataFrame]:
    """One workbook's tables with fictional names and no free text.

    `renamed` maps each normalised spelling to the member's fictional name.
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


def build_demo_chama(config: dict, key: bytes, source_id: str = "chama_b",
                     demo_id: str = "chama_demo") -> None:
    chamas = {c["id"]: c for c in config["chamas"]}
    if demo_id not in chamas or not chamas[demo_id].get("demo"):
        raise StepFailed(f"Add {demo_id} to chamas in config/pipeline.yaml with demo: true first.")
    if source_id not in chamas or chamas[source_id].get("demo"):
        raise StepFailed(f"{source_id} is not a real chama in config/pipeline.yaml.")

    review = alias_files.review_file(source_id)
    if not review.exists():
        raise StepFailed(f"No reviewed names for {source_id}: {shown_path(review)} is missing.")
    spellings = alias_files.read_review_file(review, only_reviewed=True)
    canonical = sorted({name for name in spellings.values()})
    code_of = {name: member_code(name, source_id, key) for name in canonical}
    real = sorted(set(canonical) | set(spellings))
    fictional = fictional_names(code_of.values(), real)
    renamed = {raw: fictional[code_of[resolve_name(raw, spellings)]] for raw in spellings}
    for name in canonical:
        renamed.setdefault(normalise_name(name), fictional[code_of[name]])

    source_dir = PROJECT_ROOT / chamas[source_id]["raw_dir"]
    demo_dir = PROJECT_ROOT / chamas[demo_id]["raw_dir"]
    files = raw_files(source_dir)
    if not files:
        raise StepFailed(f"No Excel files in {shown_path(source_dir)}.")

    books = {}
    for path in files:
        frames, _ = read_workbook(path, source_id)
        books[path.name] = demo_frames(frames, renamed, source_id, demo_id)
    leaks = {}
    for name, frames in books.items():
        for column, count in find_names(frames, real).items():
            leaks[f"{name} {column}"] = count
    if leaks:
        detail = ", ".join(f"{place} ({n})" for place, n in leaks.items())
        raise StepFailed(f"Real names would be left in the demo copy: {detail}. Nothing was written.")

    demo_dir.mkdir(parents=True, exist_ok=True)
    sheets = sheet_names()
    for name, frames in books.items():
        with pd.ExcelWriter(demo_dir / name, engine="openpyxl") as writer:
            for table, df in frames.items():
                df.to_excel(writer, sheet_name=sheets[table], index=False)

    names = pd.DataFrame({"raw_name": [normalise_name(n) for n in fictional.values()],
                          "canonical_name": list(fictional.values()), "status": "reviewed",
                          "score": 1.0, "similar_to": "", "occurrences": 0, "first_photo": ""})
    alias_files.write_review_file(names, alias_files.review_file(demo_id))
    print(f"[{demo_id}] {len(books)} workbooks written to {shown_path(demo_dir)}, "
          f"{len(fictional)} members with fictional names")
    print(f"[{demo_id}] reviewed names: {shown_path(alias_files.review_file(demo_id))}")
    print("Next: python -m chama.pipeline all, then python -m chama.pipeline score")
