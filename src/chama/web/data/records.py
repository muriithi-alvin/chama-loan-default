"""Queries on the chama's records (the analytics schema) and saved scores.

Every query takes the chama ID from the signed-in account (auth.py); none
takes it from an address. Results hold member codes only; names are added by
services/names.py just before a page gets them.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Loans still owed on: not cleared, not rolled into a bigger loan, not lost track of.
RUNNING = "('open', 'open_no_due_date', 'overdue')"


def _rows(conn: Connection, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def _row(conn: Connection, sql: str, **params) -> dict | None:
    row = conn.execute(text(sql), params).first()
    return dict(row._mapping) if row else None


def latest_meeting(conn: Connection, chama_id: str) -> dict | None:
    return _row(conn, """
        SELECT page_no, meeting_month, meeting_date, date_source, source_photo, source_file
        FROM analytics.meetings WHERE chama_id = :c ORDER BY page_no DESC LIMIT 1
    """, c=chama_id)


def latest_scored_page(conn: Connection, chama_id: str) -> int | None:
    return conn.execute(text("SELECT max(page_no) FROM app.risk_scores WHERE chama_id = :c"),
                        {"c": chama_id}).scalar()


def scores_at(conn: Connection, chama_id: str, page_no: int) -> list[dict]:
    """The newest score of each member for one meeting."""
    return _rows(conn, """
        SELECT DISTINCT ON (member_code) member_code, page_no, meeting_month, meeting_date, band,
               reasons, model_run_id, model_name, model_version, model_checksum, scored_at
        FROM app.risk_scores WHERE chama_id = :c AND page_no = :p
        ORDER BY member_code, scored_at DESC
    """, c=chama_id, p=page_no)


def previous_bands(conn: Connection, chama_id: str, page_no: int) -> dict[str, str]:
    """Each member's band at the last scored meeting before `page_no`."""
    rows = _rows(conn, """
        SELECT DISTINCT ON (member_code) member_code, band
        FROM app.risk_scores
        WHERE chama_id = :c
          AND page_no = (SELECT max(page_no) FROM app.risk_scores WHERE chama_id = :c AND page_no < :p)
        ORDER BY member_code, scored_at DESC
    """, c=chama_id, p=page_no)
    return {r["member_code"]: r["band"] for r in rows}


def last_scored_at(conn: Connection, chama_id: str):
    return conn.execute(text("SELECT max(scored_at) FROM app.risk_scores WHERE chama_id = :c"),
                        {"c": chama_id}).scalar()


def member_codes(conn: Connection, chama_id: str) -> list[str]:
    return [r[0] for r in conn.execute(
        text("SELECT member_code FROM private.member_codes WHERE chama_id = :c ORDER BY member_code"),
        {"c": chama_id})]


def is_member_of(conn: Connection, chama_id: str, code: str) -> bool:
    return conn.execute(
        text("SELECT 1 FROM private.member_codes WHERE chama_id = :c AND member_code = :m"),
        {"c": chama_id, "m": code}).first() is not None


def running_loans(conn: Connection, chama_id: str) -> list[dict]:
    """Loans still owed on, one row each, with the balance last recorded."""
    return _rows(conn, f"""
        SELECT loan_id, member_code, loan_type, issued_month, due_month, last_balance, status
        FROM analytics.loans
        WHERE chama_id = :c AND status IN {RUNNING} AND coalesce(last_balance, 0) > 0
    """, c=chama_id)


def missed_at_meeting(conn: Connection, chama_id: str, page_no: int) -> dict:
    """Running loans at a meeting, and how many got no repayment."""
    return _row(conn, """
        SELECT count(*) AS running,
               count(*) FILTER (WHERE coalesce(repayment, 0) = 0) AS missed
        FROM analytics.loan_lines
        WHERE chama_id = :c AND page_no = :p AND loan_id IS NOT NULL
          AND line_kind = 'balance' AND opening_balance > 0
    """, c=chama_id, p=page_no) or {"running": 0, "missed": 0}


def member_months_at(conn: Connection, chama_id: str, page_no: int) -> dict[str, dict]:
    rows = _rows(conn, """
        SELECT member_code, open_loans, missed_last_3_meetings
        FROM analytics.member_months WHERE chama_id = :c AND page_no = :p
    """, c=chama_id, p=page_no)
    return {r["member_code"]: r for r in rows}


# ---- One member ---------------------------------------------------------------


def member_loans(conn: Connection, chama_id: str, code: str) -> list[dict]:
    return _rows(conn, f"""
        SELECT l.loan_id, l.loan_type, l.issued_month, l.due_month, l.status, l.cleared_month,
               l.amount_given, l.last_balance, l.status IN {RUNNING} AND coalesce(l.last_balance, 0) > 0
                   AS running,
               rolled.issued_month AS rolled_into_month
        FROM analytics.loans l
        LEFT JOIN analytics.loans rolled ON rolled.loan_id = l.rolled_into_loan_id
        WHERE l.chama_id = :c AND l.member_code = :m
        ORDER BY l.issued_month DESC NULLS LAST, l.loan_id DESC
    """, c=chama_id, m=code)


