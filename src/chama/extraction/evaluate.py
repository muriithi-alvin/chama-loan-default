"""Measure extraction against the hand-typed Excel files, cell by cell.

The typed files are the answer key: each typed row names the photo it was read
from. For each photo, the extracted rows are lined up with the typed rows by
member name; rows the model missed or added are counted, not compared. A cell
is right when it gives the pipeline the same value as the typed one: the same
text ignoring case and spaces, the same normalised name, or for amounts the
same number ("40,000" and "40000"). Free-text columns (remarks, notes,
headings, host, next meeting) are not scored.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from chama.anonymisation.pseudonymise import normalise_name
from chama.extraction.checks import Flag, parse_amount

SCORED_COLUMNS = {
    "meetings": ["meeting_date", "contribution_total", "brought_forward", "total_collection",
                 "cash", "banked"],
    "statements": ["meeting_date", "line_no", "member_name", "monthly", "loan_before",
                   "repayment", "interest", "loan_after", "due", "loan_type"],
    "new_loans": ["loan_date", "member_name", "amount", "loan_type"],
}
AMOUNT_COLUMNS = {"monthly", "loan_before", "repayment", "interest", "loan_after", "amount",
                  "contribution_total", "brought_forward", "total_collection", "cash", "banked"}
NAME_COLUMNS = {"member_name"}


def _as_str(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _text(value) -> str:
    return re.sub(r"\s+", "", _as_str(value).lower())


def same_value(column: str, expected, got) -> bool:
    if _text(expected) == _text(got):
        return True
    if column in NAME_COLUMNS:
        return normalise_name(_as_str(expected)) == normalise_name(_as_str(got))
    if column in AMOUNT_COLUMNS:
        a, b = parse_amount(expected), parse_amount(got)
        return a is not None and a == b
    return False


def align(expected: list[str], got: list[str]) -> list[tuple[int | None, int | None]]:
    """Pairs of row positions (typed, extracted), matched on the key sequence;
    None where one side has a row the other lacks. Rows in a differing stretch
    are paired in order, so a misread name still has its cells compared."""
    pairs: list[tuple[int | None, int | None]] = []
    matcher = difflib.SequenceMatcher(a=expected, b=got, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        n = min(i2 - i1, j2 - j1) if tag in ("equal", "replace") else 0
        pairs += zip(range(i1, i1 + n), range(j1, j1 + n))
        pairs += [(i, None) for i in range(i1 + n, i2)]
        pairs += [(None, j) for j in range(j1 + n, j2)]
    return pairs


@dataclass
class PageScore:
    photo: str
    rows: Counter = field(default_factory=Counter)  # e.g. statements_expected, statements_missing
    cells: Counter = field(default_factory=Counter)  # per column: compared
    right: Counter = field(default_factory=Counter)  # per column: right
    flags: Counter = field(default_factory=Counter)  # wrong/right statement rows, flagged or not
    mismatches: list[dict] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        total = sum(self.cells.values())
        return sum(self.right.values()) / total if total else float("nan")


def _key(df: pd.DataFrame, table: str) -> list[str]:
    if table == "meetings":
        return ["page"] * len(df)
    return [normalise_name(n) if isinstance(n, str) else "" for n in df["member_name"]]


def score_page(photo: str, expected: dict[str, pd.DataFrame], got: dict[str, pd.DataFrame],
               flags: list[Flag]) -> PageScore:
    score = PageScore(photo)
    checked_rows = {f.row for f in flags if f.table == "statements" and f.severity == "check"}
    hinted_rows = {f.row for f in flags if f.table == "statements"}
    for table, columns in SCORED_COLUMNS.items():
        exp = expected.get(table, pd.DataFrame()).reset_index(drop=True)
        ext = got.get(table, pd.DataFrame()).reset_index(drop=True)
        score.rows[f"{table}_expected"] += len(exp)
        score.rows[f"{table}_extracted"] += len(ext)
        if exp.empty or ext.empty:
            score.rows[f"{table}_missing"] += len(exp)
            score.rows[f"{table}_extra"] += len(ext)
            continue
        for i, j in align(_key(exp, table), _key(ext, table)):
            if j is None:
                score.rows[f"{table}_missing"] += 1
                if table == "statements":
                    score.flags["missed_row"] += 1
                continue
            if i is None:
                score.rows[f"{table}_extra"] += 1
                continue
            wrong = False
            for column in columns:
                score.cells[column] += 1
                if same_value(column, exp.at[i, column], ext.at[j, column]):
                    score.right[column] += 1
                else:
                    wrong = True
                    score.mismatches.append({
                        "photo": photo, "table": table, "typed_row": i + 1, "column": column,
                        "typed": exp.at[i, column], "extracted": ext.at[j, column],
                    })
            if table == "statements":
                state = "wrong" if wrong else "right"
                score.flags[f"{state}_rows"] += 1
                score.flags[f"{state}_rows_checked"] += j in checked_rows
                score.flags[f"{state}_rows_flagged_any"] += j in hinted_rows
    return score


def summary_row(score: PageScore, extra: dict) -> dict:
    """One line of the evaluation table: counts only, no names."""
    amounts = [c for c in score.cells if c in AMOUNT_COLUMNS]
    return {
        "photo": score.photo, **extra,
        **{k: score.rows[k] for k in sorted(score.rows)},
        "cells": sum(score.cells.values()), "cells_right": sum(score.right.values()),
        "amount_cells": sum(score.cells[c] for c in amounts),
        "amount_right": sum(score.right[c] for c in amounts),
        "name_cells": score.cells["member_name"], "name_right": score.right["member_name"],
        **{k: score.flags[k] for k in sorted(score.flags)},
    }


def sample_photos(photos: list[str], n: int) -> list[str]:
    """n photos spread evenly through the ledger (first and last included),
    so every period's handwriting and layout is represented."""
    photos = sorted(photos)
    if n >= len(photos):
        return photos
    if n == 1:
        return photos[:1]
    return sorted({photos[round(k * (len(photos) - 1) / (n - 1))] for k in range(n)})
