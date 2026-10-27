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
| D-021 | 2026-10-20 | A second target: an early warning of missed repayments |
| D-022 | 2026-10-21 | Risk bands set by share of out-of-time scores |
| D-023 | 2026-10-21 | The chosen model: random forest, no imbalance correction |
| D-024 | 2026-10-23 | Ledger photos are read by a vision model through the Claude API, then reviewed |
| D-025 | 2026-10-23 | Extraction runs on a free open-weight model (Qwen on Groq); Claude kept for comparison |

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
**Update 2026-10-20.** Money is used only as ratios: `amount` and
`outstanding_at_issue` are replaced by `outstanding_vs_amount` (debt owed
relative to the new loan), beside `amount_vs_own_max` and
`amount_vs_chama_median`. Loan sizes grew about six-fold over the records, so
raw amounts compare loans of different years unfairly; the walk-forward test
showed no loss of ranking and a slightly better Brier score without them.

## D-021 A second target: early warning of missed repayments
**Context.** The loan-default target has 28 provisional defaults among 247
loans with a known outcome, and no model ranks future loans reliably (D-020).
A few dozen events cannot support a trustworthy model, whatever the method.
**Decision.** Add a second target beside loan default, built from the same
ledger: `analytics.member_months` has one row per member per meeting while the
member owes on a loan, with features known after that meeting and the label
`missed_ahead`: a running loan gets no repayment in the next
`warning_horizon_meetings` (3) meetings. 1,187 rows have a known label, 222 of
them events (about 1 in 5). Both targets share the same tests (walk forward,
members held out), imbalance strategies, prior correction, SHAP and MLflow,
each in its own MLflow experiment (`chama-loan-default`,
`chama-missed-repayment`).
**Why.** Officials gain an early warning between loan requests (who is likely
to fall behind soon), and the model has eight times as many events to learn
from. Missed repayments are written in the ledger as they happen, so the label
needs no agreement on loan terms.
**Consequences.** Meetings are counted in order (`meeting_seq`), not by page
number, because page numbers skip where a photo was retaken. A missed
repayment is a written line with no repayment; meetings a member did not
appear at are not counted. The loan-default target stays the main one for
loan requests; the report presents both.
**Results, 2026-10-20** (one training batch, both targets; walk forward unless
stated):
- `missed_repayment` (10 test years, 1,187 rows, chance PR AUC 0.20): the
  random forest ranks future misses above chance. Best PR AUC 0.31 (interval
  0.26–0.37) with class weights, 0.29 with k-means SMOTE, 0.26 without a
  correction; ROC AUC 0.64–0.65. Members held out: ROC AUC 0.55–0.68, best
  logistic regression. Brier scores equal giving every row the average risk,
  so the scores rank members but are not yet reliable probabilities.
- `loan_default` with money as ratios (7 test years, chance 0.165): ROC AUC
  0.48–0.55; best PR AUC 0.27 (interval 0.14–0.46), XGBoost with k-means
  cluster centroids. No reliable ranking of future loans.
- Imbalance: on the early-warning target, class weights and k-means SMOTE
  gave the random forest small gains in PR AUC within the intervals; k-means
  cluster centroids lowered it. No strategy wins on both tests for either
  target.

