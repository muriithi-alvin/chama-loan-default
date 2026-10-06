"""The agreed layout of the raw Excel files extracted from the ledger photos.

This module is the single source of truth: the template generator, the
extraction and the loader all use these definitions.

Every sheet ends with two tracking columns:
  source_photo - the photo file the row was read from (e.g. chama_b_p001.jpg)
  unclear      - 'Y' if any value in the row was hard to read, otherwise blank
Values are typed exactly as written in the ledger (no cleaning).
"""
from __future__ import annotations

TRACKING_COLUMNS = ["source_photo", "unclear"]

# The ledger is kept as one statement per monthly meeting (one page per meeting).
# The raw layout mirrors that: a Meetings row per page, a Statements row per
# member line on the page, and a NewLoans row per loan given at the meeting.
# Pages are linked to each other by `source_photo`.
#
# Column headings in the ledger change over the years (e.g. "Bal / Repayment /
# Bal / Month due / %" in 2014, "Loan due / Loan repayment / Interest paid /
# Loan balance" in 2025). Values go into the column with the same meaning, and
# the headings as written are kept in Meetings.column_headers.
# See docs/data_dictionary.md for the full mapping.
#
# table name -> (sheet name, columns, short description of each column)
SHEETS: dict[str, tuple[str, dict[str, str]]] = {
    "statements": (
        "Statements",
        {
            "meeting_date": "Date written at the top of the page, if any",
            "line_no": "Row number written in the ledger, if any",
            "member_name": "Name exactly as written",
            "monthly": "Monthly contribution column as written (e.g. 350, SF, Emergency, 'paid Feb')",
            "loan_before": "Loan balance before this meeting (Bal / Loan / Loan due / Current loan balance)",
            "repayment": "Amount repaid (Repayment / Loan repayment / Loan reduction)",
            "interest": "Interest as written: a rate (2%) or an amount (2100)",
            "loan_after": "Loan balance after this meeting (Bal / Loan balance)",
            "due": "Month or date the loan is due, as written",
            "remarks": "Other text in the row, including crossed-out values",
        },
    ),
    "meetings": (
        "Meetings",
        {
            "meeting_date": "Date written at the top of the page, if any",
            "host": "Where or whose house the meeting was held, if written",
            "column_headers": "The table's column headings exactly as written, separated by |",
            "contribution_total": "Monthly contribution total, if written",
            "brought_forward": "B/F amount, if written",
            "total_collection": "Total collection, if written",
            "cash": "Amount collected in cash, if written",
            "banked": "Amount to be banked / from the bank, if written",
            "next_meeting": "Next meeting date and host, as written",
            "notes": "NB notes and any other text on the page",
        },
    ),
    "new_loans": (
        "NewLoans",
        {
            "loan_date": "Date written next to the loans list, if any",
            "member_name": "Name exactly as written",
            "amount": "Amount given, as written",
            "loan_type": "As written: normal (blank), SF / school fees, emergency, top-up",
            "remarks": "Other text, e.g. '30,000 cash, 30,000 bank'",
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
}


def sheet_names() -> dict[str, str]:
    """table name -> sheet name, e.g. {'loans': 'Loans', ...}."""
    return {table: sheet for table, (sheet, _) in SHEETS.items()}


def expected_columns(table: str) -> list[str]:
    """All columns for a table, including the tracking columns."""
    return list(SHEETS[table][1]) + TRACKING_COLUMNS
