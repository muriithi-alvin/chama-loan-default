"""What the extraction model returns for one ledger photo.

The row models are built from chama.ingestion.raw_format, so extracted rows
have exactly the columns of the typed Excel files and every later step reads
them unchanged. Values are strings exactly as written ("" for an empty cell);
`unclear` is a yes/no that becomes 'Y' or blank, as in the typed files.
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field, create_model

from chama.ingestion.raw_format import SHEETS, expected_columns

# The sheets a ledger page fills. Attendance comes from meeting minutes, not
# the ledger: none of the typed pages has any.
PAGE_TABLES = ["meetings", "statements", "new_loans"]

UNCLEAR_HELP = (
    "True if any value in this row was hard to read; say which value and the "
    "other possible reading in remarks (notes for the meeting)"
)


def _row_model(table: str) -> type[BaseModel]:
    sheet, columns = SHEETS[table]
    fields = {name: (str, Field(description=help_text)) for name, help_text in columns.items()}
    fields["unclear"] = (bool, Field(description=UNCLEAR_HELP))
    return create_model(f"{sheet}Row", **fields)


MeetingRow = _row_model("meetings")
StatementRow = _row_model("statements")
NewLoanRow = _row_model("new_loans")


class LedgerPage(BaseModel):
    """One photo of one ledger page (one monthly meeting)."""

    is_ledger_page: bool = Field(
        description="False if the photo is not a page of this ledger, or is too blurred, "
        "dark or cut off to read"
    )
    problem: str = Field(
        description="Why the photo cannot be read, or what limits the reading "
        "(part of the page cut off, blur, glare); empty if none"
    )
    meeting: MeetingRow = Field(description="The date, column headings and footer of the page")
    statements: list[StatementRow] = Field(description="One row per member line, top to bottom")
    new_loans: list[NewLoanRow] = Field(description="One row per loan listed as given at this meeting")


def page_to_frames(page: LedgerPage, source_photo: str) -> dict[str, pd.DataFrame]:
    """The page as raw-layout tables: blank cells become None, `unclear` 'Y' or None,
    and every row carries the photo it was read from."""
    rows = {"meetings": [page.meeting], "statements": page.statements, "new_loans": page.new_loans}
    frames = {}
    for table in PAGE_TABLES:
        records = []
        for item in rows[table]:
            values = item.model_dump()
            unclear = values.pop("unclear")
            record = {name: (value.strip() or None) for name, value in values.items()}
            record["source_photo"] = source_photo
            record["unclear"] = "Y" if unclear else None
            records.append(record)
        frames[table] = pd.DataFrame(records, columns=expected_columns(table))
    return frames
