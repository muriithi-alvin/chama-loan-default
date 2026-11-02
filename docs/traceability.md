# Traceability record: objectives to tests

From each objective to the requirements that serve it, where they are built,
and the tests that check them. Requirement IDs (G1, OFF-3, X10 and so on) are
the ones in `docs/m4_master_prompt.md`; scenarios T1 to T10 and their manual
checks are in [m4_test_record.md](m4_test_record.md). Automated tests are in
`tests/` and the dbt tests in `transform/`. All run on every push (GitHub
Actions): 236 passed on 2 Nov 2026.

**Status:** Done; Partly (met with a stated gap); Cut (dropped after the
Sprint II review as not needed, now future work); Pending (built, waiting for
data or a manual check).

## 1. Objectives

The aim: a decision-support tool that tells chama officials which members to
follow up and why, from the chama's own ledger. It never approves or refuses
a loan (G2, N1).

| Objective | Requirements | Built in | Automated tests | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| **M1-1** Capture the paper records faithfully, each value traceable to its photo | S-3 | `ingestion/raw_format.py`, `excel_loader.py` (`source_photo` on every row) | `test_excel_loader.py` (values kept exactly as written, Excel row and chama kept) | M1 report §3–5 | Done |
| **M1-2** Protect members' identities: names become codes | X11, G5 | `anonymisation/` (pseudonym key, aliases), `private` schema, export name check | `test_pseudonymise.py`, `test_anonymise.py` (no name or free text reaches staging), `test_aliases.py`, `test_export.py` (a column not cleared stops the export) | D-001, D-016 | Done |
| **M1-3** Turn handwriting into typed, consistent data without hiding problems | OFF-10 | dbt staging and cleaning, extraction checks | dbt tests (`balance_after_is_plausible`, `balance_carried_forward`), `test_extraction.py` (checks flag the lines to look at) | M1 report data-quality section | Done |
| **M1-4** Rebuild each loan and its outcome (the ledger has no loan numbers) | S-4 | dbt `loans`, `loan_lines` (D-010, D-015) | dbt tests (`every_loan_line_has_a_loan`, `loan_continues_under_another_member`) | M1 report | Done |
| **M1-5** Check data quality automatically and report it | X4 | `clean` step and its report | `test_report.py`, the dbt tests | `python -m chama.pipeline clean` | Done |
| **M1-6** Make the whole process repeatable with one command | S-2 | `python -m chama.pipeline all`; GitHub Actions | the whole suite in CI | `.github/workflows/checks.yml` | Done |
| **M2-1** Agree the target with the chama | G3 | early warning of a missed repayment within 3 meetings (D-021); loan default kept back (D-018) | — | M2 report §6 | Partly: the early-warning label needs no agreement on loan terms; the loan-default definition is provisional |
| **M2-2** Build features from each member's history before the moment scored | S-4 | dbt `member_months`, `loan_features` | dbt point-in-time tests; `test_models.py` (walk forward learns only from outcomes known before the test year) | M2 report §7 | Done |
| **M2-3** Train and compare models suited to small data | — | `models/train.py` (3 models × 4 imbalance strategies) | `test_models.py` (every target, model and strategy gives scores between 0 and 1; prior correction) | MLflow experiments; M2 report §9, §12 | Done |
| **M2-4** Validate honestly | — | walk forward by year, members held out, bootstrap intervals (D-020); a chama the model never saw (D-029) | `test_models.py`, `test_held_out.py` | M2 report §10, §12; `evaluate-chama chama_a` | Done for chama B; chama A Pending its pages |
| **M2-5** Explain with SHAP and map scores to categories | G3, G4, OFF-3 | `models/explain.py`; bands by share (D-022); `web/services/reasons.py` | `test_web_reasons.py` (every model feature has a plain sentence; forbidden words never used) | M2 report §14–15 | Done |
| **M3-1** Read ledger photos | OFF-8 to OFF-10, S-2 | `extraction/` (Groq, Claude for comparison; D-024, D-025) | `test_extraction.py` (25) | `extract-eval` accuracy, `docs/extraction_log.md` | Done |
| **M3-2** Serve the model | S-4, S-6 | API and worker score each accepted page | `test_web_auth.py` (roles on every route) | live scoring after Accept (T3) | Done |
| **M3-3** Model registry | S-8 | `models/registry.py`, `register-model` (D-030) | `test_registry.py` | version 1 @champion, checksum saved with each score | Done |
| **M3-4** Monitoring | S-7 | `models/drift.py`, `drift` command (D-031) | `test_drift.py` | first report 30 Oct 2026 (MLflow `chama-missed-repayment-drift`) | Done |
| **M3-5** Containers | — | PostgreSQL in Docker Compose; the release image for the deployment | — | Sprint III deployment | Pending |
| **M4** Officials see who to follow up and why; members see their own records | G1 to G5, all OFF, MEM, X, S | `frontend/`, `src/chama/web/` (D-026 to D-028) | see section 2 | T1 to T10 | Done (see section 2 for the cuts) |

