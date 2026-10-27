"""Export the modelling tables for training in Colab (decision D-016).

Only two tables leave this computer, analytics.loan_features and
analytics.member_months: member codes, loan types, amounts, months and
engineered features, with no names and no free text. Two checks run on each
before anything is written:

- every column must be on the table's column list below, so a column added to
  a dbt model is exported only once someone adds it here on purpose;
- no value may contain a word of a member's name (the same check as the
  anonymise step).

The files go to <DRIVE_DIR>/data, DRIVE_DIR being the project folder on
Google Drive set in .env (synced by Drive for desktop), or to data/processed
when DRIVE_DIR is not set. A manifest beside each records the rows, the label
rule and the code version, so every model trained on it can be traced back.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import PROJECT_ROOT, export_dir, shown_path


@dataclass(frozen=True)
class ExportTable:
    name: str                  # analytics.<name>, written as <name>.parquet
    label: str                 # 1 = the event happened
    time: str                  # the row's month
    order_by: str
    columns: tuple[str, ...]   # the columns allowed to leave this computer

    @property
    def file_name(self) -> str:
        return f"{self.name}.parquet"

    @property
    def manifest_name(self) -> str:
        return f"{self.name}_manifest.json"


TABLES = {
    t.name: t
    for t in (
        ExportTable(
            name="loan_features",
            label="defaulted",
            time="issued_month",
            order_by="issued_month, loan_id",
            columns=(
                "loan_id", "chama_id", "member_code", "issued_month", "issue_year",
                "issue_source", "loan_type", "amount", "is_rollover", "amount_vs_own_max",
                "amount_vs_chama_median", "months_in_records", "prior_loans", "prior_repaid",
                "prior_repaid_late", "prior_rolled_over", "recent_emergency_loans",
                "recent_school_fees_loans", "open_loans_at_issue", "outstanding_at_issue",
                "oldest_open_loan_months", "recent_balance_lines", "recent_missed_share",
                "recent_repayment_ratio", "recent_contribution_rate", "status", "defaulted",
                "in_training", "outcome_month",
            ),
        ),
        ExportTable(
            name="member_months",
            label="missed_ahead",
            time="meeting_month",
            order_by="meeting_month, member_month_id",
            columns=(
                "member_month_id", "chama_id", "member_code", "page_no", "meeting_month",
                "meeting_year", "month_of_year", "open_loans", "outstanding_vs_chama_median",
                "oldest_open_loan_months", "loan_started_this_meeting", "has_emergency_loan",
                "has_school_fees_loan", "months_in_records", "loans_so_far",
                "prior_rolled_over", "missed_last_3_meetings", "recent_missed",
                "recent_missed_share", "repayment_ratio_last_3_meetings",
                "months_since_last_miss", "recent_contribution_rate", "chama_missed_share",
                "missed_ahead", "in_training", "outcome_month",
            ),
        ),
    )
}


def check_columns(df: pd.DataFrame, table: ExportTable) -> None:
    """Stop if the table has a column not cleared for export, or lacks one."""
    unexpected = [c for c in df.columns if c not in table.columns]
    missing = [c for c in table.columns if c not in df.columns]
    if unexpected:
        raise StepFailed(
            f"analytics.{table.name} has columns not cleared for export: "
            f"{', '.join(unexpected)}. If they hold no names or free text, add them to "
            "TABLES in src/chama/features/export.py. Nothing was written."
        )
    if missing:
        raise StepFailed(
            f"analytics.{table.name} lacks {', '.join(missing)}. "
            "Run python -m chama.pipeline clean first."
        )


def check_no_names(df: pd.DataFrame, names, table_name: str = "table") -> None:
    """Stop if any value contains a word of a member's name."""
    from chama.anonymisation.anonymise import find_names

    leaks = find_names({table_name: df}, names)
    if leaks:
        detail = ", ".join(f"{col} ({n} values)" for col, n in leaks.items())
        raise StepFailed(f"Member names found in {detail}. Nothing was written.")


def code_version() -> dict:
    """The git commit the export was made from, and whether files had changed."""
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {"git_commit": git("rev-parse", "--short", "HEAD"),
                "uncommitted_changes": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": None, "uncommitted_changes": None}


def write(df: pd.DataFrame, out_dir: Path, config: dict,
          table: ExportTable) -> tuple[Path, Path]:
    """Write a table as Parquet and its manifest; return both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / table.file_name
    manifest_path = out_dir / table.manifest_name
    df.to_parquet(data_path, index=False)

    training = df[df["in_training"]]
    manifest = {
        "table": f"analytics.{table.name}",
        "file": table.file_name,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(df),
        "training_rows": len(training),
        "label": table.label,
        "events": int(training[table.label].sum()),
        "members": int(df["member_code"].nunique()),
        "from": str(df[table.time].min()),
        "to": str(df[table.time].max()),
        "default_statuses": config.get("default_statuses"),
        "history_months": config.get("history_months"),
        "warning_horizon_meetings": config.get("warning_horizon_meetings"),
        **code_version(),
        "columns": list(df.columns),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return data_path, manifest_path


def read_table(engine, table: ExportTable, skip_chamas: tuple[str, ...] = ()) -> pd.DataFrame:
    """The table, without the chamas in `skip_chamas` (the demo copies, D-028:
    training on them would count chama B's rows twice)."""
    from sqlalchemy import bindparam, text

    from chama.db import table_exists

    with engine.connect() as conn:
        if not table_exists(conn, f"analytics.{table.name}"):
            raise StepFailed(
                f"analytics.{table.name} not found. Run python -m chama.pipeline clean first."
            )
        sql = text(
            f"SELECT * FROM analytics.{table.name} "
            "WHERE NOT (chama_id IN :skip) "
            f"ORDER BY {table.order_by}"
        ).bindparams(bindparam("skip", expanding=True))
        df = pd.read_sql(sql, conn, params={"skip": list(skip_chamas) or ["-"]})
    for col in (table.time, "outcome_month"):
        df[col] = pd.to_datetime(df[col])
    df[table.label] = df[table.label].astype("Int64")
    return df


def run(config: dict, engine, out_dir: Path | None = None) -> None:
    from chama.anonymisation.aliases import saved_aliases

    names = [n for a in saved_aliases(engine).values() for pair in a.items() for n in pair]
    demo = tuple(c["id"] for c in config["chamas"] if c.get("demo"))
    frames = {}
    for table in TABLES.values():   # check every table before writing any
        df = read_table(engine, table, skip_chamas=demo)
        check_columns(df, table)
        check_no_names(df, names, table.name)
        frames[table.name] = df

    out_dir = out_dir or export_dir()
    for table in TABLES.values():
        df = frames[table.name]
        data_path, manifest_path = write(df, out_dir, config, table)
        training = df[df["in_training"]]
        print(
            f"{table.name}: {len(df)} rows, {len(training)} with a known outcome, "
            f"{int(training[table.label].sum())} with {table.label} = 1"
        )
        print(f"  saved to {shown_path(data_path)} and {manifest_path.name}")
    print("name check: no names found")
