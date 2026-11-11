# Changelog

All notable changes to this project are recorded here, newest first.
Each entry links to its issue or pull request where one exists.
Reasons behind the bigger choices are in [docs/decisions.md](docs/decisions.md).

## M4 — branch `m4-web-interface`

### Added — the live release on Hugging Face, 11 Nov 2026

- **Humble Sister may be hosted (D-041):** the MOU covers hosting Kibaba, recorded as
  `hosting: agreed`; `deploy-publish` sends a bundle with real names only for such a chama.
- **Records survive restarts:** `deploy-publish` makes a private storage bucket and mounts
  it in the Space at `/data`. Pages, photos and learned names are written there, and the
  database is saved there within two minutes of a change, after each records update and
  when the Space stops; the newest good copy is restored at start. `/api/health` says
  where pages are kept.
- **The Space gets the treasurer's phone** (and the member's, if set) as secrets.

### Added — after the presentation, 6 Nov 2026

- **Humble Sister by its real names (D-036):** its officials agreed under an MOU. The
  interface copy keeps chama B's names, with Beth Wamae shown as Alvin Muriithi
  (treasurer) and Esther Mwangi as Alvin Wise (member) in the copy only, and pages
  to July 2024 (page 128). August 2024 to April 2026 are left to enter in the interface.
  The release serves the chamas marked `release: true`; the bundle is marked as
  holding real names and `deploy-publish` refuses it.
- **Sign in with Google or a phone (D-037):** Google through Supabase with PKCE, or a
  6-digit code texted to the phone. Officials confirm every sign-in with a code
  texted to their phone. `web-user add --phone`; `RELEASE_OFFICIAL_PHONE` for the
  release.
- **Type a page (D-038):** the treasurer picks the meeting date and gets the ledger
  already filled with each member and the balance they carried; then the usual
  checks, Accept and records update. The records label it "Entered here".
- **Up to three photos of one meeting (D-039):** read one at a time, joined in order,
  each shown as a tab on the review screen.
- **The flow moves on by itself (D-040):** a step bar on every page; the reading
  opens the review, Accept opens the update, and the results (each member's colour
  and main reason) open when the update is done.
- **Fixed:** two pages accepted before the first finished updating could be for the
  same month; Accept now also checks pages accepted but not yet in the records.

### Fixed — before the presentation, 5 Nov 2026

- **Good readings no longer fail on field names (D-035):** the free model sometimes
  uses its own field names, which made clear pages and non-ledger photos end in a
  technical "could not be read" message.
- **The release's member account is Kawira Mutembei:** Muthoni Ndegwa's KSh 460,000 is
  a rebuilt second loan from a 23,000 / 230,000 slip on page 149, still to be checked
  against the paper ledger.
- **`serve-release --fresh` also deletes the demo chama's scan photos.**

### Changed — after the Sprint II review (reviewers: too plain, too technical)

- **Plain words for the bands:** "Follow up now", "Keep an eye on" and "Less
  likely to miss", each with one sentence of meaning; reasons say "more likely
  to miss" or "less likely to miss". Test figures ("about 1 in 3") are only on
  the explanation page, now called How Kibaba decides.
- **No model terms on working pages:** model-run names and times are behind a
  closed "Technical details" on the member page; the pipeline steps read
  "Saving the page", "Matching names", "Hiding names", "Updating the records"
  and "Finding who to follow up".
- **More colour, in the Shanga style:** a landing page at `/` for visitors who
  are not signed in (what Kibaba does, three steps in bead rings, the three
  colours, officials and members, privacy); every page header is a colour
  block with a bead-collar corner and a beaded edge; the Overview opens with a
  tile per colour; member pages are tinted by colour; the sidebar keeps four
  main pages and puts the rest under More.
- **Simpler member page:** loans running first, past loans folded away.
- **Fixed:** the About page's scroll story no longer mismatches the server's
  HTML for readers who prefer reduced motion.
- **Fixed:** a database password holding `@` or `/` no longer breaks the
  connection address.

### Added — Sprint III

- **Model registry (S-8, D-030):** `register-model` puts the chosen model in
  the MLflow registry with the alias `champion`; scoring loads it by alias and
  each score records the version and a SHA-256 of the model's files.
