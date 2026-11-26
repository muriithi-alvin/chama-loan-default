# Final report: plan and alignment record

## Status (3 Nov 2026)

- **Draft:** [MuriithiAlvin_166326_Final_Report_DRAFT.docx](MuriithiAlvin_166326_Final_Report_DRAFT.docx).
  Chapters 1 to 3 and the reference list are rewritten to match the built system. Chapter 4
  onward is still the proposal's text and is marked in yellow. The abstract is left for last.
- **Open items are in the draft:** yellow highlights and 12 Word comments mark what needs the
  author or the supervisor (title, reason for no M-Pesa or bank data, reworded objectives,
  chama A, permission and consent, usability sessions, Table 3.4).
- **Figure 2.1** is drawn by [figures/conceptual_framework.py](figures/conceptual_framework.py).
- **Next:** Chapter 4 diagrams and requirements, then Chapter 5.

Working record for Milestone 5, started 3 Nov 2026. It compares the proposal
(`MuriithiAlvin_166326_Prof.VOmwenga`, the Word file of 24 Oct 2026, same content
as the PDF) with what the repository shows was built, against the course guide
(*Research Writing for CS 2 Projects 2026*). It holds no member names.

Every "built" entry was checked against the code or a recorded decision (D-xxx in
`decisions.md`). Nothing here is a result that has not been measured.

## 1. Where the proposal no longer matches the system

The guide requires the report to describe the actual methods and to keep the problem,
objectives, implementation and evaluation aligned. The proposal is already written in
the past tense, so each row below currently reads as a claim that the work was done.

### Needs a decision first

| # | Proposal says | Where | What the project shows | What the report needs |
| --- | --- | --- | --- | --- |
| 1 | Data from M-Pesa statements, bank records and ledgers; "multi-source" | Title, abstract, 1.1, 1.5, 1.6, 1.7.2, 3.2.1, 3.6.1, FR-1(a, b), 4.2.3.1, Fig 2.1, Table 2.1 | One kind of source: handwritten ledger pages, typed (chama B, 149 photos, 13 workbooks) or scanned. No M-Pesa or bank code exists. No decision records why | **Your reason, and a title decision with the supervisor** (section 5) |
| 2 | Predicts loan default | Title, abstract, 3.6.4, RQ v | Loan default does not rank future loans reliably: ROC AUC 0.535, PR AUC 0.228 against 0.165 by chance, on 28 provisional defaults. An added target works: a missed repayment within 3 meetings, PR AUC 0.323 (0.27–0.38) against 0.20, ROC AUC 0.670 (D-021, D-023) | Report both; state the negative result as a finding |
| 3 | Evaluated in a pilot chama, with treasurers in user acceptance testing; compared with manual or single-source methods | Objective v, RQ v, 4.2.2.4, 4.2.5 | Test kit ready (`usability_test.md`), no sessions recorded. Chama A not loaded (`data/raw/chama_a` is empty). No comparison with a manual or simple method exists | Run them, or report them as not done (section 3) |

### Rewrite to match what was built, giving the reason

| # | Proposal says | Where | Built instead | Evidence |
| --- | --- | --- | --- | --- |
| 4 | Attendance as a predictor | 1.5, 3.2, 3.6.3, FR-8(c) | The layout has an Attendance sheet, but no attendance was recorded, so no such feature exists | M2 report 7.6 |
| 5 | A default probability for each member; low, medium, high | FR-17, FR-18, 3.6.5, 3.6.6 | No score or percentage shown. Three bands in plain words: Follow up now, Keep an eye on, Less likely to miss. Scores rank but are not reliable probabilities | D-022, Sprint II feedback |
| 6 | Stratified k-fold and an 80/20 hold-out | Abstract, 3.2.3, 3.2.4, 4.2.3.4 | Walk forward by year, members held out (5 grouped folds), bootstrap 95% intervals. A random split would learn from the future | D-020 |
| 7 | Grid Search and Optuna | 3.2.3, FR-13 | Fixed cautious settings and a sensitivity check over depth and leaf size | D-023, M2 Appendix B |
| 8 | SMOTE applied to the training data | 3.2.2, 4.2.3.4 | k-means SMOTE and cluster centroids compared with no correction and class weights; none adopted | D-020, D-023 |
| 9 | Synthetic data with SDV | 3.2.1, abbreviations | Not used. The demo chama is chama B's records with fictional names, for demonstrations only | D-028 |
| 10 | All personal identifiers removed before processing | 3.2.1 | Names stay in the restricted `raw` and `private` layers; HMAC codes from `staging` on. Photos showing names go to Groq with the officials' permission | D-001, D-002, D-008, D-025 |
| 11 | Airflow or Prefect | 3.7.2 | One command, `python -m chama.pipeline all`, and a worker reading jobs from PostgreSQL | D-011, D-027 |
| 12 | Streamlit dashboard | Abstract, 3.5.6, 3.6.6, 3.7.11, Fig 2.1 | Kibaba: Next.js pages, FastAPI API, job worker, Supabase sign-in | D-026, D-027 |
| 13 | Docker packaging, automated deployment, CI/CD | Abstract, 3.7.10, Fig 2.1 | PostgreSQL in Docker Compose. GitHub Actions runs lint, tests and a build, with no automated deployment. The release image was written but never built | D-032 to D-034 |
| 14 | Real-time scoring through an API, feature engine and SHAP service on each request | 1.2, RQ iv, 4.2.4.2, 4.3.2 and its sequence diagram | Batch: scores and reasons are computed after each accepted page and saved. No model runs while a page loads, so **the sequence diagram must be redrawn** | D-027, `web/services/scoring.py` |
| 15 | Actors: Treasurer, Loan Committee Member, MLOps Engineer, System Administrator | 3.5.1, 4.3.1, Fig 4.1 | Roles: official, member, admin. Members seeing their own records was not in the proposal, so **the use case diagram must be redrawn** | `sql/02_app.sql`, D-026 |
| 16 | Monitoring of data drift, concept drift and performance, with retraining triggers | 3.7.8, FR-23(b), FR-24, FR-25, Fig 2.1 | Data drift only, run on demand. Prediction distributions are not compared, and there are no triggers | D-031, `models/drift.py` |
| 17 | Lending-risk report (PDF export); feedback on predictions | FR-22, UC-03, UC-05 | Neither is in the code. Build small versions or report them as not implemented | Code search |

