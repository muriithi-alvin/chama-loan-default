"""The two modelling targets: their table, label, time column and features.

loan_default      one row per loan (loan_features): will this loan default?
missed_repayment  one row per member per meeting while a loan runs
                  (member_months): will a repayment be missed in the next
                  meetings? An early warning between loan requests (D-021).

Money is used only relative to something (the member's earlier loans, the
Chama's typical loan, the new loan), because loan sizes grew about six-fold
over the records (D-020). Not used: member codes (the model must judge
behaviour, not identity), years (a time trend would not carry forward) and
the outcome columns (known only later).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Target:
    name: str                                # key under modelling.targets in config
    table: str                               # exported table, <table>.parquet
    label: str                               # 1 = the event happened
    time: str                                # month used to split by time
    log_features: tuple[str, ...]            # skewed values, log-scaled
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    keys: tuple[str, ...]                    # kept beside each score, to trace it back

    @property
    def features(self) -> list[str]:
        return [*self.log_features, *self.numeric_features, *self.categorical_features]


LOAN_DEFAULT = Target(
    name="loan_default",
    table="loan_features",
    label="defaulted",
    time="issued_month",
    log_features=("outstanding_vs_amount",),
    numeric_features=(
        "amount_vs_own_max", "amount_vs_chama_median", "months_in_records",
        "prior_loans", "prior_repaid", "prior_repaid_late", "prior_rolled_over",
        "recent_emergency_loans", "recent_school_fees_loans", "open_loans_at_issue",
        "oldest_open_loan_months", "recent_balance_lines", "recent_missed_share",
        "recent_repayment_ratio", "recent_contribution_rate", "is_rollover",
    ),
    categorical_features=("loan_type",),
    keys=("loan_id", "member_code", "loan_type", "issued_month", "status"),
)

MISSED_REPAYMENT = Target(
    name="missed_repayment",
    table="member_months",
    label="missed_ahead",
    time="meeting_month",
    log_features=(),
    numeric_features=(
        "open_loans", "outstanding_vs_chama_median", "oldest_open_loan_months",
        "loan_started_this_meeting", "has_emergency_loan", "has_school_fees_loan",
        "months_in_records", "loans_so_far", "prior_rolled_over",
        "missed_last_3_meetings", "recent_missed", "recent_missed_share",
        "repayment_ratio_last_3_meetings", "months_since_last_miss",
        "recent_contribution_rate", "chama_missed_share", "month_of_year",
    ),
    categorical_features=(),
    keys=("member_month_id", "member_code", "page_no", "meeting_month"),
)

TARGETS = {t.name: t for t in (LOAN_DEFAULT, MISSED_REPAYMENT)}


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Features computed from exported columns."""
    if {"outstanding_at_issue", "amount"} <= set(df.columns):
        df = df.assign(
            outstanding_vs_amount=df["outstanding_at_issue"] / df["amount"].where(df["amount"] > 0)
        )
    return df


def load_table(path: Path, target: Target) -> pd.DataFrame:
    """Read an exported table and give the columns their types."""
    df = pd.read_parquet(path)
    for col in (target.time, "outcome_month"):
        df[col] = pd.to_datetime(df[col])
    df[target.label] = df[target.label].astype("Int64")
    df["in_training"] = df["in_training"].astype(bool)
    return add_derived(df)


def load_manifest(data_path: Path) -> dict:
    """The manifest written beside a table by the export step, if present."""
    path = Path(data_path).with_name(f"{Path(data_path).stem}_manifest.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def known_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose outcome is known: the ones models may learn from."""
    return df[df["in_training"]]


def xy(df: pd.DataFrame, target: Target) -> tuple[pd.DataFrame, pd.Series]:
    """Feature matrix and label (label empty where the outcome is unknown)."""
    X = df[target.features].copy()
    for col in [*target.log_features, *target.numeric_features]:
        X[col] = X[col].astype(float)
    return X, df[target.label]
