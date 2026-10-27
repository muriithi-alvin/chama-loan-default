"""The pipeline run after a scan is accepted (OFF-11, S-2, S-3).

    ingest -> names -> anonymise -> checks -> score

- ingest: the accepted rows are written as a raw file beside the typed Excel
  files, data/raw/<chama>/scans/scan-<upload>.xlsx, in exactly the typed
  layout, with the page's photo saved as <chama>_p<page>.jpg. The scan is
  then a second raw source: every later reload from files keeps it (S-3).
  The chama's raw tables are reloaded with the existing loader.
- names: each spelling the official matched is added to the chama's reviewed
  names (the review file and private.member_aliases), the same record the
  alias review keeps; the step stops if any spelling is still unmatched.
- anonymise, checks: the existing steps (names to codes; dbt models and tests,
  then the quality report).
- score: bands and reasons for the chama's latest meeting (scoring.py).

Only one run at a time: the steps rebuild shared tables, so the run holds a
database lock. Each step's status, times and any error go to
app.pipeline_steps for the timeline page.
"""
from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from chama import StepFailed
from chama.anonymisation import aliases
from chama.anonymisation.pseudonymise import normalise_name
from chama.config import PROJECT_ROOT
from chama.extraction.schema import PAGE_TABLES
from chama.ingestion.excel_loader import load_to_raw, read_folder
from chama.ingestion.raw_format import expected_columns, sheet_names
from chama.web.data import scans
from chama.web.services.scoring import LoadedModel, score_chama
from chama.web.settings import chamas

RUN_LOCK = 72_640_001  # pg_advisory_lock key: one pipeline run at a time


def scan_file(chama_id: str, upload_id: int) -> Path:
    return PROJECT_ROOT / chamas()[chama_id]["raw_dir"] / "scans" / f"scan-{upload_id:04d}.xlsx"


def photo_name(chama_id: str, page_no: int) -> str:
    return f"{chama_id}_p{page_no:03d}.jpg"


def write_scan(conn, upload: dict) -> Path:
    """The accepted rows as a raw Excel file in the typed layout."""
    rows = scans.draft_rows(conn, upload["id"])
    source_photo = photo_name(upload["chama_id"], upload["page_no"])
    path = scan_file(upload["chama_id"], upload["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets = sheet_names()
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for table in PAGE_TABLES:
            records = [{**r["cells"], "source_photo": source_photo} for r in rows if r["tbl"] == table]
            pd.DataFrame(records, columns=expected_columns(table)).to_excel(
                writer, sheet_name=sheets[table], index=False)
    photos = PROJECT_ROOT / chamas()[upload["chama_id"]]["photos_dir"]
    photos.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(upload["photo_path"], photos / source_photo)
    return path


def new_canonical(raw: str) -> str:
    return " ".join(w.capitalize() for w in normalise_name(raw).split())


def save_names(engine, conn, upload: dict) -> int:
    """Add the page's matched spellings to the chama's reviewed names."""
    chama_id = upload["chama_id"]
    matches = scans.name_matches(conn, upload["id"])
    unmatched = [m["raw_name"] for m in matches if not m["canonical_name"] and not m["is_new"]]
    if unmatched:
        raise StepFailed(f"{len(unmatched)} names on the page are not matched to a member.")
    found = {m["raw_name"]: (new_canonical(m["raw_name"]) if m["is_new"] else m["canonical_name"])
             for m in matches}
    saved = aliases.saved_aliases(engine, chama_id).get(chama_id, {})
    added = {raw: name for raw, name in found.items() if raw not in saved}
    if not added:
        return 0
    path = aliases.review_file(chama_id)
    existing = (pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("") if path.exists()
                else pd.DataFrame(columns=aliases.REVIEW_COLUMNS))
    rows = pd.DataFrame([{"raw_name": raw, "canonical_name": name, "status": "reviewed", "score": "",
                          "similar_to": "", "occurrences": "", "first_photo": photo_name(chama_id, upload["page_no"])}
                         for raw, name in added.items()])
    aliases.write_review_file(pd.concat([existing, rows], ignore_index=True), path)
    aliases.save_aliases(engine, chama_id, {**saved, **added})
    return len(added)


def run_pipeline(engine, config: dict, key: bytes, upload_id: int, loaded: LoadedModel,
                 log: Callable[[str], None] = print) -> None:
    from chama.anonymisation import anonymise
    from chama.pipeline import run_clean

    with engine.connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:k)"), {"k": RUN_LOCK})
        lock.commit()
        try:
            with engine.begin() as conn:
                upload = scans.upload_row(conn, upload_id)
                run = scans.run_for(conn, upload_id)
                scans.set_run(conn, run["id"], "running")
            chama_id = upload["chama_id"]
            chama = chamas()[chama_id]

            def ingest():
                with engine.begin() as conn:
                    write_scan(conn, dict(upload))
                frames, _ = read_folder(PROJECT_ROOT / chama["raw_dir"], chama_id)
                load_to_raw(frames, engine, chama_id, chama["raw_dir"])

            def names():
                with engine.begin() as conn:
                    added = save_names(engine, conn, dict(upload))
                aliases.restore_reviewed(config, engine)
                left = aliases.unreviewed_counts(config, engine).get(chama_id)
                if left:
                    raise StepFailed(f"{left} name spellings in the chama's records have no reviewed match.")
                log(f"names: {added} new spellings saved")

            steps = {
                "ingest": ingest,
                "names": names,
                "anonymise": lambda: anonymise.run(engine, key),
                "checks": lambda: run_clean(config, engine),
                "score": lambda: score_chama(engine, loaded, chama_id),
            }
            for name in scans.STEPS:
                with engine.begin() as conn:
                    scans.set_step(conn, run["id"], name, "running")
                start = time.perf_counter()
                try:
                    steps[name]()
                except StepFailed as e:
                    message = str(e)
                    if name == "checks":   # dbt's own message points at a terminal
                        message = ("A data check did not pass, or a table could not be built. The admin can "
                                   "see which in the worker's log; fix the rows with a new scan or ask the admin.")
                    with engine.begin() as conn:
                        scans.set_step(conn, run["id"], name, "failed", message[:500])
                        scans.set_run(conn, run["id"], "failed")
                    raise
                except Exception as e:
                    with engine.begin() as conn:
                        scans.set_step(conn, run["id"], name, "failed",
                                       f"The {name} step stopped unexpectedly. The admin can see the details "
                                       "in the worker's log.")
                        scans.set_run(conn, run["id"], "failed")
                    raise StepFailed(f"{name} stopped unexpectedly: {type(e).__name__}") from e
                with engine.begin() as conn:
                    scans.set_step(conn, run["id"], name, "done")
                log(f"run {run['id']}: {name} done in {time.perf_counter() - start:.1f} s")
            with engine.begin() as conn:
                scans.set_run(conn, run["id"], "done")
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": RUN_LOCK})
            lock.commit()