## D-022 Risk bands set by share of out-of-time scores
**Context.** The bands were fixed score cut-offs (0.15 and 0.30 for loan
default, 0.20 and 0.40 for missed repayments). The best early-warning model
ranks members well but its scores are compressed: 95% of its walk-forward
scores lie below 0.27, so the high band held 3 of 938 test rows. Its Brier
score equals giving everyone the average risk, so the scores are not reliable
probabilities and should not be shown to officials as such.
**Decision.** Bands are set by share, per target (`band_shares` in
`config/pipeline.yaml`): the top 20% of scores are high, the next 30% medium,
the bottom 50% low. Each training run turns the shares into score cut-offs
from its own walk-forward scores, logs them to MLflow
(`band_cutoff_medium`, `band_cutoff_high`) with a band table giving each
band's event rate and a bootstrap 95% interval, and the rows still open are
scored with the chosen run's cut-offs. Officials see the band and what it
meant in testing, not the raw score.
**Why.** Bands by share use what the models do well, which is ranking; the
cut-offs are tested out of time, so the band rates are honest; and a fixed
share fixes the follow-up workload (about one member in five in the high
band).
**Results** (random forest with class weights, early-warning target, 938
walk-forward rows): in testing a repayment was missed within 3 meetings by
12% of low-band rows (interval 9–15%), 25% of medium (20–30%) and 33% of high
(26–40%): the high band had the event almost three times as often as the low
band, and the event rate rose across every fifth of the scores (8, 14, 22, 24
and 33%). For loan default no run's bands separate defaults (by fifth of the
scores, for example 19, 19, 7, 12 and 26%); its bands are computed the same
way but should not be presented as meaningful until the label is agreed and
there are more defaults.
The final numbers for the chosen model are in D-023.
**Consequences.** The shares are provisional, to agree with the Chama (for
example, how many members the officials can follow up each month). The
cut-offs change with every training batch, so the M4 dashboard must read them
from the chosen run, not from the config.

## D-023 The chosen model: random forest, no imbalance correction
**Context.** D-020 compared three models and four imbalance strategies per
target; most differences lay within the intervals. The project owner chose the
random forest.
**Decision.** For both targets: a random forest of 500 trees, depth 4, at
least 20 rows per leaf, without an imbalance correction (`chosen` under each
target in `config/pipeline.yaml`). `chama.models.chosen` loads the chosen run
of the latest training batch with its band cut-offs; notebook 03, and later
the officials' dashboard (M4), score with it.
**Sensitivity check.** The forest (with class weights) was tested walking
forward at depths 3, 4, 6 and 8 with at least 5, 10 or 20 rows per leaf. All
results lay within each other's intervals, so the conclusions do not depend on
these settings. Leaves of at least 20 rows did a little better on both targets
at every depth (early warning: PR AUC 0.32–0.33 against 0.27–0.32, Brier 0.155
against up to 0.168), so the forest uses 20. The setting was picked on the
same test, so part of that small gain may be luck.
**Why no correction.** With 20-row leaves, class weights no longer helped:
the same PR AUC (0.323 without, 0.324 with) and, without them, an equal or
better ROC AUC (0.670), Brier score (0.152), members-held-out ROC AUC (0.640)
and band separation. Without a correction the model is also simpler: no
weights and no prior correction. k-means SMOTE (PR AUC 0.305) and k-means
cluster centroids (0.281) were tested and not adopted.
**Results** (final batch, 2026-10-21, walk forward):
- Early warning: PR AUC 0.323 (interval 0.27–0.38) against 0.20 by chance;
  ROC AUC 0.670; members held out 0.640. A repayment was missed within 3
  meetings by 11.9% of low-band rows (9–15%), 23.8% of medium (19–29%) and
  35.1% of high (28–42%); the high band held 35% of all misses. Strongest
  factors (SHAP): months since the member last missed a repayment (and whether
  they ever have), the share of recent meetings missed, months of membership,
  the recent repayment ratio, the number of loans and past roll-overs.
- Loan default: PR AUC 0.228 (0.13–0.42) against 0.165, ROC AUC 0.535: not
  reliable. Its bands (15%, 10%, 30%) are out of order with overlapping
  intervals.
**Consequences.** The early-warning model is the one ready to show officials.
The loan-default model is carried forward so the pipeline is complete, but its
category should not be presented as meaningful (D-022) until the default label
is agreed with the Chama and there are more defaults. Every new training batch
updates the chosen run and its cut-offs.