Also new since the proposal, and to be added: reading ledger photos with a vision model
and a human review step (D-024, D-025), the model registry (D-030), the name review
(D-011), loan reconstruction (D-010), and laptop-plus-ngrok deployment (D-034).

## 2. Errors in the proposal that do not depend on the build

- **References.** About 25 sources cited in the text are missing from the reference list,
  including FSD Kenya 2022, Huduma Global 2026, Andanje & Sakwa 2022, Ng et al. 2025,
  Amed et al. 2025, Creswell & Creswell 2018, Goodfellow et al. 2016, Patki et al. 2016
  and Kohavi 1995. Six listed sources are never cited: Breiman, Bussmann, Hosmer, Karlan,
  Polyzotis, Sambasivan. Polyzotis should be checked before it is kept: its DOI looks wrong.
  Several are news or company sites, which the guide says to avoid. Only 9 citations are
  live Zotero fields.
- **Requirement IDs.** Section 4.2.5 and 4.3.2 cite NFR-17, NFR-22 and DR-13 to DR-15, but
  no NFR, DR or IR identifier exists in the text. The guide requires unique IDs, and the
  repository's own IDs (G1, OFF-3, X10) also need mapping to FR-1 to FR-25.
- **Figures.** 4.3.1 reads "presented in provides" (the figure number is missing); 4.3.2
  says "Figure 3.3"; the sequence diagram has no caption and is unreadable at page size;
  the List of Figures omits Figure 4.1.
- **Wording.** FR-19(b) "were supported" should be "where supported"; a stray ")" in 4.1;
  Behavioral and Behavioural are mixed; "chama's" used as a plural in the abstract.
- **Layout.** Blank pages 6, 10, 20 and 39; near-empty pages 30, 34 and 37; headings 3.5.1,
  3.6.1 and 3.7.1 in the wrong font, the last two with no space after the number.
- **Abbreviations.** Unused entries such as LLM, RAG, WHO and SDV; new ones needed, such as
  PR AUC, CSRF, HTTPS.
- **Front matter.** Cover date, declaration dates and both signatures need redoing for the
  final version; the Gantt chart and Turnitin report need redoing at the end.

## 3. Evidence Chapter 5 needs that does not exist yet