- **Chama A as the test chama (D-029):** `test_only: true` keeps a chama out
  of the modelling tables; `reading_notes` add a chama's own column layout to
  the reading instructions for its scans only; `evaluate-chama chama_a` tests
  the model trained on chama B on it and logs the result to the MLflow
  experiment `chama-missed-repayment-held-out`.
- **Data drift report (S-7, D-031):** `drift --chama <id> --months 12` compares
  the model's 17 inputs in recent meetings with the rows it learned from, with
  Evidently; the HTML report goes to `data/reports/drift/` and MLflow.
- **HTTPS release (D-032):** `deploy/huggingface/` (Dockerfile, start script,
  Space README) and `docs/deployment.md`; `deploy-bundle` writes the private
  bundle (demo chama and champion model, checked for real names);
  `deploy-publish` sets up the private dataset and the Space from `.env`; the
  image installs the project's exact library versions (`constraints.txt`) and
  runs its own PostgreSQL, loaded with the demo chama and its two accounts at
  each start (D-033); `CHAMA_ONLY` and `MODEL_BUNDLE` settings for the cloud.
- **The release on the laptop (D-034):** Hugging Face now charges for Docker
  Spaces, so `serve-release` runs the release on the laptop for an ngrok tunnel,
  with its own database holding only the demo chama.
- **Sprint III records:** `docs/traceability.md` (objectives to requirements to
  tests) and `docs/usability_test.md` (tasks, questionnaire, record sheet).

### Added — Kibaba, the web interface (D-026, D-027, D-028)

- **Pages** (`frontend/`, Next.js 16, TypeScript, Tailwind CSS 4, Motion), in
  the Shanga beadwork style: sign-in with the bead collar; for officials the
  Overview (bead strands per band that move when scores change, members to
  follow up, chama health, a "new scores" banner checked every 60 s), the
  Members list (sort, filter by band and search, kept in the address), the
  Member page (band, what it meant in testing, top 3 reasons, where the score
  comes from, loans, repayments, contributions), About the scores (a scroll
  story of how members are put in bands), Records (meetings list and meeting
  page beside its photo), Scan a page, Scan status, Review and correct, the
  Pipeline run timeline, Upload history and the Edit record; for members My
  summary and My loans (MEM-2, brought forward from Sprint III). Loading, empty, error and "not allowed" states; a web app manifest
  so officials can add it to a phone's home screen. A short key to the bands
  (what each meant in testing, with a link to About the scores) wherever bands
  appear. No "demo" wording on any page; the demo chama's fictional names are
  explained in the report (D-028).
- **API** (`src/chama/web/`, FastAPI): sign-in through Supabase Auth exchanged
  for the server's own HttpOnly session cookie and CSRF token; one role check
  per route that takes the chama and member from the account, never the
  address; error messages with a reference that also appears in the log; a
  request log and `web-stats` for page times; `/api/health`.
- **Worker** (`python -m chama.web.worker`): jobs from `app.jobs` with
  `FOR UPDATE SKIP LOCKED`; reads scanned photos with the extraction provider
  (retrying rate limits up to 3 times), and after Accept runs ingest, names,
  anonymise, checks and score, one run at a time.
- **Tables** (`sql/02_app.sql`): accounts, sessions, uploads, jobs, drafts,
  flags, name matches, the insert-only edit record (a trigger refuses changes
  and deletes), pipeline runs and steps, risk scores and the worker heartbeat.
  Constraints stop a second upload of the same photo or form, a second job of
  a kind and a second run per upload.
- **Commands**: `score` (bands and plain-word reasons for each chama's latest
  meeting, saved with the meeting, model run and time), `demo-chama` (chama B
  with fictional names, D-028), `web-user add | list | deactivate | codes`
  (adding a deactivated email again reopens it with the new details),
  `web-stats`.
- **Docs**: `docs/web_setup.md` (Supabase, the demo chama, accounts, running
  it), `docs/m4_test_record.md` (T1 to T10: the automated tests and manual
  checks for each) and the master prompt as `docs/m4_master_prompt.md`.
- **Tests**: reason sentences for every model feature, fictional names,
  sign-in, sessions, CSRF and every role against the routes, scan rules, and
  database rules on a separate `chama_test` database (skipped without Docker).

### Changed