## D-024 Ledger photos are read by a vision model, then reviewed
**Context.** Sprint II asks for a working path from input to output: an
official photographs a ledger page and the system takes it through to risk
scores. Until now every page was typed into Excel by hand (M1). Open-source
OCR (Tesseract, PaddleOCR) is built for print, not this handwriting, and
cloud OCR (Google Cloud Vision, AWS Textract) returns words and positions,
leaving the table and the typing rules to be rebuilt in code.
**Decision.** A vision model reads each photo through the Claude API
(`extraction` in `config/pipeline.yaml`) and returns the page as structured
output in the raw layout: the same columns as the typed files, values exactly
as written, following the typing rules of `docs/data_dictionary.md`
(`src/chama/extraction/prompt.py`). Every later step reads its rows
unchanged. Nothing it returns is trusted as it stands: checks flag the lines
to look at (`checks.py`), and a person reviews the rows against the photo
before they are loaded into `raw`. Extraction is measured against the typed
Excel files, cell by cell (`python -m chama.pipeline extract-eval`).
**Checks.** Each rule was tried on the 1,799 typed lines before it was
adopted. Amounts that are not numbers and balances that grow by more than a
month's interest almost never occur on correct lines, so they are flagged
"check". Lines where before - repayment (+ interest) is not after are
flagged only as a hint: 13% of correct lines do not add up in the ledger
itself. A check of each balance against the last page's was dropped: it
fired on 29% of correct lines, mostly where a loan was topped up between
pages. On the typed pages taken as a perfect extraction, 3.1% of lines get a
"check" flag, mostly lines marked unclear when they were typed.
**Data.** This changes D-016's boundary: ledger photos, which show real
names, now leave this computer for the Claude API. The officials gave their
permission on 2026-10-23. Photos are re-saved before sending, which drops
EXIF data such as location. The API key stays in `.env` on the server and
never reaches a browser. Extractions are saved in `data/interim/`, on this
computer only.
**Rejected.** Tesseract and PaddleOCR (handwriting); Google Cloud Vision and
Textract (positions only, rules rebuilt in code); open-weight vision models
(need a GPU, too slow on this laptop for the web interface). The extractor is
one class (`ClaudeExtractor`), so another can be compared in Sprint III.
**Consequences.** A model can return a plausible but wrong number without
warning, so the review step and the measured accuracy are part of the
design, not extras. Each page is one paid API call; `extract-eval` reports
the time and cost per page.

## D-025 Extraction runs on a free open-weight model; Claude kept for comparison
**Context.** D-024 read the photos through the Claude API, which has no free
tier. The project uses free and open-source tools where it can.
**Decision.** The default extraction provider is the open-weight Qwen 3.8 27B
model on Groq's free plan, through its OpenAI-style API
(`extraction.providers.groq` in `config/pipeline.yaml`, key `GROQ_API_KEY`).
Everything else in D-024 stands: the same layout, prompt, checks, review and
measurement. The Claude API stays as a second provider:
`extract-eval --provider claude` compares the two on the same pages, and any
other service with an OpenAI-style API and image input can be added in the
config.
**Limits.** The free plan allows about 8,000 tokens a minute. A page is about
4,300 tokens in (prompt 900, layout 1,300, photo 2,048) and 1,600 out, so it
is read in one request, with the answer capped at 3,500 tokens and no
thinking first: roughly one page a minute.
**Data.** Replaces D-024's data paragraph: ledger photos, which show real
names, leave this computer for the extraction provider. The officials gave
their permission on 2026-10-23. Groq keeps no copy of requests by default;
Zero Data Retention (Data Controls in its console) is turned on, so not even
its short abuse-monitoring logs are kept. Photos are re-saved before sending,
which drops EXIF data such as location. API keys stay in `.env` on the
server. Extractions are saved in `data/interim/`, on this computer only.
**Rejected.** Running an open-weight model on this laptop (7.4 GB of memory
and no graphics card: minutes per page); free routes whose providers may log
or train on prompts, which the names on the pages rule out; GitHub Models
(reported closed in July 2026); Cloudflare Workers AI (a free daily
allowance, but its documentation does not show image input through the
OpenAI-style API).
**Consequences.** A 27B open model may read this handwriting less accurately
than Claude; `extract-eval` measures both, and the review step catches what
either misses.

