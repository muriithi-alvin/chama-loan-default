"""Step 1 - Ingestion: copy the raw Excel sheets into the `raw` schema unchanged.

Every value is kept as text, exactly as typed from the ledger photos.
Cleaning and anonymisation happen in later steps, never here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chama.config import PROJECT_ROOT
from chama.ingestion.raw_format import expected_columns, sheet_names


@dataclass
class SheetReport:
    """What was found in one sheet, so problems are visible before loading."""

    table: str
    rows: int = 0
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    skipped: bool = False

    def summary(self) -> str:
        if self.skipped:
            return f"{self.table}: sheet not found - skipped"
        text = f"{self.table}: {self.rows} rows"
        if self.missing_columns:
            text += f" | MISSING columns: {', '.join(self.missing_columns)}"
        if self.extra_columns:
            text += f" | unexpected columns: {', '.join(self.extra_columns)}"
        return text


def _tidy_column(name) -> str:
    return str(name).strip().lower().replace(" ", "_")


def read_workbook(path: Path, chama_id: str) -> tuple[dict[str, pd.DataFrame], list[SheetReport]]:
    """Read the expected sheets as text and report on their columns."""
    available = pd.ExcelFile(path).sheet_names
    frames: dict[str, pd.DataFrame] = {}
    reports: list[SheetReport] = []
    for table, sheet in sheet_names().items():
        report = SheetReport(table)
        reports.append(report)
        if sheet not in available:
            report.skipped = True
            continue
        df = pd.read_excel(path, sheet_name=sheet, dtype=str)
        df.columns = [_tidy_column(c) for c in df.columns]
        df = df.dropna(how="all")  # ignore completely empty rows

        expected = expected_columns(table)
        report.missing_columns = [c for c in expected if c not in df.columns]
        report.extra_columns = [c for c in df.columns if c not in expected]
        for col in report.missing_columns:  # keep every table's shape the same
            df[col] = None
        report.rows = len(df)

        df["chama_id"] = chama_id
        df["source_file"] = path.name
        df["source_row"] = [int(i) + 2 for i in df.index]  # the Excel row number
        df["loaded_at"] = datetime.now(timezone.utc)
        frames[table] = df
    return frames, reports


def load_to_raw(frames: dict[str, pd.DataFrame], engine, chama_id: str, source_file: str) -> None:
    """Replace this Chama's rows in raw.<table> and log the load."""
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, df in frames.items():
            exists = conn.execute(text("SELECT to_regclass(:t)"), {"t": f"raw.{table}"}).scalar()
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


def run(config: dict, engine) -> None:
    for chama in config["chamas"]:
        path = PROJECT_ROOT / chama["raw_file"]
        if not path.exists():
            print(f"[{chama['id']}] {path.name} not found - skipped")
            continue
        frames, reports = read_workbook(path, chama["id"])
        for r in reports:
            print(f"[{chama['id']}] {r.summary()}")
        if any(r.missing_columns for r in reports):
            print(f"[{chama['id']}] WARNING: missing columns were added as empty - check the Excel file")
        load_to_raw(frames, engine, chama["id"], path.name)
        print(f"[{chama['id']}] loaded into raw schema")
