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
| D-008 | 2026-10-06 | Free text stays in `raw`; staging gets structured columns and codes only |
| D-009 | 2026-10-06 | dbt builds the analytics layer and runs the data checks |
| D-010 | 2026-10-06 | Loans are rebuilt by chaining ledger lines on balance |
| D-011 | 2026-10-06 | One command (`all`) runs the pipeline; Kestra deferred |
| D-012 | 2026-10-08 | Loan term is 12 months; later written due months are per-loan extensions |
| D-013 | 2026-10-08 | Statements gain a `loan_type` column for the emergency mark |
| D-014 | 2026-10-08 | Milestone 1 closes with Chama B only |
| D-015 | 2026-10-12 | Loan linking prefers lines of the same loan type |
| D-016 | 2026-10-16 | Models train in Colab; only the codes-only modelling table goes to Google Drive |
| D-017 | 2026-10-16 | The GitHub repository is private |
| D-018 | 2026-10-16 | Point-in-time features and a provisional default label, built in dbt |
| D-019 | 2026-10-16 | MLflow experiment tracking starts in Milestone 2 |
| D-020 | 2026-10-16 | Walk-forward testing; imbalance strategies compared, not assumed |

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

## D-008 Free text stays in raw
**Context.** The free-text columns (`Statements.remarks`, `Meetings.host`,
`Meetings.notes`, `Meetings.next_meeting`, `NewLoans.remarks`) mention people by
name: hosts, members who brought cash, and people who are not members at all.
Replacing names in free text with codes only works for names already on the
member list, so some names would slip through.
**Decision.** The anonymise step copies only structured columns to `staging`,
with `member_name` replaced by `member_code`. Free-text columns stay in `raw`,
for checking against the paper. From `next_meeting` only the date is kept
(`next_meeting_date`), because early pages give no other date. Before saving,
the step checks every staging column for words from members' names and stops
if it finds any. Every spelling must have a reviewed alias in
`private.member_aliases` first; the step stops rather than give an unreviewed
spelling its own code.
**Why.** D-001 promises that everything after anonymisation sees only codes.
Leaving the text out is the only way to keep that promise.
**Consequences.** Staging values are still text as written; the clean step
gives them types. Anonymisation stays in Python, not dbt, because it needs the
secret key from `.env` and a human review of name matches. SQL tools start at
`staging`, which holds no names.