- `excel_loader.raw_files` also reads accepted scans,
  `data/raw/<chama>/scans/scan-<upload>.xlsx`, so a reload keeps them (S-3).
- `export` leaves demo chamas out of the modelling tables.
- `ExtractionFailed` says whether trying again may work (rate limit, outage).
- The extractor offers only the X25519 key exchange: the laptop's network
  dropped OpenSSL 3.5's larger post-quantum handshake to Groq, so every read
  timed out (certificates are still checked).
- `pyproject.toml` gains a `web` extra; `.env.example` the web settings;
  `config/pipeline.yaml` chama names and `chama_demo`.

## M3 — branch `m3-mlops` (merged)

### Changed — free open-weight extraction provider (D-025)
- Extraction runs by default on the open-weight Qwen 3.8 27B model on Groq's
  free plan; the Claude API (paid) is kept as a second provider for
  comparison.
- `extractor.py`: `OpenAICompatibleExtractor` (Groq, or any OpenAI-style API
  with image input) beside `ClaudeExtractor`, chosen by `make_extractor` from
  `extraction.provider`; clear messages for a missing key, rate limit and a
  request too large for the plan.
- `schema.py`: `page_schema` writes the layout out in full for APIs that do
  not follow JSON Schema references.
- `extract` and `extract-eval` take `--provider`; saved extractions and the
  evaluation files are kept per provider, so two providers can be compared on
  the same pages.
- `config/pipeline.yaml`: `extraction.providers` (groq, claude);
  `pyproject.toml`: `httpx` in the `extraction` extra; `.env.example`:
  `GROQ_API_KEY`.
- Tests for the new extractor with a fake HTTP transport (no request leaves
  the test), the full layout schema and the provider choice.

### Added — ledger photo extraction (D-024)
- `src/chama/extraction/`: a vision model reads a ledger photo into the raw
  layout through the Claude API, values exactly as written.
  - `schema.py`: the structured output, built from `raw_format.py` so the
    rows have the typed files' columns; `page_to_frames` turns a page into
    raw-layout tables.
  - `prompt.py`: the typing rules of `docs/data_dictionary.md`, for the model.
  - `images.py`: checks that an upload really is an image, turns it upright,
    shrinks it to the model's largest useful size and drops EXIF data.
  - `extractor.py`: `ClaudeExtractor`, with a clear message for each failure
    (key rejected, rate limit, service down, answer cut off, refusal), and a
    server-side fallback model if the first declines.
  - `checks.py`: flags lines to look at (hard to read, not an amount, balance
    jump, does not add up), each rule tried on the typed lines first.
  - `evaluate.py`, `run.py`: line the extracted rows up with the typed rows
    of the same photo and score them cell by cell.
- Commands: `extract <photos>` and `extract-eval [--pages] [--sample] [--refresh]`.
- `extraction` settings and each Chama's `photos_dir` in `config/pipeline.yaml`;
  the `extraction` extra in `pyproject.toml` (`anthropic`, `pillow`);
  `ANTHROPIC_API_KEY` in `.env.example`.
- Tests in `tests/test_extraction.py` (made-up rows, a fake API client).
- README: data protection, setup and a section on reading ledger photos.

### Found
- On the 1,799 typed lines: 13% do not add up in the ledger itself and 29%
  differ from the last page's balance, so those checks are a hint or dropped;
  a perfect extraction gets a "check" flag on 3.1% of lines (D-024).

## M2 — branch `m2-features-models` (merged)

### Added — Milestone 2 report
- `docs/milestone_2_report.md`: the working method, data correction, both
  targets, features, models and imbalance strategies, testing, results,
  the chosen model, risk bands, explanations, limitations, commands and the
  plan for M3, with every run of the final batch and the sensitivity check.
- README: M2 marked done, link to the report.

### Added — the chosen model (D-023)
- `chosen` per target in `config/pipeline.yaml`: random forest without an
  imbalance correction, for both targets.
- `chama.models.chosen`: `chosen_run` (the chosen model's run from the latest
  batch) and `chosen_model` (its fitted model and band cut-offs), for
  notebook 03 and the M4 dashboard. Tests in `tests/test_chosen.py`.
- Notebook 03 explains and scores with the chosen model.

### Changed
- Random forest leaves hold at least 20 rows (was 5), after a sensitivity
  check of depth and leaf size on the walk-forward test (D-023).