## D-026 A web interface, Kibaba, replaces the Streamlit dashboard; the mobile app is future work
**Context.** M4 was planned as a Streamlit dashboard for officials. The
supervisor asked for wider reach (a mobile app); with the Sprint II review on
28 October 2026 there was not time to build and test a native app as well as
the scan-to-score workflow.
**Decision.** M4 is a web interface for officials and members: role-based
sign-in, the chama's records, scanning a ledger page with review before it is
saved, and early-warning bands with their reasons. It works in any phone or
computer browser and can be added to a phone's home screen (a web app
manifest). The JSON API it uses is the one a mobile app would call, so the app
stays possible and becomes future work (report, Chapter 6). The interface is
called **Kibaba**, from the proverb *haba na haba hujaza kibaba* ("little by
little fills the measure"), which its sign-in page shows: a chama's savings
and records build up one meeting at a time.
**Rejected.** Streamlit (no real roles or sessions, a page reload for each
change, hard to make work well on a phone); a native mobile app now (two code
bases, app-store builds and device testing within days).
**Consequences.** The pages, roles and API are specified in
`docs/m4_master_prompt.md`; their IDs (G1, OFF-3, T9 ...) become the Sprint
III traceability table.

## D-027 Pages in Next.js; a FastAPI JSON API and a job worker behind them
**Context.** The master prompt planned FastAPI with Jinja2 templates and
HTMX. Alvin asked for a more modern, animated and responsive interface (beads
that move between band strands, a scroll story, page transitions), which is
more natural in React.
**Decision.** Two parts, one site:
- `frontend/`: Next.js 16 (React 19, TypeScript, Tailwind CSS 4, Motion for
  animation, SWR for live updates). Pages are rendered on the server with
  their data, so they arrive complete; the browser talks only to this server,
  which forwards `/api/*` to the Python API.
- `src/chama/web/`: a FastAPI JSON API that holds every rule (sessions,
  roles, CSRF, demo names, reads of the records and scores), and a worker
  (`python -m chama.web.worker`) that reads scanned photos and runs the
  pipeline from the `app.jobs` table with `SELECT ... FOR UPDATE SKIP LOCKED`,
  without Redis. Scores and reasons are computed by `python -m chama.pipeline
  score` and saved, so no model runs while a page loads.
**Sign-in.** Supabase Auth (free plan) holds the passwords. The API sends the
email and password to Supabase and, if it accepts them and the email has an
active account in `app.users`, starts its own session: an HttpOnly, Secure,
SameSite=Lax cookie whose SHA-256 alone is stored, and a CSRF token sent back
with every change. No Supabase key reaches a page.
**Scans as raw files.** An accepted scan is written as
`data/raw/<chama>/scans/scan-<upload>.xlsx` in the typed layout and its photo
as the next ledger page, so the loader, the name review and dbt treat it like
a typed page, and a rebuild from files keeps it (S-3).
**Rejected.** Jinja2 and HTMX (less suited to the animation asked for);
Supabase sessions in the browser (keys and tokens in page scripts, and the
role rules would sit in two places); Redis or Celery for jobs (another
service on a 7.4 GB laptop).
**Consequences.** Two runtimes (Node.js and Python) and three processes to
start; the README lists them. Next.js needs about 1 GB of memory while
building.

## D-028 A demo chama with fictional names
**Context.** Ground rule G5: real names never appear on a projector. Showing
chama B with names replaced on screen would still let a demo scan change
chama B's real records and bands.
**Decision.** `python -m chama.pipeline demo-chama` copies chama B's typed
pages into `chama_demo` (marked `demo: true` in `config/pipeline.yaml`) with
every member renamed to a fixed fictional Kenyan name chosen from their
member code, free-text columns emptied and no photos. The copy is checked for
every word of every real name before it is written. The pipeline then treats
it as a chama of its own, so its bands and reasons match chama B's; demo
accounts belong to it, and the handwritten demo page is scanned into it.
`DEMO_MODE=true` stays as a safety net: fictional names for any real chama
and no real ledger photo on any page. The pages carry no "demo" wording (no
banner, and the demo chama's name has no "(demo)"), so a demonstration looks
like the real service; the fictional names are explained in the report and
when presenting. This replaces the banner in the master prompt's G5.
**Consequences.** `export` leaves demo chamas out, so models are never
trained on chama B's rows twice. No fictional name shares a word with a real
member's name.
