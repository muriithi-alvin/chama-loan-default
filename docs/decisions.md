# Design decisions

A short record of the important choices, why they were made, and what was
rejected. Newest last. Change a decision by adding a new one that replaces it.

| ID | Date | Decision |
| --- | --- | --- |
| D-001 | 2026-09-25 | Anonymise inside the pipeline, not by hand |
| D-002 | 2026-09-25 | Four database layers: raw, private, staging, analytics |
| D-003 | 2026-09-26 | Git workflow: issue → branch → PR → merge commit, branches kept (replaced by D-007) |
| D-004 | 2026-09-29 | One raw Excel file per Chama per year |
| D-005 | 2026-09-29 | Photos named by page order in one folder, not by year |
| D-006 | 2026-09-29 | Raw Excel layout mirrors the ledger's meeting statements |
| D-007 | 2026-10-01 | One long-lived branch per milestone plus `housekeeping` |

---

## D-001 Anonymise inside the pipeline
**Context.** The ledgers contain real member names.
**Decision.** Extract names exactly as written into the raw Excel files. The
pipeline replaces them with codes (`M-xxxxxxxx`) using HMAC-SHA256 and a secret
key kept in `.env`. Spelling variants are first linked to one member through the
`private.member_aliases` table.
**Why.** Keeps raw data faithful to the ledger and makes data protection a
visible, tested part of the system.
**Consequences.** Raw files and the `raw`/`private` schemas are sensitive and
never leave this computer. Losing the key changes every code, so it is backed up.

## D-002 Four database layers
`raw` (as recorded, text) → `private` (name-to-code link, restricted) →
`staging` (codes, typed values) → `analytics` (clean tables and features).
Everything after `staging` sees codes only.

## D-003 Git workflow
Every change starts as an issue, is built on a branch named
`type/issue-short-name`, and returns to `main` through a pull request that
records the problem and the remedy. Merge with a merge commit
(`gh pr merge --merge`) and keep branches, so the history shows each piece of
work. Rejected: squash-and-delete, because it hides the branch history.

## D-004 One raw Excel file per Chama per year
**Decision.** `data/raw/<chama>/<year>.xlsx`, combined by the loader.
**Why.** Small enough to check against the paper in one sitting; a correction
to one year does not touch the others. Rejected: one large file (hard to review,
risky to edit) and five-year files (arbitrary split).

## D-005 Photo naming
**Decision.** All pages of a Chama live in one folder, named by the order they
were photographed (`chama_b_p001.jpg` …), with a manifest linking each name to
the original file. The meeting date is read from the page into the data.
**Why.** The pages were photographed in ledger order, and each page carries its
own date, so the year is data rather than a folder. Names never change if a
missing page is added later. This replaces the year folders suggested earlier.

## D-006 Raw layout mirrors the ledger
**Context.** Reading the photos showed the ledger is not a separate loan book
and repayment book: each page is one monthly meeting's statement with a row per
member (balance before, repayment, interest, balance after, month due, and from
about 2018 a monthly contribution), followed by the loans given that day, totals
and notes. Column headings change over the years.
**Decision.** Sheets `Statements`, `Meetings`, `NewLoans` and `Attendance`
(see [data_dictionary.md](data_dictionary.md)). Values go into the column with
the same meaning; the headings as written are kept in `Meetings.column_headers`.
Rows are linked to their page by `source_photo`.
**Why.** Raw data should look like the source. Splitting into loans and
repayments is a cleaning step, done in code where it is tested and repeatable.
**Consequences.** The cleaning step must work out meeting dates (some early
pages only give the *next* meeting's date) and link each balance to its loan.

## D-007 One branch per milestone plus housekeeping
**Context.** D-003 made a new branch for every issue (`feature/5-...`,
`chore/3-...`). With many small issues this made too many branches, and it was
hard to tell which one held what.
**Decision.** One long-lived branch per milestone (`m1-data-pipeline` …
`m5-report`) and one `housekeeping` branch for bug fixes, docs, templates and
tooling not tied to a milestone. Each round of work goes to `main` through a pull
request from the pull request template, merged with a merge commit. Branches are
kept and reused. Steps are in [git_workflow.md](git_workflow.md).
**Why.** The branch name says which milestone the work belongs to, and there are
only six branches to keep track of.
**Consequences.** A pull request can close several issues at once. Before each
round, run `git pull origin main` on the branch so it picks up work merged from
the other branches. Replaces D-003.