### Found
- Early warning, chosen model: walk-forward PR AUC 0.323 (0.27–0.38) against
  0.20; risk bands missed 11.9% / 23.8% / 35.1% of the time in testing.

### Changed — risk bands set by share (D-022)
- `band_shares` per target replaces the fixed `risk_bands` cut-offs: top 20%
  high, next 30% medium. Each run computes its score cut-offs from its
  walk-forward scores and logs them (`band_cutoff_medium`, `band_cutoff_high`);
  the band table gives each band's event rate with a bootstrap 95% interval.
- New run metrics `low_band_event_rate` and `high_to_low_rate_ratio`.
- Notebook 02 shows the band table of the best run; notebook 03 shows what
  each band meant in testing and scores open rows with the run's cut-offs.

### Added — a second target: early warning of missed repayments (D-021)
- `analytics.member_months` (dbt): one row per member per meeting while a loan
  runs, with features known after the meeting and `missed_ahead` (a repayment
  missed in the next `warning_horizon_meetings`, 3). 1,187 known rows, 222
  events. Meetings are counted in order, not by page number (p051 is not
  used). dbt unit test with a page-number gap.
- `export` writes both modelling tables, each checked and with a manifest.
- `src/chama/models`: a `Target` describes each target (table, label, time,
  features); tests, imbalance strategies, prior correction, SHAP and MLflow
  work for both, each target in its own MLflow experiment. Runs are tagged
  with their `training_batch`.
- `python -m chama.pipeline train --target ...`; notebooks 02 and 03 take a
  `TARGET`, 01 explores both tables, 03 explains the best run of the latest
  batch.

### Changed
- Loan-default features use money only as ratios (D-020 update): `amount` and
  `outstanding_at_issue` replaced by `outstanding_vs_amount`.
- Settings under `modelling:` are shared, with one block per target under
  `modelling.targets` (`min_training_events` replaces `min_training_defaults`).

### Found
- The early-warning target ranks future missed repayments above chance
  (walk-forward PR AUC 0.31, interval 0.26–0.37, against 0.20; ROC AUC 0.65);
  loan default still does not (ROC AUC about 0.5). Details in D-021.

### Added — modelling table and export (Milestone 2 start)
- `analytics.loan_features` (dbt): one row per loan with features known when
  it was given (earlier loans, loans open at issue, recent repayments and
  contributions, size against the member's and the Chama's loans) and a
  provisional label `defaulted` from `default_statuses` in
  `config/pipeline.yaml` (decision D-018). A dbt unit test checks that nothing
  after the issue month is used.
- Warning test `loan_continues_under_another_member`: a lost-track loan whose
  balance is picked up by another member's new loan, usually one person under
  two unlinked spellings. 15 found in Chama B (three pairs of codes).
- `python -m chama.pipeline export`: writes the modelling table and a manifest
  (rows, label rule, git commit) to `<DRIVE_DIR>/data` for Colab, after checking
  every column is cleared for export and no value holds a member's name
  (decision D-016). Tests in `tests/test_export.py`.
- `pyarrow` dependency; `ml` extra (scikit-learn, imbalanced-learn, XGBoost,
  SHAP, MLflow, matplotlib). `*.parquet` ignored by git.
- Decisions D-016 to D-019: Colab and Drive with a codes-only boundary, private
  repository, point-in-time features and provisional label, MLflow from M2.

### Added — training, testing and explanation
- `loan_features.outcome_month`: when each outcome became known, so a test
  year learns only from outcomes known before it. dbt unit test extended.
- `src/chama/models/`: three models (logistic regression, random forest,
  XGBoost) × four imbalance strategies (none, class weights, k-means SMOTE,
  k-means cluster centroids; resampling inside training folds only);
  walk-forward test 2019–2024 and a members-held-out check; PR AUC, ROC AUC
  and Brier score with bootstrap intervals; risk bands; SHAP explanations
  (decision D-020). Settings under `modelling:` in `config/pipeline.yaml`.
- `python -m chama.pipeline train`: runs every combination and logs each to
  MLflow (params, data version, metrics, plots, scores, the final model).
  Tests in `tests/test_models.py` (made-up loans).
