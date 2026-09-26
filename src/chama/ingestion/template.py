"""Builds the empty raw Excel template described in raw_format.py."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from chama.ingestion.raw_format import SHEETS, expected_columns

HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")


def build_template(path: Path) -> Path:
    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    readme.append(["Sheet", "Column", "What to enter"])
    for cell in readme[1]:
        cell.font = Font(bold=True)
    for table, (sheet, columns) in SHEETS.items():
        for col, desc in columns.items():
            readme.append([sheet, col, desc])
        readme.append([sheet, "source_photo", "Photo file this row was read from"])
        readme.append([sheet, "unclear", "Y if any value was hard to read, else blank"])
    readme.append([])
    readme.append(["Rule", "", "Type values exactly as written. Do not correct, total or reformat."])
    for col, width in zip("ABC", (16, 16, 70)):
        readme.column_dimensions[col].width = width

    for table, (sheet, _) in SHEETS.items():
        ws = wb.create_sheet(sheet)
        ws.append(expected_columns(table))
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL
        ws.freeze_panes = "A2"
        for i, _ in enumerate(expected_columns(table)):
            ws.column_dimensions[chr(65 + i)].width = 18

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path

