
"""The agreed layout of the raw Excel files extracted from the ledger photos.

This module is the single source of truth: the template generator, the
extraction and the loader all use these definitions.

Every sheet ends with two tracking columns:
  source_photo - the photo file the row was read from (e.g. 2015_page03.jpg)
  unclear      - 'Y' if any value in the row was hard to read, otherwise blank
Values are typed exactly as written in the ledger (no cleaning).
"""
from __future__ import annotations

TRACKING_COLUMNS = ["source_photo", "unclear"]

# table name -> (sheet name, columns, short description of each column)
SHEETS: dict[str, tuple[str, dict[str, str]]] = {
    "loans": (
        "Loans",
        {
            "loan_ref": "Loan number if the ledger has one, otherwise blank",
            "member_name": "Name exactly as written",
            "date_issued": "Date the loan was given, as written",
            "amount": "Amount borrowed, as written (e.g. 300,000 or 300000/=)",
            "interest": "Interest amount or rate, if recorded",
            "due_date": "Due date, if recorded",
            "remarks": "Any other text in the row",
        },
    ),
    "repayments": (
        "Repayments",
        {
            "loan_ref": "Loan number if shown, otherwise blank",
            "member_name": "Name exactly as written",
            "date_paid": "Date of payment, as written",
            "amount_paid": "Amount paid, as written",
            "balance": "Remaining balance, if recorded",
            "remarks": "Any other text in the row",
        },
    ),
    "contributions": (
        "Contributions",
        {
            "member_name": "Name exactly as written",
            "date": "Date of contribution, as written",
            "amount": "Amount contributed, as written",
            "remarks": "Any other text in the row",
        },
    ),
    "attendance": (
        "Attendance",
        {
            "meeting_date": "Date of the meeting, as written in the minutes",
            "member_name": "Name exactly as written",
            "status": "As written: present / absent / apology / late, etc.",
            "remarks": "Any other text, e.g. reason for absence",
        },
    ),
    "notes": (
        "Notes",
        {
            "note": "Anything unusual on the page: crossings-out, corrections, rule changes",
        },
    ),
}


def sheet_names() -> dict[str, str]:
    """table name -> sheet name, e.g. {'loans': 'Loans', ...}."""
    return {table: sheet for table, (sheet, _) in SHEETS.items()}


def expected_columns(table: str) -> list[str]:
    """All columns for a table, including the tracking columns."""
    return list(SHEETS[table][1]) + TRACKING_COLUMNS