- Notebooks `01_explore_features`, `02_train_and_compare`, `03_explain_risk`,
  runnable in Colab (first cell mounts Drive and fetches the code with a
  token from Colab Secrets) and locally.
- `DRIVE_DIR` in `.env` (replaces `EXPORT_DIR`): the project folder on Google
  Drive, holding `data/` and `mlruns/`.

### Changed — testing after the name review was fixed
- The name review again links the six split member codes (12 members): 263
  loans, 7 lost track, 28 provisional defaults, matching the M1 report.
- Prior correction (`PriorCorrectedPipeline`): models trained with class
  weights or k-means resampling have their scores moved back to the real
  share of defaults, so the Brier score and risk bands are comparable. Test
  in `tests/test_models.py`.
- Walk-forward test years 2018–2024 with at least 5 known defaults before
  each (was 2019–2024, 8): 22 test defaults instead of 12.
- First results recorded in D-020: no model ranks future loans reliably
  (walk-forward ROC AUC 0.50–0.55); tree models reach 0.62–0.68 with members
  held out; no imbalance strategy wins on both tests.

### Changed
- The GitHub repository is private (D-017).
- D-016: the officials confirmed that their permission covers keeping the
  codes-only table on Google Drive.

### Found
- The database built from the merged M1 code gives 277 loans, 17 member codes
  and 21 lost-track loans, not the 263, 13 and 7 in the M1 report. About 11 of
  the lost-track loans continue under a second code for the same person;
  their spellings need linking in the name review.

## M1 — branch `m1-data-pipeline` (merged)

### Added — the whole ledger extracted (2021 to April 2026)
- **2021–2026 extracted** from photos p086–p149 into `2021.xlsx` … `2026.xlsx`
  (local only). With 2014–2020 the ledger is complete: 148 meetings (January
  2014 – 5 April 2026), 1,799 member lines, 174 listed loans. Every page's
  doubts are listed in the extraction log.
- Extraction rules 16–19 (new loan written only as the balance after, penalty
  lines, struck-through lines, the separate interest column from July 2022).
- Cleaning: a new loan written only in the balance-after column is a
  `loan_given` line; a payment with no loan before or after is
  `repayment_only`; a line with only a contribution note is `no_loan`; `=`
  means nothing; `Er` is an emergency mark; dates such as "September 1st 2024"
  are read. dbt unit tests cover these.
- Loan linking prefers an earlier line of the same loan type (decision D-015);
  `loan_lines.opening_balance` for loans that open in the balance-after column.
- `docs/milestone_1_report.md` rewritten as the full Milestone 1 report.

### Found in 2021–2026
- Normal loans grew from about 45,000 (2014) to 250,000–350,000 (2023–2025)
  and are repaid over two years or more, so the 12-month rule marks many of
  them late or overdue. To discuss with the Chama before defining default.


### Added — 2016 to 2020 extracted
- **2016–2020 extracted** from photos p025–p085 into one workbook per year
  (local only): 60 meetings, 710 statement rows, 55 listed loans. p048 (Dec
  2017) is blurred; its retake p051 is typed under p048 (extraction rule 13).
  What to check on each page is in the extraction log.
- Cleaning: a written month without a day ("May 2016", "Nov/17") dates a
  page (`date_source = written_month`); a due year cut off to three digits
  counts as no year; `E` / `(E)` is an emergency mark; "Cleared" in the due
  column is not flagged; a line with an unreadable value is no longer taken
  for a new loan.
- Loans: a balance-only line can continue an open loan; new status
  `topped_up` (an unpaid balance rolled into a bigger loan of the same member,
  with `rolled_into_loan_id`); the "balance grows too much" check allows 1%
  for rounding.
- Extraction rules 13–15 (retakes, cut-off due years, emergency marks).

### Found in 2016–2020 (to raise with the Chama)
- From 2017 emergency loans run 2–3 months at 3% rather than being repaid at
  the next meeting at 5%; `emergency_term_days: 31` marks most of them late.
- One member stops appearing after January 2020 with 89,640 outstanding; two
  normal loans are overdue at the end of 2020.


### Added — 2015 extracted; closing Milestone 1
- **2015 extracted** from photos p013–p024 into `data/raw/chama_b/2015.xlsx`
  (local only): 12 meetings, 141 statement rows, 12 new loans; 20 rows flagged
  unclear. Details and what to check in the extraction log.