## 2. Requirements (web interface) to tests

| ID | Requirement | Built in | Automated tests | Scenario | Status |
| --- | --- | --- | --- | --- | --- |
| G1 | Officials see who to follow up and why; members only their own | Overview, member page, `/m` | `test_a_member_gets_not_allowed_on_officials_routes` | T2, T6 | Done |
| G2 | The system suggests, officials decide; no approve, reject or "defaulter" | wording on every page; band key | `test_sentences_are_plain_and_never_use_forbidden_words` | walkthrough | Done |
| G3 | Early warning only: a band and reasons, no score or percentage | `scoring.py` saves the band, never the score | `test_every_feature_of_the_model_has_a_template` | T2 | Done (bands renamed in plain words after Sprint II) |
| G4 | Every score shows where it came from | member page "Based on" and "Technical details" (model, registry version, checksum) | `test_registry.py` (checksum) | T2 | Done |
| G5 | Fictional names on a projector | demo chama (D-028), `DEMO_MODE` | `test_demo_mode_keeps_a_real_officials_name_off_screen`, `test_no_fictional_name_shares_a_word_with_a_real_name`, `test_demo_frames_rename_members_and_drop_free_text` | demo | Done |
| R1 | Official role | `auth.official` | `test_an_official_sees_only_their_own_chamas_members` | T1, T2 | Done |
| R2 | Member role | `auth.member` | `test_a_member_gets_not_allowed_on_officials_routes`, `test_the_footer_status_gives_members_no_score_details` | T6 | Done |
| R3 | Admin sets up chamas, users, roles | `web-user add/list/deactivate/codes` | `test_a_deactivated_account_can_be_given_another_member` | — | Partly: the command is done; the page (OFF-15) was cut |
| R4 | Every request checks the session and role | route dependencies, same-origin and CSRF checks | `test_without_a_session_every_page_says_the_session_ended`, `test_changes_need_the_sessions_csrf_token`, `test_changes_from_another_site_are_refused` | T6, T7 | Done |
| OFF-1 | Overview | `app/o/page.tsx` | — | T1 | Done |
| OFF-2 | Members list, filters kept in the address | `app/o/members/` | — | walkthrough | Done |
| OFF-3 | Member page | `app/o/members/[code]/` | `test_sentences_use_the_members_own_values` | T2 | Done |
| OFF-4 | Band history | — | — | — | Cut |
| OFF-5 | Meetings list | `app/o/records/meetings/` | — | walkthrough | Done |
| OFF-6 | Meeting page beside its photo | `app/o/records/meetings/[id]/` | — | walkthrough | Done |
| OFF-7 | Loans list | — | — | — | Cut |
| OFF-8 | Scan a page | `app/o/scan/`, `POST /api/uploads` | `test_uploads_are_refused_next_to_the_photo_field`, `test_the_same_form_sent_twice_returns_the_first_upload`, `test_the_same_photo_or_form_cannot_make_a_second_upload` | T3, T5 | Done |
| OFF-9 | Scan status | `app/o/scans/[id]/`, worker | `test_openai_style_extractor_explains_failures` | T3, T4, T8 | Done |
| OFF-10 | Review and correct | `app/o/scans/[id]/review/` | `test_flags_point_at_the_draft_row_and_use_plain_labels`, `test_accept_waits_until_every_name_is_matched`, `test_accept_refuses_a_meeting_already_in_the_records`, `test_name_suggestions_come_from_the_chamas_members` | T3, T10 | Done |
| OFF-11 | Pipeline run timeline | `app/o/runs/[id]/` | `test_one_pipeline_run_and_one_job_of_each_kind_per_upload` | T3, T9 | Done (plain step names after Sprint II) |
| OFF-12 | Upload history | `app/o/uploads/` | — | walkthrough | Done |
| OFF-13 | Edit record | `app/o/edits/`, insert-only table | `test_the_edit_record_cannot_be_changed_or_deleted` | T3 | Done |
| OFF-14 | About the scores (How Kibaba decides) | `app/o/about/` | — | walkthrough | Done |
| OFF-15 | Users page | — | — | — | Cut |
| MEM-1 | My summary | `app/m/page.tsx` | — | T6 | Done |
| MEM-2 | My loans | `app/m/loans/` | — | T6 | Done (brought forward from Sprint III) |
| MEM-3 | No scores, other members or photos for members | `auth.member`; members' API | `test_a_member_gets_not_allowed_on_officials_routes` | T6 | Done |
| X1 | Sign-in; an expired session says so | Supabase password check on the server, own session cookie | `test_sign_in_sets_an_httponly_session_and_a_csrf_cookie`, `test_wrong_password_is_refused_next_to_the_field`, `test_missing_email_is_refused_next_to_the_field`, `test_an_unknown_or_deactivated_account_gets_no_session` | T1, T7 | Done (Google sign-in cut) |
| X2 | Safe sessions | HttpOnly cookie, CSRF token, same-origin check | `test_signing_out_ends_the_session`, `test_changes_need_the_sessions_csrf_token` | T7 | Done |
| X3 | Loading, empty and error states | `loading.tsx`, `error.tsx`, empty states | — | walkthrough | Done |
| X4 | Plain messages with a reference | `web/errors.py` | `test_errors_never_show_a_stack_trace` | T5, T8 | Done |
| X5 | Accessibility | skip link, labels, bands as beads plus words (never colour alone), reduced motion | — | headless Chrome checks | Done, checked by hand; no automated accessibility test |
| X6 | Phone to desktop | responsive layout, bottom bar on phones | — | screenshots at 390 px | Done |
| X7 | Installable | `manifest.ts` | — | walkthrough | Done |
| X8 | Live updates | new-results banner (every 60 s), run timeline (every 2 s) | — | T3 | Done |
| X9 | Speed | built pages; scores read from a table, never computed while a page loads | — | T1 | Partly: pages load within 1 s; sign-in takes about 1.8 s at Supabase |
| X10 | Safe retries | idempotency key, unique constraints, `SKIP LOCKED` | `test_the_same_form_sent_twice_returns_the_first_upload`, `test_double_accept_starts_one_run`, `test_jobs_are_taken_once` | T8, T9 | Done |
| X11 | Data protection | codes in analysis, photos without location data, logs with codes only | `test_no_name_or_free_text_reaches_staging`, `test_large_photo_is_shrunk_to_a_jpeg_without_exif` | — | Done |
| S-1 | App tables | `sql/02_app.sql` | `test_web_db.py` (8) | — | Done |
| S-2 | Worker | `web/worker.py` | `test_jobs_are_taken_once` | T8 | Done |
| S-3 | Scans as a second raw source | `excel_loader.raw_files` reads `scans/scan-*.xlsx` | — | T3 (24 Oct run) | Done |
| S-4 | Scoring step | `web/services/scoring.py` | `test_web_reasons.py` | T2, T3 | Done |
| S-5 | Health check | `/api/health` | — | walkthrough | Done |
| S-6 | JSON API | `web/routes/` | role tests in `test_web_auth.py` | — | Done |
| S-7 | Data drift with Evidently | `models/drift.py` (D-031) | `test_drift.py` | — | Done |
| S-8 | Model from the registry by alias, checksum per score | `models/registry.py` (D-030) | `test_registry.py` | — | Done |
| N1–N5 | Out of scope: no approve or reject, no percentages or raw scores, no app, no payments, accepted pages not edited | — | `test_sentences_are_plain_and_never_use_forbidden_words` | — | Respected |

## 3. Sprint III course criteria

| Criterion | Where | Status |
| --- | --- | --- |
| A deployed HTTPS release | Hugging Face Docker Space with Supabase's free PostgreSQL, demo chama only: `deploy/huggingface/`, [deployment.md](deployment.md) | Pending: ready to deploy once the accounts exist |
| Traceability from objectives to tests | this record | Done |
| Usability testing with real users | [usability_test.md](usability_test.md) (script, tasks, questionnaire) | Pending: sessions with officials and members |
| Failure-path demos | T4 (not a ledger page), T5 (wrong file), T7 (session ends), T8 (service down) | T8 seen for real; T4, T5, T7 to show |
| Chapters 5 and 6, and a handover a stranger can follow | `docs/web_setup.md`; the report (M5) | Pending |
