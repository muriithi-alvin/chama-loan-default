"""Step 1 - Ingestion: copy the raw Excel sheets into the `raw` schema unchanged.

Every value is kept as text, exactly as typed from the ledger photos."""
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

    from chama.db import add_missing_columns, table_exists

    with engine.begin() as conn:
        for table, df in frames.items():
            if table_exists(conn, f"raw.{table}"):
                add_missing_columns(conn, "raw", table, df.columns)
                conn.execute(text(f"DELETE FROM raw.{table} WHERE chama_id = :c"), {"c": chama_id})
            df.to_sql(table, conn, schema="raw", if_exists="append", index=False)
            conn.execute(
                text(
                    "INSERT INTO raw.load_log (chama_id, source_file, sheet, row_count) "
                    "VALUES (:c, :f, :s, :n)"
                ),
                {"c": chama_id, "f": source_file, "s": table, "n": len(df)},
            )


def raw_files(folder: Path) -> list[Path]:
    """Yearly Excel files in a Chama's folder, in name order, then the pages
    scanned and accepted in the web interface (scans/scan-<upload>.xlsx, D-027).

    Both are raw files, so reloading from files keeps the scanned pages too.
    Skips Excel's temporary '~$' files and the empty template.
    """
    if not folder.is_dir():
        return []

    def usable(p: Path) -> bool:
        return not p.name.startswith("~$") and p.stem != "raw_template"

    typed = sorted(p for p in folder.glob("*.xlsx") if usable(p))
    scanned = sorted(p for p in (folder / "scans").glob("scan-*.xlsx") if usable(p))
    return typed + scanned


def read_folder(folder: Path, chama_id: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Read every yearly file for one Chama and combine them table by table."""
    parts: dict[str, list[pd.DataFrame]] = {}
    messages: list[str] = []
    for path in raw_files(folder):
        frames, reports = read_workbook(path, chama_id)
        for r in reports:
            if not r.skipped:
                messages.append(f"{path.name} | {r.summary()}")
        for table, df in frames.items():
            parts.setdefault(table, []).append(df)
    combined = {t: pd.concat(dfs, ignore_index=True) for t, dfs in parts.items()}
    return combined, messages


def run(config: dict, engine) -> None:
    for chama in config["chamas"]:
        folder = PROJECT_ROOT / chama["raw_dir"]
        frames, messages = read_folder(folder, chama["id"])
        if not frames:
            print(f"[{chama['id']}] no Excel files in {chama['raw_dir']} - skipped")
            continue
        for m in messages:
            print(f"[{chama['id']}] {m}")
        if any("MISSING" in m for m in messages):
            print(f"[{chama['id']}] WARNING: missing columns were added as empty - check the files")
        load_to_raw(frames, engine, chama["id"], chama["raw_dir"])
        print(f"[{chama['id']}] loaded into raw schema")