- `Statements.loan_type` for the emergency mark beside a name (`Em`, `Eme`,
  `(Em)`), standardised in `analytics.statements` and used for the loan type
  (decision D-013). `2014.xlsx` got the empty column (backup kept as
  `2014.xlsx.bak`).
- `add_missing_columns()` in `db.py`: ingest and anonymise add new columns to
  existing raw and staging tables.
- Cleaning: `Cleared` as a balance is 0; lines of dashes only are `no_loan`;
  dates in words (`7th June 2015`) are read; `/-` after an amount is dropped.
  dbt unit tests cover these.
- Extraction rules 8–12 in the data dictionary (tick marks, loan type mark,
  `Cleared`, names partly outside the photo, ambiguous figures).
- Decisions D-012 (loan term 12 months; later written due months are
  extensions), D-013 (loan type column) and D-014 (M1 closes with Chama B).
- `docs/milestone_1_report.md`: what was built, decisions, stack, commands.


### Added — the whole pipeline in one command (issue #13)
- `python -m chama.pipeline all` runs schemas, ingest, name check, anonymise
  and clean in order (decision D-011). It stops with instructions when new
  name spellings need review.
- A rebuilt, empty database is filled by `all` alone: reviewed names are
  restored from `data/interim/aliases_<chama>.csv`; `load-aliases` now marks
  every loaded row `reviewed`. Tested on an empty database with fake data.
- `create_schemas()` runs `sql/*.sql`, so `all` also works on a database not
  created by Docker. README: step table, the review loop and how to start
  again from an empty database.
- Tests for the review file (45 pytest tests in total).

### Fixed
- `anonymise` now always writes all four staging tables, empty where no
  workbook has that sheet; before, a missing Attendance sheet broke `clean`.


