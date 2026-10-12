# Milestone 1 report — the data pipeline

*Chama Loan Default Prediction · report date 12 October 2026 · branch `m1-data-pipeline`*

This report describes everything built and decided in Milestone 1 (M1): the
data source, the pipeline that turns a handwritten Chama ledger into clean,
anonymised, checked data, the technology and design decisions behind it, the
results on the full ledger (January 2014 – April 2026), the findings that
matter for modelling, the commands to run it, what remains to close the
milestone, and an introduction to Milestone 2.

It contains no member names. Detailed references: [decisions.md](decisions.md)
(every design decision), [data_dictionary.md](data_dictionary.md) (every
column and extraction rule), [extraction_log.md](extraction_log.md) (what was
extracted each year and what to check against the paper),
[git_workflow.md](git_workflow.md) and the [CHANGELOG](../CHANGELOG.md).

## Contents

1. [Summary](#1-summary)
2. [Background and objectives](#2-background-and-objectives)
3. [The data source: the Chama B ledger](#3-the-data-source-the-chama-b-ledger)
4. [Architecture](#4-architecture)
5. [How each step works](#5-how-each-step-works)
6. [Technology stack](#6-technology-stack)
7. [Design decisions](#7-design-decisions)
8. [Data protection and ethics](#8-data-protection-and-ethics)
9. [Testing and quality assurance](#9-testing-and-quality-assurance)
10. [Results on the full ledger](#10-results-on-the-full-ledger)
11. [Findings for the Chama and for modelling](#11-findings-for-the-chama-and-for-modelling)
12. [Limitations](#12-limitations)
13. [Running the project](#13-running-the-project)
14. [What is left to close Milestone 1](#14-what-is-left-to-close-milestone-1)
15. [Why this milestone matters](#15-why-this-milestone-matters)
16. [Next: Milestone 2 — features and models](#16-next-milestone-2--features-and-models)
17. [Glossary](#17-glossary)

---

## 1. Summary

| | |
| --- | --- |
| **Goal of M1** | Turn the Chama's handwritten loan ledger into trustworthy, anonymised, analysis-ready data, with a repeatable pipeline |
| **Data captured** | The whole Chama B ledger: 149 photos, 148 monthly meetings (January 2014 – 5 April 2026), 1,799 member lines, 174 loans listed as given |
| **Pipeline** | Five steps run by one command, `python -m chama.pipeline all`: database set-up, ingest, name matching (with a human review), anonymisation, and cleaning, loan reconstruction and data checks with dbt |
| **Output** | The `analytics` schema in PostgreSQL: typed ledger tables, **263 loans** rebuilt from the ledger lines with their outcome, and a data quality report, holding member codes only and no names |
| **Loan outcomes** | 161 repaid on time, 70 repaid late, 15 rolled into a bigger loan, 6 overdue, 4 open, 7 lost track (by the 12-month rule; see section 11) |
| **Checks** | 45 Python tests, 34 dbt data tests and 3 dbt unit tests; the last full run passed with 2 warnings that point at known ledger inconsistencies |
| **Issues** | #5, #6, #8, #9, #10, #11, #12, #13 built. Open: the accuracy check against the paper (#7) and the review of the latest name spellings |

Figures in this report come from a full run of the pipeline with the name
matches suggested in the review file. They will move slightly once the name
review is confirmed (section 14).

---

## 2. Background and objectives

A **Chama** is a Kenyan savings and credit group: members meet monthly,
contribute savings, and lend to each other at interest. Officials decide on
each loan request. The project's aim is a decision-support tool that gives
officials a **risk score, a risk category and an explanation** for a loan
request. It does not approve or reject loans.

| Milestone | Focus |
| --- | --- |
| **M1** | **Data pipeline: ingest, anonymise, validate, clean** (this report) |
| M2 | Features and models (Logistic Regression, Random Forest, XGBoost, SHAP) |
| M3 | MLOps: MLflow tracking, Evidently monitoring, Docker |
| M4 | Dashboard for officials (Streamlit) |
| M5 | Report and defence |

**M1 objectives:**

1. Capture the paper records faithfully, with every value traceable to its photo.
2. Protect members' identities: names replaced by codes inside the pipeline.
3. Turn handwriting into typed, consistent data without hiding problems.
4. Rebuild each loan and its outcome, because the ledger has no loan numbers.
5. Check data quality automatically and report it.
6. Make the whole process repeatable with one command.

**Scope.** Chama B only. Chama A has no ledger data yet and is picked up
automatically when its files appear (decision D-014).

---

## 3. The data source: the Chama B ledger

### 3.1 What a page looks like

Each page is one monthly meeting. It has a table with a line per member (loan
balance before the meeting, repayment, interest, balance after, and in some
years the due month and the monthly contribution), followed by the loans given
that day, totals and notes. Members can hold several loans at once (normal,
emergency, school fees), each on its own line.

### 3.2 How the ledger changed over twelve years

| Period | What changes in the ledger |
| --- | --- |
| 2014 | Balance · repayment · balance · month due · interest rate (1–2% a month for normal loans, 5% for emergency loans). Some pages give only the *next* meeting's date. |
| 2015 | Due months written for every loan; the % column disappears mid-year; emergency loans marked "Em" beside the name; normal loans 60,000–80,000. |
| 2016 | Several pages dated by month only; from December a **monthly contribution** column (300 per member). Normal loans reach 100,000. |
| 2017 | Interest written as an **amount** in its own column for part of the year; emergency loans now run 2–3 months at 3%; a books review records total debt (540,400 in 2015, 677,940 in 2017). |
| 2018 | **Due months no longer written**; emergency lines marked "E"; contribution 350; normal loans up to 130,000. |
| 2019 | Pages without headings; payments after the meeting listed with their dates. |
| 2020 | From April, pages record contributions paid by cash (C) or bank (B) rather than meetings; first **school-fees loans**. |
| 2021 | School-fees loans become regular; normal loans 150,000–200,000; penalty payments; a new loan sometimes written only as the balance after. |
| 2022 | From July a separate **Interest** column, with the repayment column holding principal only ("loan reduction"). |
| 2023–2024 | Interest column throughout; loans up to 350,000; at the annual meeting of 1 May 2024 each member received a 10,000 dividend. |
| 2025–2026 | Large loans "topped up" in instalments; prepaid contributions noted; the last page photographed is 5 April 2026. |

These changes are why the raw layout mirrors the ledger and every
interpretation happens later, in tested code (decision D-006).

### 3.3 From photos to Excel

The 149 photos were renamed in ledger order (`chama_b_p001.jpg` …
`chama_b_p149.jpg`) with a manifest linking each to its original file
(decision D-005). One photo (p048, December 2017) is blurred; the same page was
photographed again later (p051), and December 2017 was typed from the retake
(extraction rule 13). One ledger page was photographed twice in halves (p068
and p069).

Each year was typed into an Excel workbook (`data/raw/chama_b/<year>.xlsx`,
decision D-004) with four sheets mirroring the ledger: **Statements**,
**Meetings**, **NewLoans** and **Attendance**. Transcription was AI-assisted
(the photos were read and typed with Claude), year by year, under 19 written
extraction rules ([data_dictionary.md](data_dictionary.md)). The main ones:

- Type values **exactly as written**, with commas, `/=`, `%` and spelling.
  Nothing is corrected, totalled or converted.
- Crossed-out values go in `remarks`. A doubtful value gets `unclear = Y`, with
  the doubt and any other reading in `remarks`.
- Loan type marks (`Em`, `E`, `SF`, `school fee`) go in their own column
  (D-013). Notes such as "Cleared" or "paid by bank" are kept, not interpreted.

After each year the full pipeline was run to catch reading mistakes through
balance continuity. Every page's open questions are listed in the extraction
log for the check against the paper.

---

## 4. Architecture

```mermaid
flowchart LR
    L[Paper ledger] --> P[149 photos<br/>data/photos]
    P --> X[13 yearly workbooks<br/>data/raw, as written]
    X -->|1. ingest| RAW[(raw<br/>real names)]
    RAW -->|2. suggest-aliases| REV[Name review file<br/>checked by a person]
    REV -->|load-aliases| PRIV[(private<br/>name → code)]
    RAW -->|3. anonymise| STG[(staging<br/>codes only)]
    PRIV -.-> STG
    STG -->|4. clean · dbt| AN[(analytics<br/>clean tables, loans,<br/>quality report)]
    AN --> M2[Milestone 2:<br/>features and models]
```

**Four database layers** (decision D-002), in PostgreSQL:

| Layer | Holds | Who may see it |
| --- | --- | --- |
| `raw` | The workbooks as typed: text, real names, free-text notes | This computer only |
| `private` | The reviewed name spellings and the name-to-code link | This computer only, restricted |
| `staging` | Structured columns with member codes; no names, no free text | Pipeline and analysis |
| `analytics` | Typed tables, loans and the quality report; codes only | Models, MLflow, dashboard |

**One command** runs it all: `python -m chama.pipeline all` (decision D-011).

| Step | Command | What it does | Code |
| --- | --- | --- | --- |
| 0 | (part of `all`) | Creates the schemas and private tables if missing | `sql/01_schemas.sql`, `db.py` |
| 1 | `ingest` | Loads every yearly workbook into `raw`, as text, and reports missing or unexpected columns | `src/chama/ingestion/` |
| 2 | `suggest-aliases`, `load-aliases` | Groups the spellings of each member for a person to review; loads the reviewed list | `src/chama/anonymisation/aliases.py` |
| 3 | `anonymise` | Copies `raw` to `staging` with member codes, leaves free text behind, checks no name remains | `src/chama/anonymisation/anonymise.py` |
| 4 | `clean` | Runs the dbt project: typed tables, loans, data tests, quality report | `transform/`, `src/chama/cleaning/`, `src/chama/validation/` |

---

## 5. How each step works

### 5.1 Ingest (issues #5, #6)

The sheet layout is defined once (`raw_format.py`) and used by the Excel
template, the loader and the checks. The loader reads every value as **text**,
skips empty rows, records the source file, Excel row and photo for each row,
and reports missing or unexpected columns before loading. Each run replaces
that Chama's rows, so it can be repeated safely. When the layout gains a column
(for example `loan_type`), existing tables are extended automatically.

### 5.2 Name matching (issue #8)

The ledger writes the same person in different ways across twelve years:
initials, swapped order, a misspelled or shortened name, a surname that changes.
Each spelling is normalised (lower case, no punctuation) and scored against
the others. The score allows for initials, swapped order, spelling slips and a
missing name. Spellings scoring at least 0.85 are suggested as one member, and
the fullest spelling becomes the member's name.

The suggestions go to a **review file** (`data/interim/aliases_<chama>.csv`)
with a status (`check`, `new`, `reviewed`), the score, and `similar_to` for new
names close to an existing member. A person confirms or corrects the file and
runs `load-aliases`. Nothing is merged without that review. Loaded rows are
marked `reviewed`, so the file is the lasting record and can rebuild an empty
database (D-011).

Balance continuity is strong evidence in the review: when one spelling's
balance carries straight on from another's, they are the same person.

### 5.3 Anonymisation (issue #9)

Each reviewed member gets a code such as `M-3f9a1c2b`, made with HMAC-SHA256
and a secret key kept in `.env`. The same name always gives the same code, the
name cannot be recovered without the key, and the Chama id is part of the input
(D-001).

`staging` receives only structured columns plus the code. **Free text stays in
`raw`**, because notes mention people by name, including non-members (D-008).
Only the date is kept from the "next meeting" note. The step stops if any
spelling is unreviewed, and before saving it scans every staging column for
words from members' names.

### 5.4 Cleaning (issue #10)

A dbt project (`transform/`) reads `staging` and builds `analytics` (D-009).

| Written as | Read as |
| --- | --- |
| `40,000`, `46 000`, `59,000/=`, `92,400/-`, `Ksh. 43,571`, `300k` | numbers |
| `5500 + 776` | 6,276 (sums are added) |
| `-`, `=`, `nil` | 0 |
| `Cleared` as a balance | 0 |
| `8/6/14`, `7th June 2015`, `September 1st 2024` | dates (day first) |
| `May 2016`, `Nov/17` | the meeting month, when no day is written |
| `Nov. 2014`, `11/14`, `May 15`, `Aug` | due months (no year: the next such month after the meeting) |
| `2%`, `1` | an interest rate; a larger number (`2100`) is an interest amount |
| `Em`, `E`, `(E)`, `Er`, `SF`, `school fee` | loan types |

Every page gets a meeting month: written, from the previous page's "next
meeting" note, or counted from the nearest dated page (`date_source`).

Each member line gets a `line_kind`:

- `balance`: a running loan;
- `loan_given`: a new loan written as a balance;
- `repayment_only`: a payment that can't be tied to a balance;
- `no_loan`: dashes, or only a contribution;
- `empty`.

Anything unreadable is kept, with the reason in an `issues` column, never
dropped.

### 5.5 Rebuilding loans (issue #11)

The ledger has no loan numbers; a loan exists only as a balance carried from
page to page. `loan_lines` chains each member's lines (D-010, D-015). A line
continues an earlier line of the same member, up to three pages back, when:

- its balance before matches that line's closing balance, or
- it matches that balance plus a loan listed at that meeting (a top-up),

within 10%. Candidates of the same loan type come first, then the nearest page,
then the closest balance. Both lines must choose each other. A line that
continues nothing starts a new loan.

`loans` then gives one row per loan:

- when it was given, and how that was found;
- its type;
- its due month: written in the ledger, or 12 months (normal loans) or one
  month (emergency loans) after it was given;
- what was repaid, and when it was cleared;
- the balance outstanding at the due month;
- a status: `repaid_on_time`, `repaid_late`, `topped_up` (the unpaid balance
  was rolled into a bigger loan), `overdue`, `open`, or `lost_track`.

### 5.6 Data checks and report (issue #12)

dbt data tests check every model. **Structural** problems stop the pipeline
with a clear message: duplicate ids, a page without a month, an unknown status,
a balance line not tied to a loan. **Ledger inconsistencies** only warn,
because the data must stay as written: a balance not carried forward exactly,
or a balance that grows more than interest allows.

Three dbt unit tests run the parsing, dating and linking rules on made-up
rows. On success, a quality report (counts per Chama and year) is printed and
saved to `data/processed/quality_report.csv`.

### 5.7 One command (issue #13)

`all` creates the schemas, ingests, restores reviewed names, anonymises and
builds `analytics`. When it finds unreviewed spellings, it writes the review
file and stops with instructions. A wiped database is rebuilt from the
workbooks and the review file alone, which was tested on an empty database.

---

## 6. Technology stack

The project follows the DataTalksClub **Data Engineering Zoomcamp**, except
where a course tool does not suit private, small, batch data on one computer.

| Tool | Version / form | Role in the project |
| --- | --- | --- |
| Python | 3.11, conda environment `chama` | Pipeline code |
| PostgreSQL | 16, Docker Compose | The four-layer database |
| pandas, openpyxl | — | Reading workbooks, building the template |
| SQLAlchemy, psycopg2 | — | Talking to PostgreSQL |
| click | 8 | The command line `python -m chama.pipeline <step>` |
| dbt | dbt-core 1.12, dbt-postgres 1.11 | Cleaning, loan reconstruction, data tests, unit tests |
| pytest, ruff | — | Python tests and linting |
| hmac, hashlib, difflib | Python standard library | Member codes; name similarity |
| Git, GitHub | terminal-only workflow (D-007) | Version control, issues, milestones |
| PlantUML, Mermaid | — | Diagrams |

**Course tools not used, and why:**

| Course tool | Decision | Reason |
| --- | --- | --- |
| uv | conda instead | The project owner's choice of environment manager |
| GCS, BigQuery, Terraform | not used | The data names real people and is used with the officials' permission; it stays on this computer (D-001) |
| Kestra | deferred to M3 | Runs are occasional, with a human review in the middle; a scheduler adds a server without removing that step (D-011) |
| Spark, Kafka | not used | A few thousand rows of monthly batch records need no distributed or streaming processing |
| pgAdmin | not added yet | `psql` in the container is enough for now |
| pandera | replaced by dbt tests | One tool for transformations and data tests (D-009) |

---

## 7. Design decisions

| ID | Decision | Why | Where |
| --- | --- | --- | --- |
| D-001 | Anonymise inside the pipeline, not by hand | Raw data stays faithful; protection is a tested step | `pseudonymise.py`, `anonymise.py` |
| D-002 | Four layers: raw, private, staging, analytics | Real names stay in two restricted layers | `sql/01_schemas.sql` |
| D-003 | Branch per issue with pull requests | First workflow; replaced by D-007 | — |
| D-004 | One workbook per Chama per year | Checkable in one sitting; a fix stays local to a year | `data/raw/<chama>/<year>.xlsx` |
| D-005 | Photos named by page order with a manifest | Pages were photographed in order; the date is data | `data/photos/` |
| D-006 | Workbook layout mirrors the ledger | Raw looks like the source; interpretation is tested code | `raw_format.py` |
| D-007 | One branch per milestone plus `housekeeping`, merged from the terminal | Simple to follow | [git_workflow.md](git_workflow.md) |
| D-008 | Free text stays in raw | Notes name people, including non-members | `anonymise.py` |
| D-009 | dbt for the analytics layer and checks | Course tool; SQL never sees names | `transform/` |
| D-010 | Loans rebuilt by chaining lines on balance | No loan numbers exist | `loan_lines.sql`, `loans.sql` |
| D-011 | One command (`all`); Kestra deferred | Occasional runs with a human review | `pipeline.py` |
| D-012 | Loan term 12 months; later written due months are extensions | Confirmed with the Chama's rule | `config/pipeline.yaml` |
| D-013 | A loan type column on Statements | Type marks must survive anonymisation | `raw_format.py`, `statements.sql` |
| D-014 | M1 closes with Chama B only | Chama A has no data yet | `config/pipeline.yaml` |
| D-015 | Linking prefers the same loan type | Members hold several loans with equal balances | `loan_lines.sql` |

Smaller choices and why:

- **Flag, never drop.** Unreadable values become empty, with the reason
  recorded. Counts stay honest.
- **Planned stops, not crashes.** A step that cannot continue explains what to
  do.
- **Tolerances.** Balances may differ by 10% between linked lines (misreadings,
  interest), and a member may miss two meetings. Differences over 2% are
  reported as warnings.
- **Retakes and halves.** A page photographed twice is typed once, under the
  first photo's number, so pages stay in ledger order.
- **The dbt project is in `transform/`.** A folder named `dbt` in the project
  root clashes with the installed package.
- **dbt's anonymous usage tracking is off,** because this is a private data
  project.
- **The database container receives only the database settings,** never the
  pseudonym key.

---

## 8. Data protection and ethics

- The data is used with the written permission of the Chama's officials.
- **Never committed:** photos, workbooks, review files, `.env` and the database
  volume. `.gitignore` blocks them by type and folder.
- **Names stop at anonymisation.** `staging` and `analytics` hold codes only,
  and the pipeline checks this on every run. Everything later (models, MLflow,
  dashboard) sees codes only.
- **Free text is left behind** in `raw`, because no name list can clean it.
- **The key** (`PSEUDONYM_KEY`) lives in `.env` and must be backed up. Losing it
  changes every code.
- **Documentation holds no names.** This report, the extraction log and the
  quality report contain counts and codes only.
- **Transcription.** The photos were read with AI assistance during
  extraction. The pipeline itself sends no data anywhere.

---

## 9. Testing and quality assurance

| Layer | Tests | What they cover |
| --- | --- | --- |
| Python (pytest) | 45 | Loader and template (8), member codes (7), name matching and the review file (15), anonymisation and the name check (14), report layout (1) |
| dbt data tests | 34 | Unique ids, required values, accepted values, page relationships, every balance line tied to a loan; 2 warning tests for ledger inconsistencies |
| dbt unit tests | 3 | Amount, date, interest and loan-type parsing; page dating; line linking with top-ups, missed meetings and loans of different types |
| End to end | — | A wiped database rebuilt with one command; each year re-run after extraction |

Last full run: **42 passed, 2 warnings, 0 errors**. The warnings list 6
balances carried forward with more than a 2% difference and 2 balances that
grow too much. Each one is a known ledger inconsistency, logged for the paper
check, such as a balance carried as 32,000 then 30,000, or one written as
"23000" for 230,000.

---

## 10. Results on the full ledger

### 10.1 Overall

| | |
| --- | --- |
| Meetings | 148 (January 2014 – April 2026): 75 dated on the page, 48 with month only, 4 dated from the previous page's note, 21 placed by their neighbours |
| Member lines | 1,799: 1,630 loan balances, 148 with no loan that month, 12 new loans written as balances, 5 unlinked repayments, 4 empty |
| Lines marked unclear in the ledger | 53 (to check against the paper) |
| Lines with unreadable values | 7 |
| Loans listed as given | 174 (4 with no member written) |
| Members | 13 (after the suggested name matches) |
| Loans rebuilt | **263**: 116 normal, 111 emergency, 36 school fees |
| Lines linked into loans | 1,364 continued, 15 with a top-up, 263 starts |

### 10.2 By year

| Year | Pages | Lines | Loans listed | Loans | Repaid on time | Repaid late | Topped up | Overdue / open / lost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | 12 | 167 | 22 | 46 | 42 | 3 | 0 | 0 / 0 / 1 |
| 2015 | 12 | 141 | 12 | 23 | 17 | 3 | 3 | 0 / 0 / 0 |
| 2016 | 12 | 131 | 15 | 19 | 16 | 2 | 1 | 0 / 0 / 0 |
| 2017 | 12 | 148 | 12 | 26 | 20 | 6 | 0 | 0 / 0 / 0 |
| 2018 | 12 | 144 | 16 | 22 | 7 | 11 | 2 | 0 / 0 / 2 |
| 2019 | 12 | 146 | 4 | 23 | 5 | 12 | 4 | 0 / 0 / 2 |
| 2020 | 12 | 141 | 8 | 15 | 3 | 11 | 1 | 0 / 0 / 0 |
| 2021 | 12 | 175 | 19 | 32 | 19 | 9 | 2 | 0 / 0 / 2 |
| 2022 | 12 | 152 | 14 | 15 | 8 | 6 | 1 | 0 / 0 / 0 |
| 2023 | 12 | 144 | 11 | 14 | 7 | 4 | 1 | 2 / 0 / 0 |
| 2024 | 12 | 144 | 15 | 14 | 10 | 1 | 0 | 3 / 0 / 0 |
| 2025 | 12 | 124 | 17 | 10 | 6 | 1 | 0 | 1 / 2 / 0 |
| 2026 (Jan–Apr) | 4 | 42 | 9 | 4 | 1 | 1 | 0 | 0 / 2 / 0 |
| **Total** | **148** | **1,799** | **174** | **263** | **161** | **70** | **15** | **6 / 4 / 7** |

"Loans" are counted in the year the loan first appears.

### 10.3 Loan behaviour

| | Normal | Emergency | School fees |
| --- | --- | --- | --- |
| Loans | 116 | 111 | 36 |
| Months from issue to clearing (median, cleared loans) | 12 | 1 | 5 |
| Longest (months) | 33 | 18 | 20 |
| Median months late (late loans) | 3.5 | 1 | 8 |

**Average normal loan by the year it starts:**

| Year | Average |
| --- | --- |
| 2014 | ≈ 43,000 |
| 2015–2017 | ≈ 70,000 |
| 2018–2019 | ≈ 100,000–110,000 |
| 2021 | ≈ 140,000 |
| 2022 | ≈ 190,000 |
| 2023–2025 | ≈ 230,000–300,000 (largest 350,000) |

**Where the dates come from:**

- Issue month: from the new-loans list for 125 loans, estimated (the meeting
  before the loan first appears) for 118, written as a new balance for 8, and
  already running when the records start for 12.
- Due month: written in the ledger for 57 loans (2014–2017), and set by the
  12-month (or one-month emergency) rule for 206.

---

## 11. Findings for the Chama and for modelling

1. **The 12-month rule does not describe practice.** The Chama's rule is 12
   months (D-012).
   - In 2014–2017 the due month written beside a loan is usually about 15
     months after it was given.
   - From 2018 no due months are written.
   - Since 2021 loans of 200,000–350,000 are repaid at 10,000–20,000 a month,
     which takes two years or more.

   Under the 12-month rule, 70 loans count as repaid late and 6 as overdue.
   Many of these are normal practice rather than distress. **The definition of
   default must be agreed with the Chama before modelling.**
2. **Emergency loans changed.** In 2014–2016 they were repaid at the next
   meeting at 5%. From 2017 they run two to three months at 3%. With a one-month
   term, 41 emergency loans count as late. The emergency term needs confirming.
3. **Interest practice changed.** Monthly rates of 1–2% were written up to
   2015. Interest amounts were written in their own column from July 2022, with
   repayments then counting only principal. Features must account for this.
4. **Rolled-over loans.** 15 loans were not cleared but rolled into a bigger
   loan. This is a common pattern and a likely signal for the model.
5. **Loans that stop appearing.** 7 loans stop appearing while the records go
   on. Most are small emergency or school-fees loans whose repayment was not
   written; one member stopped appearing in 2020 with a balance outstanding.
   These need the Chama's explanation.
6. **A small, stable membership.** 13 members, 10–12 at a meeting. The data is
   long (12 years) but narrow, which shapes how models can be trained and
   tested (section 16).

---

## 12. Limitations

- **Transcription accuracy is not yet measured.** The check against the paper
  (#7) is pending. 53 lines were typed with doubts and are listed in the
  extraction log.
- **Name review.** The latest spellings (2016–2026) await confirmation. The
  figures in this report assume the suggested matches.
- **Loan reconstruction is a heuristic.** Linking on balance is checked by
  warnings and unit tests, but a misread figure can split a loan. One example
  is the April 2026 balance written "23000" for 230,000.
- **Dates.** 21 pages are placed by their neighbours, and 48 give the month
  only. 206 due months come from a rule, not the ledger.
- **Free text is not available to models.** Reasons, agreements and remarks
  stay in `raw` by design.
- **Small data.** One Chama, 13 members, 263 loans (116 normal). Training
  must avoid overfitting and keep a member's or a period's loans out of both
  training and testing at once.

---

## 13. Running the project

All commands run in PowerShell from the project folder, inside the `chama`
conda environment.

### First-time setup

```powershell
conda create -n chama python=3.11 -y
conda activate chama
pip install -e ".[dev]"                     # pandas, dbt-postgres, click, pytest, ruff, ...
Copy-Item .env.example .env                 # then fill in the password and the key
python -c "import secrets; print(secrets.token_hex(32))"   # a new PSEUDONYM_KEY (back it up)
docker compose up -d                        # PostgreSQL (Docker Desktop must be running)
pytest
```

### Every session

```powershell
conda activate chama
docker compose up -d
```

### The pipeline

```powershell
python -m chama.pipeline all               # everything, in order (stops if names need review)

python -m chama.pipeline ingest            # 1. workbooks -> raw
python -m chama.pipeline suggest-aliases   # 2. write the name review file
python -m chama.pipeline load-aliases      #    load the reviewed file
python -m chama.pipeline anonymise         # 3. raw -> staging with codes
python -m chama.pipeline clean             # 4. dbt build, checks, quality report

python -m chama.pipeline --help            # list the steps
```

### Reviewing names (when `all` stops for it)

```powershell
# 1. Open data/interim/aliases_chama_b.csv in Excel, check canonical_name, save
python -m chama.pipeline load-aliases      # 2. load it (rows are marked "reviewed")
python -m chama.pipeline all               # 3. carry on

python -m chama.pipeline suggest-aliases --overwrite   # regenerate a file with unloaded changes
```

### dbt

```powershell
python -m chama.pipeline dbt build                     # models and all tests
python -m chama.pipeline dbt test                      # tests only
python -m chama.pipeline dbt run --select loans        # one model
python -m chama.pipeline dbt docs generate             # documentation site
python -m chama.pipeline dbt docs serve                # open it at http://localhost:8080
```

### Tests and code checks

```powershell
pytest
ruff check src tests
```

### Looking at the data

```powershell
docker exec -it chama-postgres psql -U <POSTGRES_USER> -d <POSTGRES_DB>
#   \dt analytics.*
#   select status, count(*) from analytics.loans group by 1;
#   select * from analytics.quality_report;
#   \q
```

The quality report is also saved to `data/processed/quality_report.csv`.

### Templates, rebuilds and the container

```powershell
python scripts/make_raw_template.py        # an empty yearly workbook

docker compose down -v                     # deletes ALL database data (workbooks and review files are kept)
docker compose up -d
python -m chama.pipeline all               # rebuilds everything from the workbooks and review files

docker compose ps                          # is the database running?
docker compose stop                        # stop it (data kept)
```

### Git (terminal only)

Full steps: [git_workflow.md](git_workflow.md).

```powershell
git switch m1-data-pipeline
git pull --no-edit origin main
pytest
git status                                 # no data files, photos or .env
git add <files>
git commit -m "M1: short description (#issue)"
git push

git switch main
git pull
git merge --no-ff m1-data-pipeline `
  -m "M1: <what this round does>" `
  -m "Closes #<issue>" `
  -m "Problem: <what was wrong or missing>" `
  -m "Remedy: <what changed and why>"
git push
git switch m1-data-pipeline
```

---

## 14. What is left to close Milestone 1

| Item | Status (12 October 2026) |
| --- | --- |
| Extract the ledger | **Done.** All 149 photos, January 2014 – April 2026. |
| Review the latest name spellings | **To do.** Confirm the suggested matches in the review file, then `load-aliases` and `all`. |
| Check the extraction against the paper (#7) | **To do.** Every page's doubts are listed in the extraction log; record the error rate in the log. |
| Confirm with the Chama | **To do.** The practical term of large loans; the emergency loan term since 2017; the loans that stop appearing. |
| Close the finished issues | **Ready.** #3, #5, #6, #8–#13 close with the next merge into `main` (`Closes #N` lines); #7 after the paper check. |
| Chama A | **Deferred** (D-014). |
| Tidy up | Delete `data/raw/chama_b/2014.xlsx.bak` once 2014 is confirmed. |

---

## 15. Why this milestone matters

Everything later in the project rests on M1.

- **There is now data.** Twelve years of handwritten records are a database
  that can be rebuilt with one command. Adding new pages is typing them in and
  running `all`.
- **Privacy by design.** Names stop at the anonymisation step. This is enforced
  by code, tests and a check on every run, as the officials' permission
  requires.
- **Traceable and honest.** Every value leads back to its photo, workbook and
  row. Doubts and inconsistencies are flagged and counted, not hidden, which
  matters when the results are defended.
- **Loans and outcomes exist.** The ledger has no loan numbers. M1 rebuilt 263
  loans with their issue month, type, repayments and outcome. This is the raw
  material for the default label in M2.
- **The data corrected assumptions.** The 12-month rule, the emergency term and
  interest practice all differ from first expectations. Without this, M2 would
  have learned from a mislabelled target.

---

## 16. Next: Milestone 2 — features and models

**Goal.** For each loan request, give officials a **risk score, a risk
category and an explanation**. The model supports their decision; it does not
make it. Work happens on the `m2-features-models` branch.

**Planned approach:**

1. **Agree the target with the Chama.** Possible definitions:
   - still owing a set share of the loan a set number of months after the
     practical term;
   - several months with no principal repaid;
   - the loan rolled into a bigger one while unpaid;
   - the loan written off or lost.

   The section 11 findings mean the 12-month rule alone is not a usable
   label.
2. **Build features from each member's history before the loan is given**, so
   no information leaks from after the decision. Candidates:
   - repayment regularity, and months with interest only or no payment;
   - past late, rolled-over and overdue loans;
   - emergency and school-fees borrowing;
   - loan size against the member's past loans and the Chama's typical loan;
   - number of loans held at once;
   - years of membership;
   - contribution regularity (from December 2016).

   These can be dbt models in `analytics`, tested like the rest.
3. **Train and compare models suited to small data:** Logistic Regression as
   an interpretable baseline, then Random Forest and XGBoost with strong
   regularisation.
4. **Validate honestly:** train on earlier years and test on later ones, keep
   each member's loans together when testing, and handle the class imbalance.
   Report recall on defaults, precision-recall and the calibration of risk
   scores.
5. **Explain with SHAP,** so officials see which factors raised or lowered a
   member's risk, and map scores to clear risk categories.

MLflow experiment tracking, Evidently monitoring and scheduled runs (possibly
Kestra) follow in M3, and the officials' dashboard in M4.

---

## 17. Glossary

| Term | Meaning |
| --- | --- |
| Chama | A Kenyan savings and credit group |
| Normal loan | The main loan, repaid monthly with interest |
| Emergency loan (Em, E) | A short loan, repaid within one to three months at 3–5% |
| School-fees loan (SF) | A loan for school fees, usually repaid within months |
| Top-up | Money added to a running loan; the balance grows |
| B/F | Brought forward (money carried from the last meeting) |
| Monthly | A member's monthly contribution (300, later 350) |
| `raw` / `private` / `staging` / `analytics` | The four database layers (section 4) |
| Member code | The anonymous identifier (`M-xxxxxxxx`) that replaces a name |
| Review file | `data/interim/aliases_<chama>.csv`, the human-checked list of name spellings |
