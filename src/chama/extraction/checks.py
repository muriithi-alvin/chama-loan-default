"""Checks on extracted rows, to point the reviewer at the lines to look at.

Each rule was tried on the hand-typed pages (1,619 statement lines with a
balance) before it was adopted, so its false-alarm rate on correct rows is
known:
- `marked_unclear`: the model said a value was hard to read.
- `unreadable_amount`: an amount that is not a number. Almost never on typed
  pages (6 of about 5,600 written amounts).
- `balance_jump`: the balance grew by more than one month's interest, the
  dbt test balance_after_is_plausible. 2 typed lines.
- `does_not_add_up`: before - repayment (+ interest) is not after, within 1%.
  A hint only: 13% of typed lines do not add up in the ledger itself.
A check comparing each balance with the last page's was tried and dropped: it
fired on 29% of typed lines, mostly where a loan was topped up between pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

# Columns that must hold an amount, per table.
AMOUNT_COLUMNS = {
    "statements": ["loan_before", "repayment", "loan_after"],
    "new_loans": ["amount"],
    "meetings": ["contribution_total", "brought_forward", "total_collection", "cash", "banked"],
}


@dataclass(frozen=True)
class Flag:
    table: str
    row: int  # position of the row in that table
    column: str | None
    rule: str
    severity: str  # "check": likely misread; "hint": often right, worth a glance
    message: str


def parse_amount(value) -> float | None:
    """The Python twin of the parse_amount dbt macro (transform/macros/parsing.sql),
    plus "Cleared", which the clean step also reads as 0."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    v = re.sub(r"^ksh\.?|/=|/-|,|\s", "", str(value).strip().lower())
    if v == "":
        return None
    if v in ("-", "–", "—", "=", "nil", "cleared"):
        return 0.0
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?k", v):
        return float(v[:-1]) * 1000
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?(\+[0-9]+(\.[0-9]+)?)*", v):
        return sum(float(part) for part in v.split("+"))
    return None


def interest_parts(value) -> tuple[float, float]:
    """(rate in %, amount): a value with % or a number up to 20 is a rate,
    a larger number an amount, as in the clean step."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0, 0.0
    text = str(value)
    percent = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text)
    if percent:
        return float(percent.group(1)), 0.0
    number = parse_amount(text)
    if number is None:
        return 0.0, 0.0
    return (number, 0.0) if number <= 20 else (0.0, number)


def _written(value) -> bool:
    return value is not None and not (isinstance(value, float) and pd.isna(value)) and str(value).strip() != ""


def check_page(frames: dict[str, pd.DataFrame]) -> list[Flag]:
    flags: list[Flag] = []
    for table, df in frames.items():
        for i, row in enumerate(df.to_dict("records")):
            if row.get("unclear") == "Y":
                note = row.get("remarks") if table != "meetings" else row.get("notes")
                flags.append(Flag(table, i, None, "marked_unclear", "check",
                                  f"Hard to read{': ' + note if _written(note) else ''}"))
            for column in AMOUNT_COLUMNS.get(table, []):
                if _written(row.get(column)) and parse_amount(row[column]) is None:
                    flags.append(Flag(table, i, column, "unreadable_amount", "check",
                                      f"{column} '{row[column]}' is not an amount"))
            if table == "statements":
                flags.extend(_balance_flags(i, row))
    return flags


def _balance_flags(i: int, row: dict) -> list[Flag]:
    before = parse_amount(row.get("loan_before"))
    after = parse_amount(row.get("loan_after"))
    if before is None or after is None or before <= 0:
        return []
    repaid = parse_amount(row.get("repayment")) or 0.0
    rate, interest = interest_parts(row.get("interest"))
    if after > before * (1 + max(rate, 5) / 100) * 1.01:
        return [Flag("statements", i, "loan_after", "balance_jump", "check",
                     f"Balance grew from {before:,.0f} to {after:,.0f} in one month")]
    tolerance = 0.01 * before
    readings = [before - repaid, before - repaid + interest, before * (1 + rate / 100) - repaid]
    if all(abs(reading - after) > tolerance for reading in readings):
        return [Flag("statements", i, "loan_after", "does_not_add_up", "hint",
                     f"{before:,.0f} - {repaid:,.0f} does not give {after:,.0f}")]
    return []
