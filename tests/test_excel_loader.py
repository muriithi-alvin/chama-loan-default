"""Loader tests using small fake workbooks. No real Chama data is used here."""
from openpyxl import Workbook, load_workbook

from chama.ingestion.excel_loader import read_workbook
from chama.ingestion.raw_format import SHEETS, expected_columns
from chama.ingestion.template import build_template


def make_workbook(path, loans_rows, loans_columns=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Loans"
    ws.append(loans_columns or expected_columns("loans"))
    for row in loans_rows:
        ws.append(row)
    wb.save(path)
    return path


def test_template_has_every_sheet_with_expected_headers(tmp_path):
    path = build_template(tmp_path / "template.xlsx")
    wb = load_workbook(path)
    for table, (sheet, _) in SHEETS.items():
        headers = [c.value for c in wb[sheet][1]]
        assert headers == expected_columns(table)


def test_empty_template_reads_with_no_problems(tmp_path):
    path = build_template(tmp_path / "template.xlsx")
    _, reports = read_workbook(path, "chama_test")
    assert all(r.rows == 0 and not r.missing_columns and not r.skipped for r in reports)


def test_values_are_kept_exactly_as_written(tmp_path):
    row = ["", "Test Member A", "01/02/15", "300,000/=", "10%", "", "", "p1.jpg", ""]
    path = make_workbook(tmp_path / "wb.xlsx", [row, ["", "Test Member B", "3.4.15", 50000, "", "", "", "p1.jpg", "Y"]])
    frames, _ = read_workbook(path, "chama_test")
    loans = frames["loans"]
    assert loans.loc[0, "amount"] == "300,000/="
    assert loans.loc[0, "date_issued"] == "01/02/15"
    assert loans.loc[1, "amount"] == "50000"  # a number cell still comes back as text
    assert loans.loc[1, "unclear"] == "Y"


def test_rows_keep_their_excel_row_number_and_chama(tmp_path):
    rows = [
        ["", "Test Member A", "01/02/15", "1000", "", "", "", "p1.jpg", ""],
        [None] * 9,  # an empty row in the middle is skipped
        ["", "Test Member B", "02/02/15", "2000", "", "", "", "p1.jpg", ""],
    ]
    frames, _ = read_workbook(make_workbook(tmp_path / "wb.xlsx", rows), "chama_test")
    loans = frames["loans"]
    assert list(loans["source_row"]) == [2, 4]
    assert set(loans["chama_id"]) == {"chama_test"}


def test_missing_sheets_are_skipped_and_reported(tmp_path):
    path = make_workbook(tmp_path / "wb.xlsx", [])
    frames, reports = read_workbook(path, "chama_test")
    skipped = {r.table for r in reports if r.skipped}
    assert skipped == {"repayments", "contributions", "attendance", "notes"}
    assert set(frames) == {"loans"}


def test_missing_and_extra_columns_are_reported(tmp_path):
    columns = ["member_name", "date_issued", "amount", "Witness"]  # no source_photo etc.
    path = make_workbook(tmp_path / "wb.xlsx", [["Test Member A", "01/02/15", "1000", "X"]], columns)
    frames, reports = read_workbook(path, "chama_test")
    loans_report = next(r for r in reports if r.table == "loans")
    assert "source_photo" in loans_report.missing_columns
    assert loans_report.extra_columns == ["witness"]
    assert "source_photo" in frames["loans"].columns  # added as empty so shapes match
