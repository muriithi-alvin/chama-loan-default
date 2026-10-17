"""The modelling table: which columns are features, the label, and loading it."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# Features known when a loan is given (see transform/models/features/features.yml).
# Not used: member_code (the model must judge behaviour, not identity),
# issue_year (a time trend would not carry into the future), and status and
# outcome_month (known only after the loan was given).
LOG_FEATURES = ["amount", "outstanding_at_issue"]   # skewed amounts, log-scaled
NUMERIC_FEATURES = [
    "amount_vs_own_max", "amount_vs_chama_median", "months_in_records",
    "prior_loans", "prior_repaid", "prior_repaid_late", "prior_rolled_over",
    "recent_emergency_loans", "recent_school_fees_loans", "open_loans_at_issue",
    "oldest_open_loan_months", "recent_balance_lines", "recent_missed_share",
    "recent_repayment_ratio", "recent_contribution_rate", "is_rollover",
]
CATEGORICAL_FEATURES = ["loan_type"]
FEATURES = LOG_FEATURES + NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "defaulted"

# Columns kept beside each prediction, so results can be traced to a loan.
KEYS = ["loan_id", "member_code", "loan_type", "issued_month", "issue_year", "status"]


def load_features(path: Path) -> pd.DataFrame:
    """Read the exported table and give the columns their types."""
    df = pd.read_parquet(path)
    for col in ("issued_month", "outcome_month"):
        df[col] = pd.to_datetime(df[col])
    df[TARGET] = df[TARGET].astype("Int64")
    df["in_training"] = df["in_training"].astype(bool)
    return df


def load_manifest(data_path: Path) -> dict:
    """The manifest written beside the table by the export step, if present."""
    from chama.features.export import MANIFEST_NAME

    path = Path(data_path).with_name(MANIFEST_NAME)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def known_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Loans whose outcome is known: the ones models may learn from."""
    return df[df["in_training"]]


def xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Feature matrix and label (label empty for loans still open)."""
    X = df[FEATURES].copy()
    X["is_rollover"] = X["is_rollover"].astype(float)
    for col in LOG_FEATURES + NUMERIC_FEATURES:
        X[col] = X[col].astype(float)
    return X, df[TARGET]