## D-009 dbt for the analytics layer
**Decision.** Cleaning (#10), linking lines into loans (#11) and the data
checks (#12) are a dbt project in `transform/`, reading `staging` and writing
`analytics`. Checks are dbt tests: structural ones (unique ids, every page
dated, known statuses) stop the pipeline; ledger inconsistencies (a balance not
carried forward exactly) only warn, because the data must stay as written.
dbt unit tests check the parsing and linking rules on made-up rows.
**Why.** The project follows the Data Engineering Zoomcamp, which uses dbt for
transformations and data tests. This replaces the pandera checks planned in
issue #12; one tool now does both. `analytics` holds codes only, so SQL tools
never see names (D-008).
**Consequences.** dbt is run through `python -m chama.pipeline clean` (or
`... dbt <command>`), which loads `.env` and passes the loan rules from
`config/pipeline.yaml`. dbt's anonymous usage tracking is switched off.

## D-010 Loans rebuilt from ledger lines
**Context.** The ledger has no loan numbers. Each page lists a member's balance
before, repayment, balance after and due month; a member can have a normal and
an emergency loan at once, and top-ups are added to running balances.
**Decision.** A line continues an earlier line of the same member (up to three
pages back) when its balance before matches that line's closing balance, or
that balance plus a loan listed for the member at that meeting (a top-up),
within 10%. The nearest page wins, then the closest balance; each line
continues at most one other. Unmatched lines start a new loan. The due month
is the one written in the ledger; `loan_term_days` (and `emergency_term_days`)
only fill in when none is written. Loans already running on the first page are
marked `before_records`.
**Why.** Balance continuity is how a person reads the ledger, and it survives
spelling and heading changes. Written due months reflect what the Chama agreed
for each loan.
**Consequences.** Linking depends on correct member codes: two spellings of
one person left as two members break a loan's chain (seen as `lost_track` or a
carried-balance warning). In 2014 the written due month is about 15 months after
a normal loan is given, not 12 as `loan_term_days: 365` suggests; to be
confirmed with the Chama.

## D-011 One command runs the pipeline; Kestra deferred
**Decision.** `python -m chama.pipeline all` runs every step in order (#13):
schemas, ingest, name check, anonymise, dbt build and report. It stops, with
instructions, when new name spellings need a person's review. The review files
in `data/interim/` are the lasting record of that review: `load-aliases` marks
their rows `reviewed`, and `all` restores reviewed rows into an empty database,
so the database can be rebuilt from the Excel files and the review files.
**Why not Kestra (yet).** The Zoomcamp orchestrates with Kestra, which pays off
for scheduled, unattended runs. This pipeline runs occasionally (when a year of
ledger pages has been extracted), on one computer, with a human review in the
middle; a scheduler would add a server and its own database without removing
that manual step, and it would need access to the private data and the secret
key. A Kestra flow can be added on top later with a single task that calls
`python -m chama.pipeline all`, for example in Milestone 3 when models are
retrained on a schedule.

## D-012 Loan term 12 months; written due months are extensions
**Context.** D-010 noted that due months written in the ledger are about 15
months (13–19 in 2015) after a normal loan is given, while `loan_term_days`
is 365.
**Decision.** Confirmed: the Chama's rule is 12 months (`loan_term_days: 365`
stays). A later due month written beside a loan is an extension agreed for
that loan, so the written due month still decides when that loan is due; the
rule only fills in loans with no written due month. `rule_due_month` in
`analytics.loans` keeps the 12-month date for comparison.
**Consequences.** Milestone 2 can treat "due later than the rule" as a feature
(an extended loan) and should define default against the written due month.

## D-013 A loan type column on Statements
**Context.** From mid-2015 the ledger marks emergency loans with `Em`, `Eme` or
`(Em)` beside the name. Kept in the name, the mark is lost when names become
codes; kept in `remarks`, it does not reach staging (D-008).
**Decision.** `Statements.loan_type` holds the mark as written. The pipeline
standardises it (`emergency`, `school_fees`, `top_up`) and a marked loan takes
that type. Existing workbooks get the column empty; the loader and anonymise
step add missing columns to existing tables, so the raw format can grow.
**Why.** Emergency and normal loans behave differently; the model needs to know
which is which.

## D-014 Milestone 1 closes with Chama B only
**Decision.** Chama A has no ledger data yet. Milestone 1 closes on Chama B;
Chama A stays in `config/pipeline.yaml` and is picked up automatically when its
Excel files appear in `data/raw/chama_a/`.

## D-015 Linking prefers the same loan type
**Context.** From 2021 members often hold a normal, a school-fees and an
emergency loan at once, sometimes with equal balances (for example a 30,000
emergency loan beside a 30,000 school-fees balance). Matching on balance alone
could join the wrong pair.
**Decision.** When a line could continue more than one earlier line, it takes
one of the same loan type first (normal, emergency, school fees), then the
nearest page, then the closest balance. A line of another type is still used
when no same-type line matches, because the ledger sometimes marks one loan
differently from month to month. Extends D-010.

## D-016 Train in Colab; only the modelling table goes to Drive
**Context.** The supervisor's Sprint II workflow is: code on the laptop, push
to GitHub, open notebooks in Google Colab, read data from and save models,
metrics and plots to Google Drive, then review the synced results locally.
In M1 the cloud tools were set aside because the data names real people
(D-001).
**Decision.** Follow the workflow, with one boundary: the only data that
leaves this computer is `analytics.loan_features`, written by
`python -m chama.pipeline export` as `loan_features.parquet` with a manifest.
It holds member codes, loan types, amounts, months and features: no names and
no free text. The export stops if the table gains a column not on its list or
if any value contains a word of a member's name. Workbooks, photos, review
files, the `raw` and `private` schemas and the pseudonym key never leave.
`DRIVE_DIR` in `.env` names the project folder on Drive; it holds `data/` (the
export) and `mlruns/` (models, metrics, plots).
**Why.** Colab gives the supervisor an environment to open and rerun; it is
not needed for speed (a few hundred loans train in seconds). The export keeps
D-001's promise: everything outside this computer sees codes only.
**Consequences.** Pseudonymised data is still personal data: with about a
dozen members, someone who knows the group could recognise a member from loan
sizes and dates. The officials confirmed on 2026-10-16 that their permission
covers storing it on Google Drive. Notebooks also run locally from the same folder
(synced by Drive for desktop), so work does not depend on Colab.

## D-017 Private GitHub repository
**Context.** In the workflow, Colab saves notebook changes straight to GitHub,
outputs included, without passing through local git or its checks. Outputs
show member codes, amounts and dates.
**Decision.** The repository is private (changed 2026-10-16; it had no stars,
forks or Pages site). The supervisor is added as a collaborator.
**Consequences.** Colab needs GitHub authorisation to open notebooks, and a
read-only access token stored in Colab Secrets to install the `chama` package
from the repository. Outputs in notebooks hold nothing beyond what D-016
allows, because notebooks read only the exported table.

## D-018 Point-in-time features and a provisional label
**Context.** Section 11 of the M1 report showed the 12-month rule does not
describe practice, so the default label must be agreed with the Chama. Work
cannot wait for that.
**Decision.** `analytics.loan_features` (dbt) has one row per loan with a known
issue month. Features use only meetings before the issue month and earlier
loans as they stood then; a dbt unit test checks this on made-up loans.
`defaulted` is 1 when the status is in `default_statuses` in
`config/pipeline.yaml`, provisionally `topped_up`, `overdue` and `lost_track`;
0 for other finished loans; empty while the outcome is unknown.
**Why.** Features in dbt are tested and rebuilt with the data, and the M4
dashboard can reuse them; notebooks only model. Keeping the label rule in the
config means the agreed definition changes one line.
**Update 2026-10-16.** Confirmed: an overdue loan is a default. `topped_up` and
`lost_track` stay provisional. All six overdue loans (2023–2025) are normal
loans of 250,000–350,000 with no due month written, so they are judged by the
12-month rule while still being repaid; if the Chama agreed a longer term for
large loans, `loan_term_days` should say so, or these count as defaults.
**Consequences.** `lost_track` is in the label, so unlinked name spellings now
create false defaults. The warning test `loan_continues_under_another_member`
lists loans that seem to continue under another member code; these must be
resolved in the name review before training.

## D-019 MLflow tracking starts in Milestone 2
**Decision.** Training runs log their settings, metrics, plots, SHAP results
and the model to MLflow from the first model. In Colab the tracking folder is
`mlruns/` on Drive; locally `mlflow ui` reads the same folder through Drive
for desktop. Milestone 3 keeps the model registry, serving, Evidently
monitoring, Docker and scheduling.
**How.** MLflow 3 keeps folder tracking in maintenance mode and refuses it
unless `MLFLOW_ALLOW_FILE_STORE=true`; the code sets this. The recommended
SQLite database is a single file that Colab's Drive mount and Drive for
desktop would both write, which risks corrupting it; a folder of small files
syncs safely. In M3 the runs can move to a database (for example the
project's PostgreSQL) with `mlflow migrate-filestore`. Models are saved with
cloudpickle, because MLflow's default (skops) refuses the imbalanced-learn and
XGBoost types; they are only loaded back from the project's own folder.
**Why.** The MLOps Zoomcamp introduces experiment tracking right after the
first model (module 2), and the workflow's "save models, metrics, plots and
logs" step is what MLflow does. Comparing models without it means comparing
loose files.

## D-020 Walk-forward testing; imbalance strategies compared
**Context.** A few hundred loans from about a dozen members over twelve years,
roughly one default in six. Random train/test splits would let a model learn
from later loans of the same members and from outcomes nobody knew yet, and
would overstate how well it works.
**Decision.**
- **Main test: walk forward.** For each year 2018–2024, train only on loans
  given and resolved (`outcome_month`) before that year, then score that
  year's loans; the years are pooled for the metrics. Loans given after 2024
  have had too little time to show a default and are not tested. A year needs
  at least 5 known defaults before it: 2018 and 2019 train on 5–6, but
  without them the test rests on 12 defaults instead of 22.
- **Second check: members held out** (grouped folds), for how the model would
  do on a member it has not seen.
- **Metrics:** precision-recall AUC (chance level is the share of defaults),
  ROC AUC and the Brier score, with bootstrap 95% intervals, plus how the risk
  bands sorted the test loans.
- **Imbalance:** at the project owner's request, k-means based resampling is
  included. Every model is trained four ways and compared on the same tests:
  no correction, class weights, k-means SMOTE (synthetic defaults inside
  k-means clusters) and k-means cluster centroids (repaid loans reduced to one
  real loan per cluster). Resampling runs inside the training folds only.
  These strategies train as if half the loans defaulted, so their scores are
  moved back to the real share of defaults (prior correction: odds multiplied
  by share / (1 − share); Saerens et al. 2002, Dal Pozzolo et al. 2015). The
  order of the scores, and so PR AUC and ROC AUC, is unchanged; the Brier
  score and the risk bands become comparable with `none`.
- **Choice:** the best walk-forward PR AUC, unless its Brier score shows the
  scores cannot be read as risks; differences within the intervals are not
  treated as wins.
**Why.** A study of clinical risk models (van den Goorbergh et al., "The harm
of class imbalance corrections for risk prediction models", JAMIA 2022) found
that random over- and undersampling and SMOTE did not improve the ranking of
logistic regression models and made their probabilities overestimate risk,
which officials here would read as a member's risk. Testing the strategies on
this data, rather than assuming they help or hurt, gives evidence either way.
**Results, 2026-10-19** (clean names; 263 loans, 247 with a known outcome,
28 provisional defaults):
- Walk forward (133 test loans, 22 defaults, chance PR AUC 0.165): ROC AUC
  0.50–0.55 for every model and strategy, so no model ranks future loans
  reliably. XGBoost with k-means cluster centroids had the best PR AUC (0.355,
  interval 0.19–0.54), stable across seeds, from ranking a few defaults first.
- Members held out (247 loans, 28 defaults, chance 0.113): the tree models
  reach ROC AUC 0.62–0.68 (lower interval bounds 0.50–0.58); logistic
  regression 0.54–0.60. Brier scores match giving every loan the average risk.
- No imbalance strategy wins on both tests. Before the prior correction,
  weighting and resampling pushed every loan into the high band.
- SHAP: loan amount, amount against the member's largest earlier loan, number
  of earlier loans and loan type weigh most. Raw amounts grew about six-fold
  over the records; dropping them cost nothing in a separate comparison.
The first run, before the name review was fixed, is not comparable (labels
included 11 split-member artefacts).