def member_lines(conn: Connection, chama_id: str, code: str, meetings: int = 12) -> list[dict]:
    """The member's loan lines at their last `meetings` meetings with a line."""
    return _rows(conn, """
        WITH pages AS (
            SELECT DISTINCT page_no FROM analytics.loan_lines
            WHERE chama_id = :c AND member_code = :m AND loan_id IS NOT NULL
            ORDER BY page_no DESC LIMIT :n
        )
        SELECT ll.page_no, ll.meeting_month, mt.meeting_date, ll.loan_type, ll.line_kind,
               ll.opening_balance, ll.repayment, ll.interest_amount, ll.interest_rate_pct,
               ll.closing_balance, ll.closing_estimated
        FROM analytics.loan_lines ll
        JOIN pages USING (page_no)
        LEFT JOIN analytics.meetings mt ON mt.chama_id = ll.chama_id AND mt.page_no = ll.page_no
        WHERE ll.chama_id = :c AND ll.member_code = :m AND ll.loan_id IS NOT NULL
        ORDER BY ll.page_no DESC, ll.source_row
    """, c=chama_id, m=code, n=meetings)


def member_contributions(conn: Connection, chama_id: str, code: str, meetings: int = 12) -> list[dict]:
    """The member's monthly contribution at the chama's last `meetings` meetings
    that recorded contributions (none recorded before 2017)."""
    return _rows(conn, """
        WITH pages AS (
            SELECT page_no, meeting_month FROM analytics.statements
            WHERE chama_id = :c GROUP BY page_no, meeting_month
            HAVING bool_or(monthly_amount > 0)
            ORDER BY page_no DESC LIMIT :n
        )
        SELECT pages.page_no, pages.meeting_month,
               max(s.monthly_amount) AS amount, count(s.line_id) > 0 AS on_page
        FROM pages
        LEFT JOIN analytics.statements s
            ON s.chama_id = :c AND s.page_no = pages.page_no AND s.member_code = :m
        GROUP BY pages.page_no, pages.meeting_month
        ORDER BY pages.page_no
    """, c=chama_id, m=code, n=meetings)


def member_first_month(conn: Connection, chama_id: str, code: str):
    return conn.execute(text(
        "SELECT min(meeting_month) FROM analytics.statements WHERE chama_id = :c AND member_code = :m"),
        {"c": chama_id, "m": code}).scalar()


# ---- Meetings (OFF-5, OFF-6) ------------------------------------------------------


def meetings_list(conn: Connection, chama_id: str) -> list[dict]:
    return _rows(conn, """
        WITH lines AS (
            SELECT page_no, count(*) AS lines FROM analytics.statements WHERE chama_id = :c GROUP BY page_no
        ), loans AS (
            SELECT page_no, count(*) AS new_loans FROM analytics.new_loans WHERE chama_id = :c GROUP BY page_no
        )
        SELECT m.page_no, m.meeting_month, m.meeting_date, m.date_source, m.contribution_total,
               m.total_collection, m.source_file, m.issues IS NOT NULL AS has_issues,
               coalesce(lines.lines, 0) AS lines, coalesce(loans.new_loans, 0) AS new_loans
        FROM analytics.meetings m
        LEFT JOIN lines USING (page_no)
        LEFT JOIN loans USING (page_no)
        WHERE m.chama_id = :c
        ORDER BY m.page_no DESC
    """, c=chama_id)


def meeting(conn: Connection, chama_id: str, page_no: int) -> dict | None:
    return _row(conn, """
        SELECT page_no, meeting_month, meeting_date, date_source, contribution_total, brought_forward,
               total_collection, cash, banked, column_headers, unclear, issues, source_photo, source_file
        FROM analytics.meetings WHERE chama_id = :c AND page_no = :p
    """, c=chama_id, p=page_no)


def meeting_lines(conn: Connection, chama_id: str, page_no: int) -> list[dict]:
    return _rows(conn, """
        SELECT line_on_page, line_no, member_code, line_kind, loan_type, monthly_amount, monthly_note,
               loan_before, repayment, interest_rate_pct, interest_amount, loan_after, closing_balance,
               due_month, unclear, issues
        FROM analytics.statements WHERE chama_id = :c AND page_no = :p
        ORDER BY line_on_page
    """, c=chama_id, p=page_no)


def meeting_new_loans(conn: Connection, chama_id: str, page_no: int) -> list[dict]:
    return _rows(conn, """
        SELECT member_code, amount, loan_type, loan_month, unclear, issues
        FROM analytics.new_loans WHERE chama_id = :c AND page_no = :p
        ORDER BY line_id
    """, c=chama_id, p=page_no)


def neighbour_pages(conn: Connection, chama_id: str, page_no: int) -> dict:
    return _row(conn, """
        SELECT (SELECT max(page_no) FROM analytics.meetings WHERE chama_id = :c AND page_no < :p) AS previous,
               (SELECT min(page_no) FROM analytics.meetings WHERE chama_id = :c AND page_no > :p) AS next
    """, c=chama_id, p=page_no) or {"previous": None, "next": None}
