"""Export the modelling table for training in Colab (decision D-016).

Only analytics.loan_features leaves this computer: member codes, loan types,
amounts, months and engineered features, with no names and no free text. Two
checks run before anything is written:

- every column must be on EXPORT_COLUMNS, so a column added to the dbt model
  is exported only once someone adds it here on purpose;
- no value may contain a word of a member's name (the same check as the
  anonymise step).

The file goes to <DRIVE_DIR>/data, DRIVE_DIR being the project folder on
Google Drive set in .env (synced by Drive for desktop), or to data/processed
when DRIVE_DIR is not set. A manifest
beside it records the rows, the label rule and the code version, so every
model trained on it can be traced back.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import PROJECT_ROOT, export_dir, shown_path

TABLE = "analytics.loan_features"
FILE_NAME = "loan_features.parquet"
MANIFEST_NAME = "loan_features_manifest.json"

# The columns of analytics.loan_features allowed to leave this computer.
EXPORT_COLUMNS = [
    "loan_id", "chama_id", "member_code", "issued_month", "issue_year", "issue_source",
    "loan_type", "amount", "is_rollover", "amount_vs_own_max", "amount_vs_chama_median",
    "months_in_records", "prior_loans", "prior_repaid", "prior_repaid_late",
    "prior_rolled_over", "recent_emergency_loans", "recent_school_fees_loans",
    "open_loans_at_issue", "outstanding_at_issue", "oldest_open_loan_months",
    "recent_balance_lines", "recent_missed_share", "recent_repayment_ratio",
    "recent_contribution_rate", "status", "defaulted", "in_training", "outcome_month",
]


def check_columns(df: pd.DataFrame) -> None:
    """Stop if the table has a column not cleared for export, or lacks one."""
    unexpected = [c for c in df.columns if c not in EXPORT_COLUMNS]
    missing = [c for c in EXPORT_COLUMNS if c not in df.columns]
    if unexpected:
        raise StepFailed(
            f"{TABLE} has columns not cleared for export: {', '.join(unexpected)}. "
            "If they hold no names or free text, add them to EXPORT_COLUMNS in "
            "src/chama/features/export.py. Nothing was written."
        )
    if missing:
        raise StepFailed(
            f"{TABLE} lacks {', '.join(missing)}. Run python -m chama.pipeline clean first."
        )


def check_no_names(df: pd.DataFrame, names) -> None:
    """Stop if any value contains a word of a member's name."""
    from chama.anonymisation.anonymise import find_names

    leaks = find_names({"loan_features": df}, names)
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


def write(df: pd.DataFrame, out_dir: Path, config: dict) -> tuple[Path, Path]:
    """Write the table as Parquet and its manifest; return both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / FILE_NAME
    manifest_path = out_dir / MANIFEST_NAME
    df.to_parquet(data_path, index=False)

    training = df[df["in_training"]]
    manifest = {
        "table": TABLE,
        "file": FILE_NAME,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(df),
        "training_rows": len(training),
        "defaults": int(training["defaulted"].sum()),
        "members": int(df["member_code"].nunique()),
        "issued_from": str(df["issued_month"].min()),
        "issued_to": str(df["issued_month"].max()),
        "default_statuses": config.get("default_statuses"),
        "history_months": config.get("history_months"),
        **code_version(),
        "columns": list(df.columns),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return data_path, manifest_path


def read_features(engine) -> pd.DataFrame:
    from sqlalchemy import text

    from chama.db import table_exists

    with engine.connect() as conn:
        if not table_exists(conn, TABLE):
            raise StepFailed(f"{TABLE} not found. Run python -m chama.pipeline clean first.")
        df = pd.read_sql(text(f"SELECT * FROM {TABLE} ORDER BY issued_month, loan_id"), conn)
    df["issued_month"] = pd.to_datetime(df["issued_month"])
    df["outcome_month"] = pd.to_datetime(df["outcome_month"])
    df["defaulted"] = df["defaulted"].astype("Int64")
    return df


def run(config: dict, engine, out_dir: Path | None = None) -> None:
    from chama.anonymisation.aliases import saved_aliases

    df = read_features(engine)
    check_columns(df)
    names = [n for a in saved_aliases(engine).values() for pair in a.items() for n in pair]
    check_no_names(df, names)

    data_path, manifest_path = write(df, out_dir or export_dir(), config)
    training = df[df["in_training"]]
    print(
        f"{len(df)} loans ({len(training)} with a known outcome, "
        f"{int(training['defaulted'].sum())} defaults) | name check: no names found"
    )
    print(f"Saved to {shown_path(data_path)} and {manifest_path.name}")