| # | Item | State today | Who |
| --- | --- | --- | --- |
| 1 | Extraction accuracy from `extract-eval` | **No result saved.** No `extraction_eval_*.csv`, and D-024 and D-025 give no figure. The only record is one typed page on 24 Oct | Claude can run it: about 10 pages at one a minute, sending photos to Groq as D-025 allows |
| 2 | Precision, recall and F1 | Promised in 3.2.4 and 4.2.2.6; the code computes PR AUC, ROC AUC and Brier only | Claude, from the saved walk-forward scores in MLflow |
| 3 | A simple baseline to compare the model with | None besides chance. The guide asks for a meaningful baseline, and RQ v asks about manual methods. A rule such as "missed in the last 3 meetings" can be scored on the same test rows | Claude |
| 4 | Usability sessions (3 officials, 3 members) | Not run; no results recorded | Alvin |
| 5 | Chama A held-out test | Pages not loaded; officials' meaning of "missed" not confirmed | Alvin, then Claude |
| 6 | HTTPS release through ngrok | `serve-release` rehearsed with a placeholder address. The tunnel, a real sign-in and a scan were unverified at last record | Alvin starts the tunnel; Claude helps check |
| 7 | Manual checks T1, T2, T3, T4, T5, T7 | Marked "to do" in `m4_test_record.md` (last updated 27 Oct) | Together, on the running site |
| 8 | Check against the paper ledger (#7) | Pending for all 13 years | Alvin, on a sample if not all |
| 9 | Chama's answers on the default label, large-loan term, lost-track loans and follow-up numbers | Open since M2 section 21 | Alvin |
| 10 | Drift figure | D-031 says 11 of 17 inputs drifted; the saved CSV shows **12 of 17**. Report the CSV's figure and correct D-031 | Claude |
| 11 | Full test run at the freeze | 241 tests collected today; last recorded 235 passed on 2 Nov | Claude |
| 12 | AI-use log and one checked AI suggestion | **None in the repository.** Required by the guide and by Sprint II. M2 report 3.2 has the start of it. This report's drafting belongs in it too | Alvin and Claude |
| 13 | Feedback-resolution matrix | Only the Sprint II comments are on record; written and oral proposal feedback are not | Alvin supplies; Claude tabulates |
| 14 | Screenshots of each main page | None in the repository | Claude, with the demo chama only |

If an item in rows 3 to 9 is not done, the report says so under limitations. It is not
written as if it happened.

## 4. Report structure

Follows the guide's Semester II chapters. Chapter 5 uses its hybrid route: data, then model,
then application.

| Chapter | Work | Main sources |
| --- | --- | --- |
| Front matter | New date, signatures, abstract **written last**, updated lists | Guide |
| 1 Introduction | Revise the claims in rows 1 to 3; keep objectives in the infinitive; tighten the problem statement to the guide's half page | Section 1 above |
| 2 Literature review | Mostly stands. Fix references; add literature for what is new (handwriting extraction, walk-forward validation, the imbalance and calibration studies in D-020); redraw Fig 2.1 | D-020, D-024 |
| 3 Methodology | Rewrite 3.2 to what was done; shorten 3.5 and point to Chapter 4; rewrite 3.6 and 3.7. Agile, OOAD and MLOps stand, with sprints as actually run | Section 1, milestone reports |
| 4 Analysis and design | Add NFR, DR and IR identifiers; amend requirements with reasons. **Analysis:** use case, activity, sequence. **Design:** class, logical database schema, architecture, data pipeline, wireframes | `sql/`, `transform/`, `frontend/`, `data_pipeline.puml` |
| 5 Implementation, testing, evaluation | 5.1 Introduction · 5.2 Environment (Table 5.1) · 5.3 Dataset description · 5.4 Pipeline · 5.5 Model training and evaluation · 5.6 Ledger reading · 5.7 Kibaba · 5.8 Testing (T1 to T10, Table 5.3, CI) · 5.9 Usability · 5.10 Deployment · 5.11 Version control · 5.12 AI declaration · 5.13 Results by objective, discussion, limitations | M1 and M2 reports, `traceability.md`, `m4_test_record.md`, `deployment.md`, D-001 to D-034 |
| 6 Conclusions | Answer the objectives in order, using only reported evidence; recommendations per audience; future work tied to limitations: mobile app, hosted deployment, M-Pesa and bank data, more chamas, an agreed default label, calibration, Google sign-in | Chapter 5 |
| Appendices | Gantt, Turnitin, traceability matrix, usability instruments, all 24 model runs, AI-use log | `traceability.md`, M2 Appendix A |

## 5. Decisions needed

1. **Why were M-Pesa and bank records not used?** Nothing in the repository says. Only Alvin
   knows, and the report must state it. This should also become a decision record.
2. **The title.** A title change is for Prof. Omwenga to approve, and it should go to him with
   rows 1 and 2.
   - Recommended, 17 words, inside the guide's 12 to 18: *Early Warning of Missed Loan
     Repayments in Kenyan Chama Groups: A Ledger-Based Data Engineering and MLOps Framework*.
   - Alternative: keep the approved title and explain both departures in Chapters 1 and 5. This
     is harder to defend, because the title then promises what the results do not show.
3. **Which of rows 3 to 9 in section 3 will happen, and by when?** The Gantt chart shows
   documentation due 1 to 21 Nov and the defence 22 to 28 Nov; confirm the real dates.
4. **Proposal feedback.** The written and oral comments, and anything from today's rehearsal.

## 6. Order of work

1. Decisions above; supervisor conversation on the title.
2. Run the measurements Claude can do alone (section 3, rows 1, 2, 3, 10, 11).
3. Chapter 4 diagrams, then Chapter 5, because they rest on evidence that already exists.
4. Revise Chapters 1 to 3 to match; fix references as they are touched.
5. Add usability and chama A results when they exist.
6. Chapter 6, then the abstract, front matter, lists, Gantt and Turnitin.

Word stays the master format: a working copy of the proposal file is edited, keeping the
template's styles, and the original in Downloads is left untouched.
