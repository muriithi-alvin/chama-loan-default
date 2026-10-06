# Data dictionary — raw layer

The raw Excel files (`data/raw/<chama>/<year>.xlsx`) hold the ledger **exactly as
written**. This page describes every sheet and column, how ledger headings map
to columns, and the rules used when typing values in. The code definition is
`src/chama/ingestion/raw_format.py`.

## How the ledger is organised (Chama B)

One page per monthly meeting. Each page has:
1. A date at the top (from about 2016; early 2014 pages only give the *next*
   meeting's date at the bottom).
2. A table with one row per member who has a loan or pays a contribution.
3. A footer: contribution total, brought forward (B/F), total collection, cash
   and banked amounts, loans given that day, next meeting, and NB notes.

## Sheets

Every sheet ends with `source_photo` (the photo the row was read from) and
`unclear` (`Y` if any value in the row was hard to read). The loader adds
`chama_id`, `source_file`, `source_row` and `loaded_at`.

### Statements — one row per member line on a page
| Column | Meaning |
| --- | --- |
| `meeting_date` | Date at the top of the page, as written (blank if none) |
| `line_no` | Row number written in the ledger |
| `member_name` | Name as written |
| `monthly` | Monthly column as written: `350`, `SF`, `Emergency`, `paid Feb` |
| `loan_before` | Balance before the meeting |
| `repayment` | Amount repaid at the meeting |
| `interest` | Rate (`2%`) or amount (`2100`), as written |
| `loan_after` | Balance after the meeting |
| `due` | Month or date the loan is due |
| `remarks` | Other text in the row, crossed-out values |

### Meetings — one row per page
| Column | Meaning |
| --- | --- |
| `meeting_date` | Date at the top of the page |
| `host` | Venue or host, e.g. "@ <member>'s house" |
| `column_headers` | Table headings as written, separated by `\|` |
| `contribution_total` | "Monthly contribution" total |
| `brought_forward` | "B/F" amount |
| `total_collection` | "Total collection" |
| `cash` | "In cash" amount |
| `banked` | "To be banked" / "from the bank" amount |
| `next_meeting` | Next meeting date and host |
| `notes` | NB notes and other footer text |

### NewLoans — one row per loan given at the meeting
| Column | Meaning |
| --- | --- |
| `loan_date` | Date written beside the loans list, if any |
| `member_name` | Name as written |
| `amount` | Amount as written |
| `loan_type` | Blank for a normal loan; `SF` (school fees), `Emergency`, `top-up` as written |
| `remarks` | e.g. "30,000 cash, 30,000 bank" |

### Attendance — one row per member per meeting (from minutes, if available)
`meeting_date`, `member_name`, `status`, `remarks`.

## Ledger headings → columns

| Period (approx.) | Headings as written | Mapped to |
| --- | --- | --- |
| 2014–2015 | Bal · Repayment · Bal · Month due · % (from Sept 2014: Loan · Loan repayment · Loan balance · Month due) | loan_before · repayment · loan_after · due · interest |
| 2016–2017 | Loan · Repay · Bal · Due | loan_before · repayment · loan_after · due |
| 2018 | (loan) · (repayment) · (balance) · 350 | loan_before · repayment · loan_after · monthly |
| 2021 | Monthly · Loan due · Loan repayment · Loan balance | monthly · loan_before · repayment · loan_after |
| 2022 | Monthly · Current loan balance · Loan reduction · Interest · Balance | monthly · loan_before · repayment · interest · loan_after |
| 2025–2026 | Monthly payment · Loan due · Loan repayment · Interest paid · Loan balance | monthly · loan_before · repayment · interest · loan_after |

This table is updated as each year is extracted.

## Extraction rules

1. Type values **exactly as written**: keep commas, spaces, `/=`, `t`, `%` and
   spelling. Do not correct, total or convert anything.
2. A dash (`–`) or empty cell stays as written (`-`) or blank.
3. **Crossed-out values:** type the final (uncrossed) value; put the crossed-out
   one in `remarks`, e.g. `crossed out: 46,000`.
4. Values written above or beside a cell (e.g. `5500 + 776`) are typed as they
   appear.
5. Any value that is hard to read gets `unclear = Y`, with the doubt described
   in `remarks`, e.g. `amount could be 35,090 or 35,000`.
6. Footer lines that do not fit a column go to `Meetings.notes`, in the order
   they appear.
7. Rotated photos are read in their correct orientation; the photo file itself
   is never changed.

---

# Name review file — `data/interim/aliases_<chama>.csv`

Written by `python -m chama.pipeline suggest-aliases`, checked by a person, and
loaded with `load-aliases` into `private.member_aliases`. It holds real names,
so it stays in `data/interim` on this computer.

| Column | Meaning |
| --- | --- |
| `raw_name` | A spelling from the ledger, normalised (lower case, no dots or extra spaces) |
| `canonical_name` | The member this spelling belongs to. **The only column to edit.** |
| `status` | `check`: suggested as another spelling of `canonical_name` — confirm or correct. `new`: no close match, this is a member's own name. `reviewed`: loaded before. |
| `score` | How alike the spelling and the member's name are (0–1) |
| `similar_to` | For `new` rows: the closest other member and score, when they might be one person |
| `occurrences` | How many rows use this spelling |
| `first_photo` | First photo the spelling appears on, for checking against the page |

To merge two members, give their rows the same `canonical_name`. To split a
wrong match, type the right name in `canonical_name`.

# Staging layer — schema `staging`

Built by `python -m chama.pipeline anonymise`. Same tables as `raw`, with
`member_name` replaced by `member_code` (e.g. `M-3f9a1c2b`) and **no free text**
(decision D-008). Values are still text as written; the clean step gives them
types.

| Table | Columns kept from raw | Left in raw |
| --- | --- | --- |
| `statements` | `meeting_date`, `line_no`, `member_code`, `monthly`, `loan_before`, `repayment`, `interest`, `loan_after`, `due` | `remarks` |
| `meetings` | `meeting_date`, `column_headers`, `contribution_total`, `brought_forward`, `total_collection`, `cash`, `banked`, `next_meeting_date` (date only) | `host`, `notes`, `next_meeting` |
| `new_loans` | `loan_date`, `member_code`, `amount`, `loan_type` | `remarks` |
| `attendance` | `meeting_date`, `member_code`, `status` | `remarks` |

Every table also keeps `source_photo`, `unclear`, `chama_id`, `source_file` and
`source_row`, so each value can be traced to its photo.
