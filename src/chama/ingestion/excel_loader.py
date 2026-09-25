"""Step 1 - Ingestion: copy the raw Excel sheets into the `raw` schema unchanged.

Every value is kept as text, exactly as typed from the ledger photos.
Cleaning and anonymisation happen in later steps, never here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chama.config import PROJECT_ROOT


def read_workbook(path: Path, sheets: dict[str, str], chama_id: str) -> dict[str, pd.DataFrame]:
    """Read the expected sheets as text. Missing sheets are skipped with a message."""
    available = pd.ExcelFile(path).sheet_names
    frames: dict[str, pd.DataFrame] = {}
    for table, sheet in sheets.items():
        if sheet not in available:
            print(f"[{chama_id}] sheet '{sheet}' not found - skipped")
            continue
        df = pd.read_excel(path, sheet_name=sheet, dtype=str)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        df["chama_id"] = chama_id
        df["source_file"] = path.name
        df["source_row"] = range(2, len(df) + 2)  # matches the Excel row number
        df["loaded_at"] = datetime.now(timezone.utc)
        frames[table] = df
    return frames


def load_to_raw(frames: dict[str, pd.DataFrame], engine, chama_id: str, source_file: str) -> None:
    """Replace this Chama's rows in raw.<table> and log the load."""
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, df in frames.items():
            exists = conn.execute(
                text("SELECT to_regclass(:t)"), {"t": f"raw.{table}"}
            ).scalar()
            if exists:
                conn.execute(text(f"DELETE FROM raw.{table} WHERE chama_id = :c"), {"c": chama_id})
            df.to_sql(table, conn, schema="raw", if_exists="append", index=False)
            conn.execute(
                text(
                    "INSERT INTO raw.load_log (chama_id, source_file, sheet, row_count) "
                    "VALUES (:c, :f, :s, :n)"
                ),
                {"c": chama_id, "f": source_file, "s": table, "n": len(df)},
            )
            print(f"[{chama_id}] raw.{table}: {len(df)} rows")


def run(config: dict, engine) -> None:
    for chama in config["chamas"]:
        path = PROJECT_ROOT / chama["raw_file"]
        if not path.exists():
            print(f"[{chama['id']}] {path.name} not found - skipped")
            continue
        frames = read_workbook(path, config["sheets"], chama["id"])
        load_to_raw(frames, engine, chama["id"], path.name)
