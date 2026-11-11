"""What the extraction model returns for one ledger photo.

The row models are built from chama.ingestion.raw_format, so extracted rows
have exactly the columns of the typed Excel files and every later step reads
them unchanged. Values are strings exactly as written ("" for an empty cell);
`unclear` is a yes/no that becomes 'Y' or blank, as in the typed files.
"""
from __future__ import annotations

import json

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


# Other names the free model sometimes gives these fields (D-035).
_ALIASES = {
    "meeting": {"meet_date": "meeting_date", "date": "meeting_date", "headings": "column_headers",
                "headers": "column_headers", "column_headings": "column_headers"},
    "statements": {"no": "line_no", "number": "line_no", "name": "member_name", "member": "member_name",
                   "type": "loan_type"},
    "new_loans": {"date": "loan_date", "name": "member_name", "member": "member_name", "type": "loan_type"},
}


def _repaired_row(row: dict, model: type[BaseModel], aliases: dict[str, str], spare: str) -> BaseModel:
    """A row under the layout's own names: a missing field is empty, and a value under
    a name not in the layout goes in `spare` (remarks or notes) for the reviewer to see."""
    fields = {name: "" for name in model.model_fields if name != "unclear"}
    extra = []
    for key, value in row.items():
        name = aliases.get(key.strip(), key.strip())
        text = "" if value is None else str(value).strip()
        if name == "unclear":
            continue
        if name in fields:
            fields[name] = fields[name] or text
        elif text:
            extra.append(f"{key.strip()}: {text}")
    if extra:
        fields[spare] = "; ".join(filter(None, [fields[spare], *extra]))
    return model(**fields, unclear=str(row.get("unclear")).strip().lower() in ("true", "y", "yes"))


def repaired_page(content: str) -> LedgerPage | None:
    """The free model reads a page well but does not always keep to the schema's field
    names ("meet_date", or "problem" left out). Its answer is put under the right names;
    a person still checks every row against the photo (D-035). None if it is not an
    answer about a page at all, or says it is a page but gives no member lines."""
    try:
        data = json.loads(content)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("is_ledger_page"), bool):
        return None

    def said(value) -> str:
        text = value.strip() if isinstance(value, str) else ""
        return "" if text.lower() in ("true", "false", "none", "null") else text

    spare = [said(v) for k, v in data.items() if k not in LedgerPage.model_fields and said(v)]
    problem = said(data.get("problem"))
    meeting = data.get("meeting") if isinstance(data.get("meeting"), dict) else {}

    def rows(table: str, model: type[BaseModel]) -> list[BaseModel]:
        found = data.get(table) if isinstance(data.get(table), list) else []
        return [_repaired_row(r, model, _ALIASES[table], "remarks") for r in found if isinstance(r, dict)]

    if not data["is_ledger_page"]:
        return LedgerPage(is_ledger_page=False, problem=problem or " ".join(spare), statements=[], new_loans=[],
                          meeting=_repaired_row({}, MeetingRow, {}, "notes"))
    statements = rows("statements", StatementRow)
    if not statements:
        return None
    row = _repaired_row(meeting, MeetingRow, _ALIASES["meeting"], "notes")
    row.notes = "; ".join(filter(None, [row.notes, *spare]))
    return LedgerPage(is_ledger_page=True, problem=problem, statements=statements,
                      new_loans=rows("new_loans", NewLoanRow), meeting=row)


def page_schema() -> dict:
    """LedgerPage's JSON schema written out in full, for APIs that do not follow
    $ref: each definition is copied in place, titles are dropped (fewer tokens)
    and every object is closed to extra keys."""
    schema = LedgerPage.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, list):
            return [inline(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = definitions[node["$ref"].split("/")[-1]]
            node = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        out = {k: inline(v) for k, v in node.items() if k != "title"}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out

    return inline(schema)


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
