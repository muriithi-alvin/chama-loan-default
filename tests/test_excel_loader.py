"""Loader tests using small fake workbooks. No real Chama data is used here."""
from openpyxl import Workbook, load_workbook

from chama.ingestion.excel_loader import read_folder, read_workbook
from chama.ingestion.raw_format import SHEETS, expected_columns
from chama.ingestion.template import build_template

# meeting_date, line_no, member_name, monthly, loan_before, repayment, interest,
# loan_after, due, remarks, loan_type, source_photo, unclear
ROW_A = ["", "1", "Test Member A", "350", "23,475", "5000", "2%", "18,815", "Jan 2014", "", "", "p001.jpg", ""]
ROW_B = ["", "2", "Test Member B", "SF", 40000, "5 350", "1%", "35000", "Nov 2014", "", "Em", "p001.jpg", "Y"]


def make_workbook(path, rows, columns=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Statements"
    ws.append(columns or expected_columns("statements"))
    for row in rows:
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
    frames, _ = read_workbook(make_workbook(tmp_path / "wb.xlsx", [ROW_A, ROW_B]), "chama_test")
    st = frames["statements"]
    assert st.loc[0, "loan_before"] == "23,475"
    assert st.loc[0, "interest"] == "2%"
    assert st.loc[1, "loan_before"] == "40000"  # a number cell still comes back as text
    assert st.loc[1, "repayment"] == "5 350"
    assert st.loc[1, "monthly"] == "SF"
    assert st.loc[1, "unclear"] == "Y"
    assert st.loc[1, "loan_type"] == "Em"


def test_rows_keep_their_excel_row_number_and_chama(tmp_path):
    rows = [ROW_A, [None] * 13, ROW_B]  # an empty row in the middle is skipped
    frames, _ = read_workbook(make_workbook(tmp_path / "wb.xlsx", rows), "chama_test")
    st = frames["statements"]
    assert list(st["source_row"]) == [2, 4]
    assert set(st["chama_id"]) == {"chama_test"}


def test_missing_sheets_are_skipped_and_reported(tmp_path):
    frames, reports = read_workbook(make_workbook(tmp_path / "wb.xlsx", []), "chama_test")
    skipped = {r.table for r in reports if r.skipped}
    assert skipped == {"meetings", "new_loans", "attendance"}
    assert set(frames) == {"statements"}


def test_missing_and_extra_columns_are_reported(tmp_path):
    columns = ["member_name", "loan_before", "repayment", "Witness"]  # no source_photo etc.
    path = make_workbook(tmp_path / "wb.xlsx", [["Test Member A", "1000", "100", "X"]], columns)
    frames, reports = read_workbook(path, "chama_test")
    report = next(r for r in reports if r.table == "statements")
    assert "source_photo" in report.missing_columns
    assert report.extra_columns == ["witness"]
    assert "source_photo" in frames["statements"].columns  # added as empty so shapes match


def test_folder_of_yearly_files_is_combined(tmp_path):
    folder = tmp_path / "chama_test"
    folder.mkdir()
    make_workbook(folder / "2014.xlsx", [ROW_A])
    make_workbook(folder / "2015.xlsx", [ROW_B])
    build_template(folder / "raw_template.xlsx")  # must be ignored
    frames, messages = read_folder(folder, "chama_test")
    assert list(frames["statements"]["source_file"]) == ["2014.xlsx", "2015.xlsx"]
    assert len(messages) == 2


def test_missing_folder_gives_nothing(tmp_path):
    frames, messages = read_folder(tmp_path / "nope", "chama_test")
    assert frames == {} and messages == []