### Added — cleaning, loans and data checks with dbt (issues #10, #11, #12)
- dbt project `transform/` (decision D-009) building the `analytics` schema:
  `meetings`, `statements`, `new_loans`, `attendance` with typed values and
  an `issues` column for anything unreadable (#10); `loan_lines` and `loans`
  rebuilding each loan from the ledger lines (decision D-010) with due month,
  outstanding balance at the due month and a status (#11); `quality_report`
  with counts per Chama and year (#12).
- Every page gets a meeting month: written, from the previous page's "next
  meeting" note, or estimated from the nearest dated page.
- 33 dbt data tests (stop on structural problems, warn on ledger
  inconsistencies such as a balance not carried forward) and 3 dbt unit tests
  for the parsing, dating and linking rules.
- `clean` step runs `dbt build`, then prints the quality report and saves it to
  `data/processed/quality_report.csv`; `dbt` step runs any dbt command with
  `.env` loaded. `chama/cleaning/transform.py`, `chama/validation/report.py`.
- `emergency_term_days` in `config/pipeline.yaml`; `dbt-postgres` added to the
  dependencies. Test for the report layout (43 pytest tests in total).

### Found in the 2014 data
- Written due months for normal loans are about 15 months after the loan was
  given, not the 12 in `loan_term_days: 365`. To confirm with the Chama.
- A member's page-2 line (46,000 -> 44,000) is under a separate member code
  from the same balance on pages 1 and 3: likely one person, two spellings.


### Added — name matching and anonymisation (issues #8, #9)
- `suggest-aliases` step (`anonymisation/aliases.py`): groups the different
  spellings of each member (initials, swapped order, spelling slips, a missing
  name) and writes a review file `data/interim/aliases_<chama>.csv` with a
  suggested `canonical_name`, a `status` (`new`, `check`, `reviewed`), a match
  score, and `similar_to` for new members whose name is close to another's.
  It will not overwrite a review file that has not been loaded yet.
- `load-aliases` step: loads the reviewed file into `private.member_aliases`;
  stops on rows with no name or one spelling given two names.
- `anonymise` step (`anonymisation/anonymise.py`): copies raw to `staging` with
  `member_code` instead of `member_name`, fills `private.member_codes`, leaves
  free text in `raw` (decision D-008) and stops if any member's name is found
  in staging or any spelling has not been reviewed.
- Pipeline command line rebuilt with **click**: `python -m chama.pipeline --help`.
- `table_exists()` helper in `db.py`; `StepFailed` for planned stops with a
  short message instead of a traceback.
- Tests for name matching (13) and anonymisation (14); 42 in total.

### Changed — name matching and anonymisation
- `private.member_aliases.raw_name` holds the normalised spelling.
- `click` added to the dependencies (`pip install -e ".[dev]"` again).

### Changed
- **Raw Excel layout now mirrors the ledger** (decision D-006). The sheets are
  `Statements` (one row per member per meeting), `Meetings` (one row per page),
  `NewLoans` (one row per loan given) and `Attendance`. They replace the earlier
  `Loans`, `Repayments`, `Contributions` and `Notes` sheets, which did not match
  how the Chama records its data. Defined in `src/chama/ingestion/raw_format.py`;
  every column is described in [docs/data_dictionary.md](docs/data_dictionary.md).
- **One Excel file per Chama per year** (decision D-004). `config/pipeline.yaml`
  now gives each Chama a folder (`raw_dir`) instead of one file; the loader reads
  every `.xlsx` in that folder in name order and combines them.
- Chama B's records start in **2014** (previously noted as 2015).
- README setup uses **conda** (Miniconda) instead of `venv`.
- **Simpler git workflow** (decision D-007): one branch per milestone
  (`m1-data-pipeline` … `m5-report`) plus `housekeeping`, replacing one branch
  per issue. Pull request template now has an *Issues* section, a title
  convention and a CHANGELOG check. Steps in [docs/git_workflow.md](docs/git_workflow.md).
- Loader tests rewritten for the new layout (15 tests).

### Added
- `read_folder()` and `raw_files()` in the loader; skips Excel's `~$` temporary
  files and the empty template.
- Ledger photos for Chama B: 149 pages (early 2014 to April 2026) renamed in the
  order they were taken to `chama_b_p001.jpg` … `chama_b_p149.jpg`, with
  `data/photos/chama_b/photo_manifest.csv` linking each new name to its original
  WhatsApp file name (decision D-005). Photos stay local and are never committed.
- `CHANGELOG.md`, `docs/decisions.md`, `docs/data_dictionary.md`,
  `docs/extraction_log.md`.
- **2014 extracted** from photos p001–p012 into `data/raw/chama_b/2014.xlsx`
  (local only): 12 meetings, 167 statement rows, 22 new loans; 30 rows flagged
  unclear for checking against the paper. Details in the extraction log.

### Fixed
- Removed a duplicated `config = load_config()` line in `pipeline.py` and a stray
  blank line in `raw_format.py` (accidental edits).

## 2026-09-26 — Raw format, template and loader checks (PR for issues #5, #6)
### Added
- `raw_format.py`: single definition of sheets and columns, with tracking
  columns `source_photo` and `unclear` on every sheet.
- `template.py` and `scripts/make_raw_template.py`: generate an empty raw
  template with a README sheet.
- Loader reports missing and unexpected columns per sheet before loading, keeps
  all values as text and records each row's Excel row number.
### Note
- The commit message says `(#N, #M)` by mistake; the pull request description
  carries the correct issue links.

## 2026-09-26 — GitHub templates and M1 backlog (issue #3, PR #4)
### Added
- Pull request template with *Problem*, *Remedy* and *How I checked it* sections.
- Bug template with a *Remedy* section to fill in when closing.
- `scripts/create_m1_issues.ps1`: creates the nine Milestone 1 issues.
- Labels (`data-pipeline`, `modelling`, `mlops`, `dashboard`, `docs`, `chore`)
  and milestones M1–M5 on GitHub.

## 2026-09-26 — Safer database container (issue #1, PR #2)
### Changed
- `docker-compose.yml` passes only the database settings to PostgreSQL instead of
  the whole `.env` (which holds the pseudonym key), makes the port configurable
  and adds a health check.

## 2026-09-25 — Initial project structure
### Added
- Folder layout, `pyproject.toml`, `.gitignore` (blocks photos, Excel, CSV and
  `.env`), `.gitattributes`, `.env.example`, Docker Compose PostgreSQL 16.
- Database schemas `raw`, `private`, `staging`, `analytics` (`sql/01_schemas.sql`).
- Name-to-code step (`pseudonymise.py`) using HMAC-SHA256, with 7 tests.
- Excel loader, pipeline runner, PlantUML data-flow diagram, issue template.
