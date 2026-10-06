"""Data quality report: read analytics.quality_report, print it, save it as CSV.

The report holds counts only (no names or codes), one table per Chama with a
column per year.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from chama.config import PROJECT_ROOT

REPORT_FILE = PROJECT_ROOT / "data" / "processed" / "quality_report.csv"


def read_report(engine) -> pd.DataFrame:
    from sqlalchemy import text

    sql = text("SELECT * FROM analytics.quality_report ORDER BY chama_id, measure_order, year")
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def as_tables(report: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """One table per Chama: a row per measure, a column per year."""
    tables = {}
    for chama_id, rows in report.groupby("chama_id"):
        table = rows.pivot_table(
            index=["measure_order", "table_name", "measure"],
            columns="year",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        tables[chama_id] = table.droplevel("measure_order")
    return tables


def run(engine, path: Path = REPORT_FILE) -> None:
    report = read_report(engine)
    path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(path, index=False)
    for chama_id, table in as_tables(report).items():
        print(f"\n[{chama_id}] data quality")
        print(table.to_string())
    shown = path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path
    print(f"\nSaved to {shown}")
