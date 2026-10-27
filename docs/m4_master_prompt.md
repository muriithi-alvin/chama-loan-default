# Chama web interface (M4): master prompt

Oct 24, 2026 · @Alvin Muriithi

This is the master prompt for building the officials' and members' web interface of the Chama loan-default system, which replaces the Streamlit dashboard; the mobile app becomes future work. Items tagged \[S2\] are due for the Sprint II review on Oct 28, 2026; \[S3\] items come in Sprint III.

## How to use this prompt

Export this doc as Markdown to `docs/m4_master_prompt.md` in the `chama-loan-default` repository, then start Claude Code in that folder with:

```text
Read docs/m4_master_prompt.md in full and follow it. Begin with step 1 of "How to work": reply with your plan and the answers you need from me, and do not write code until I approve the plan.
```

Everything below this section is written to Claude Code. The IDs (G1, OFF-3, T9 and so on) stay fixed so they can become the Sprint III traceability table.

## 1. Context and how to work

You are building Milestone 4 of this repository: a web interface where chama officials see which members to follow up and why, and members see their own records. It replaces the planned Streamlit dashboard; the mobile app is future work.

### What already exists (read before planning)

| Piece | Where | What to reuse |
| --- | --- | --- |
| Project overview and data protection rules | `README.md` | The rules in "Data protection" apply to every page |
| Design decisions D-001 to D-025 | `docs/decisions.md` | Follow them; add D-026 (section 11) |
| Features, models, bands, explanations | `docs/milestone_2_report.md`, sections 7, 14 and 15 | Band meanings and the limits for OFF-3 and OFF-14 |
| Pipeline steps | `src/chama/pipeline.py` (`run_all`, `ingest`, `anonymise`, `clean`) | The worker calls these; do not copy them |
| Excel ingestion | `src/chama/ingestion/excel_loader.py` | `load_to_raw` deletes each chama's raw rows before reloading; see S-3 |
| Name matching and codes | `src/chama/anonymisation/` | New names in scans go through the same alias review |
| Ledger photo reading | `src/chama/extraction/` (`run.read_photo`, `checks.check_page`, `schema.py`) | The scan job and the review flags |
| The chosen model | `src/chama/models/chosen.py` (`chosen_model`) | Model, run and band cut-offs for scoring |
| Explanations | `src/chama/models/explain.py` (`shap_values`, `top_factors`) | Top 3 reasons per member |
| Settings | `config/pipeline.yaml` (`modelling.targets.missed_repayment`, `extraction`) | Target, band shares, extraction provider |
| Early-warning features | `transform/models/features/member_months.sql` and `.yml` | Exact meaning of each feature for the reason templates |

### How to work

1. **Plan first.** Read this prompt and the files above, then reply with: the folder and module plan, the new tables, the order of work, the risks to the Sprint II date, and your questions, including the open decisions in section 12. Write no code until Alvin approves.
2. **Build \[S2\] items only**, in this order, each a vertical slice that runs end to end:
   1. App tables, sign-in, roles, demo mode, layout and style (S-1, X1, X2, R1–R4, G5, X12)
   2. Scoring step and the pages that read it: Overview, Members list, Member page, About the scores (S-4, OFF-1 to OFF-3, OFF-14)
   3. Records: meetings list and meeting page (OFF-5, OFF-6)
   4. Scan to scores: upload, worker, status, review, accept, pipeline timeline (OFF-8 to OFF-11, S-2, S-3)
   5. Upload history and edit record (OFF-12, OFF-13)
   6. Members' pages (MEM-1, MEM-3)
   7. Every-page qualities: states, messages, accessibility, installable, live updates, speed, safe retries (X3 to X11), health and API (S-5, S-6)
   8. Tests for T1 to T10
3. **After each slice:** run `ruff` and `pytest`, list what changed and why, add a `CHANGELOG.md` entry, and propose a commit message starting with `M4:`. Alvin makes every commit himself.
4. **When something is unclear or conflicts with the repository, ask.** Do not guess about data, names, money rules or wording shown to officials.
5. **Do not change** the model training code, the trained models, the dbt feature definitions or the extraction prompt unless Alvin asks.

## 2. Ground rules

These five rules override anything else in this prompt.

| ID | Rule | Tag |
| --- | --- | --- |
| G1 | Officials use the interface to see which members to follow up and why, based on records the system reads from ledger photos. Members see only their own records. | \[S2\] |
| G2 | The system suggests and officials decide. Nothing on any page approves or rejects a loan. Use wording like "follow up"; never "reject" or "defaulter". | \[S2\] |
| G3 | Show the early warning only: a band (Low, Medium or High) plus reasons. Never show a percentage, a raw score or a "probability of default". The loan-default category stays hidden (D-022, D-023). | \[S2\] |
| G4 | Every score shows where it came from: the meeting it is based on, the model run, and when it was scored. | \[S2\] |
| G5 | Demo mode shows fictional names. Real names never appear on a projector. | \[S2\] |

**Words to use:** follow up, early warning, band, reasons, raises risk, lowers risk, missed repayment, running loan. **Words never to use on a page:** reject, approve, defaulter, bad member, credit score, probability, percent chance, AI decision.

**Demo mode (G5) in practice:** a `DEMO_MODE=true` setting replaces every member name with a fixed fictional Kenyan name chosen from the member code, so the same member always gets the same fictional name. A banner on every page says "Demo: names are fictional". In demo mode the meeting page and the review screen must not show a real ledger photo; see open decision 1 in section 12.

## 3. Roles

The server enforces every role on every request; hiding a link is never the only protection.

| ID | Role | Can see and do | Tag |
| --- | --- | --- | --- |
| R1 | Official (chair, treasurer, secretary) | Everything for their own chama | \[S2\] |
| R2 | Member | Their own records only. Never scores, other members or ledger photos, because the photos show everyone's names | \[S2\] |
| R3 | Admin (Alvin) | Sets up chamas, users and roles | \[S2\] with a command; \[S3\] a page |
| R4 | Every request | Checked for role, chama and member. Changing an ID in the URL gives a "not allowed" page, never someone else's data | \[S2\] |

**How to enforce it:**

- One FastAPI dependency loads the signed-in user's role, chama and member code from the `users` table and passes them to every page and API route.
- Every query that reads chama data takes the chama ID from that dependency, never from the URL alone. A member route also checks the member code.
- A failed check returns the "not allowed" page with HTTP 403 and writes a log line without names.
- The admin command for \[S2\]: `python -m chama.pipeline web-user add --email <email> --role official --chama chama_b [--member <code>]`, plus `list` and `deactivate`.
- Tests cover each role against each route: an official from another chama, a member opening an officials' page, and a member changing a member code in the URL.

## 4. Officials' pages

Officials get fifteen pages under `/o/`; every page ends with one clear next action.

| ID | Page | Address | Tag |
| --- | --- | --- | --- |
| OFF-1 | Overview | `/o/` | \[S2\] |
| OFF-2 | Members list | `/o/members` | \[S2\] |
| OFF-3 | Member page | `/o/members/{code}` | \[S2\] |
| OFF-4 | Band history for a member | Section on the member page | \[S3\] |
| OFF-5 | Records: meetings list | `/o/records/meetings` | \[S2\] |
| OFF-6 | Meeting page | `/o/records/meetings/{id}` | \[S2\] |
| OFF-7 | Records: loans list | `/o/records/loans` | \[S3\] |
| OFF-8 | Scan a page | `/o/scan` | \[S2\] |
| OFF-9 | Scan status | `/o/scans/{id}` | \[S2\] |
| OFF-10 | Review and correct | `/o/scans/{id}/review` | \[S2\] |
| OFF-11 | Pipeline run timeline | `/o/runs/{id}` | \[S2\] |
| OFF-12 | Upload history | `/o/uploads` | \[S2\] |
| OFF-13 | Edit record | `/o/edits` | \[S2\] |
| OFF-14 | About the scores | `/o/about` | \[S2\] |
| OFF-15 | Users | `/o/users` | \[S3\] |

### OFF-1 Overview

- The chama's name, the last meeting recorded, and "Scored N minutes ago with model run X".
- Counts by band, each with its text label ("High: 5 members"), drawn as three bead strands with one bead per member (section 7).
- "Members to follow up": the High band first, then Medium, each with their top reason.
- Chama health: open loans, total outstanding (KSh), and the share of running loans that missed a repayment at the last meeting.
- Quick actions: **Scan a page**, **View records**.
- A "New scores available" banner that appears by itself (X8) and reloads the overview when pressed.

### OFF-2 Members list

- Each member's name, band, open loans, outstanding balance, and repayments missed in the last 3 meetings.
- Sort by any column; filter by band; search by name. Filters live in the URL so a filtered view can be bookmarked.
- Members with no running loan show "No loan running" instead of a band.

### OFF-3 Member page

- The band, plus what it meant in testing, from the Milestone 2 report, section 14.2:
  - High: "In testing, about 1 in 3 High-band members missed a repayment within the next 3 meetings."
  - Medium: "about 1 in 4". Low: "about 1 in 8".
- The top 3 reasons in plain words, each marked "raises risk" or "lowers risk" with an icon and the words, never colour alone.
- Loans, open and past: type, issued, due, status, outstanding.
- Repayment timeline per meeting: balance before, repaid, interest, balance after.
- Monthly contributions.
- The meeting the score is based on, the model run and the scored time (G4).
- The note: "This is a prompt to follow up, not a decision."

### OFF-4 Band history \[S3\]

The member's band at each recent meeting, as a small table or chart.

### OFF-5 Meetings list

Date, ledger page number, totals, number of lines, and whether each page was typed (Excel) or scanned.

### OFF-6 Meeting page

The page's rows as recorded beside the photo, plus the footer totals and the loans given that day. In demo mode, follow open decision 1.

### OFF-7 Loans list \[S3\]

All loans, filtered by status: open, overdue, repaid.

### OFF-8 Scan a page

- Tips first: whole page in view, flat, good light.
- Accepted formats: JPEG, PNG or WebP, up to 20 MB, checked in the browser and again on the server.
- One upload control, `<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment">`: on a phone it opens the camera, on a computer a file picker.
- A preview before sending. The photo is resized and compressed in the browser (longest side 2,400 px, quality 0.85) before upload.
- The submit button disables on first press and the server ignores a repeat (X10).

### OFF-9 Scan status

Updates itself every 2 s and stops when done (X8):

```text
queued → reading → ready for review
                 ↘ failed (reason shown, Retry button)
```

Shows the time taken. A Retry reuses the same upload and never creates a second one.

### OFF-10 Review and correct

- The photo, zoomable and pannable, beside editable rows for the statements, the meeting footer and the new loans.
- Flagged cells from `checks.check_page` are marked with an icon, text and colour. Each shows its message and whether it is "Check" or a "Hint".
- The official can add or delete rows.
- Each new name is matched to an existing member from suggestions, or marked as a new member, using the same alias logic as `src/chama/anonymisation/aliases.py`.
- **Accept** works only once every name is matched, and asks for confirmation. **Discard** is also available.
- If the photo is not a ledger page, the screen says why and offers a retake.
- On a phone, rows are edited one at a time as cards, with Next and Previous.
- Drafts are saved on the server as the official edits, so nothing is lost if the session expires (X1).

### OFF-11 Pipeline run timeline

After Accept, one step per row, each with its status and duration:

```text
ingest → names → anonymise → data checks → score → done
```

A failure names the step, shows a safe message and offers Retry. When done, links go to the members whose records changed.

### OFF-12 Upload history

Every scan with its status, who uploaded it, when, the extraction model used, and links to its review and its edit record.

### OFF-13 Edit record

Who changed which cell, from what to what, and when. Rows can be added but never changed or deleted afterwards, enforced in the database (no update or delete permission on the table for the app's database role).

### OFF-14 About the scores

- How the early warning works, in plain words: it looks at each member's repayment record before the meeting and ranks who may miss a repayment in the next 3 meetings.
- What each band means and how often each band missed a repayment in testing (Milestone 2 report, section 14.2).
- The limits: one chama, 12 members, and a ranking that beats chance but is far from certain (PR AUC 0.32 against 0.20 by chance, explained in words).
- Why there is no loan-default category yet (section 14.3 of the report).
- How the data is protected (README, "Data protection").

### OFF-15 Users \[S3\]

For the chair or admin: invite by email, set the role, link a member's account to their record, deactivate.

## 5. Members' pages

Members get a short, friendly view of their own money under `/m/`, with nothing about scores or other members.

| ID | Page | Must show | Tag |
| --- | --- | --- | --- |
| MEM-1 | My summary (`/m/`) | Current loan balance or balances, the next due month, my monthly contributions, and my repayment timeline | \[S2\] |
| MEM-2 | My loans (`/m/loans`) | Open and past loans with their status | \[S3\] |
| MEM-3 | Limits | No scores, no other members, no ledger photos. Opening an officials' page shows a friendly "not allowed" page with a link back to My summary | \[S2\] |

Use the same plain words as the ledger: "contribution", "loan", "repaid", "balance". Amounts in KSh with thousands separators.

## 6. Across every page

These qualities apply to every page and every API route; each one has a test or a check.

| ID | Requirement | How | Tag |
| --- | --- | --- | --- |
| X1 | Sign-in | Supabase Auth with email and password for the demo; Google sign-in in Sprint III. Sign out on every page. An expired session sends the user to sign-in with the message "Your session ended. Sign in again to carry on." and keeps any unsaved review draft on the server | \[S2\] |
| X2 | Safe sessions | The server exchanges the Supabase token for its own session cookie: `HttpOnly`, `Secure`, `SameSite=Lax`. Every form and every HTMX request carries a CSRF token, checked by the server | \[S2\] |
| X3 | Page states | Each page has: loading, an honest empty state ("No scans yet. Scan your first ledger page."), success, an error next to the field it is about, a service error with Retry, and permission denied | \[S2\] |
| X4 | Messages | Specific and safe; never "Something went wrong", never a stack trace. Every error shows a short reference number that also appears in the server log | \[S2\] |
| X5 | Accessibility | Labelled fields, everything works from the keyboard, visible focus, contrast of at least 4.5:1, status messages in an `aria-live` region, nothing shown by colour alone | \[S2\] |
| X6 | Phone to desktop | Works from 360 px wide to a large desktop; each page shows a clear next action | \[S2\] |
| X7 | Installable | Web app manifest with icon, `display: standalone`, theme colour, and an "Add to Home screen" hint for officials on phones | \[S2\] |
| X8 | Live updates | Job status refreshes every 2 s with HTMX polling and stops when the job ends; the overview checks for new scores every 60 s | \[S2\] |
| X9 | Speed | Pages read precomputed scores and reasons; target under 100 ms on the server. Static files are vendored (no CDN) with cache headers. Photos are compressed before upload. Middleware logs each request's time, and a command prints the median and 95th percentile | \[S2\] |
| X10 | Safe retries | A double click or a retry never creates a second upload, job, run or set of rows: an idempotency key on each form, a unique photo checksum per chama, and one pipeline run per accepted scan, enforced by database constraints | \[S2\] |
| X11 | Data protection | API keys stay on the server. Logs hold codes, never names. Photos are re-saved without location data (EXIF removed) and kept in private storage outside `static/`. Members never receive photos | \[S2\] |

**Every page has:** a page title, the chama name, the signed-in person's name and role, Sign out, the language of the page set, and the demo banner when `DEMO_MODE` is on.

## 7. Visual style (X12)

The look is "Shanga": Kenyan beadwork colours on white, with beads as the one decorative element. Working pages stay calm and fast; the rich motion lives on the sign-in page and on About the scores. A screenshot of the Shanga design is in `docs/reference/` (open decision 6). \[S2\]

### Colours

| Token | Hex | Use | Text on it |
| --- | --- | --- | --- |
| `paper` | #FFFFFF | Page ground, cards | `ink` |
| `ink` | #14213D | Text, dark buttons, sidebar | `paper` |
| `muted` | #4A5470 | Secondary text on light grounds | — |
| `line` | #E3E8F2 | Borders, table rows | — |
| `ice` | #EEF3FF | Panels, selected rows, phone bottom bar | `ink` |
| `cream` | #FFF4D6 | Sign-in panel, empty states | `ink` |
| `cobalt` | #2547A8 | The one primary action colour, links, focus | white (8.2:1) |
| `red` | #D62839 | Bead colour; High band beads; errors | white (4.9:1) |
| `sun` | #F6C343 | Bead colour; Medium band beads | `ink` only |
| `leaf` | #187A42 | Bead colour; Low band beads; success | white (5.4:1) |
| `orange` | #F07F1A | Bead colour, decoration only | `ink` only |

### Band labels

Each band label is a chip with a bead count, a word and a colour, so it never relies on colour alone.

| Band | Chip text | Text colour | Chip colour | Beads |
| --- | --- | --- | --- | --- |
| Low | Low | #135C30 | #E1F2E7 | One `leaf` bead |
| Medium | Medium | #7A5200 | #FFF1C7 | Two `sun` beads |
| High | High | #9E1B2A | #FCE4E6 | Three `red` beads |

All three text and chip pairs pass 6:1 contrast. "Raises risk" uses an up arrow and "Lowers risk" a down arrow, always with the words.

### Type, shape and layout

- **Fonts, vendored as WOFF2 files in `static/fonts/`:** Gabarito (700–800) for page titles and big numbers; Atkinson Hyperlegible Next (400, 700) for everything else. Body 16–18 px, never below 14 px in tables. KSh amounts use tabular figures, right-aligned.
- **Shapes:** cards 20 px radius with a 1 px `line` border and no shadow; buttons 12 px radius, at least 44 px tall; chips fully round.
- **Desktop:** a left sidebar in `ink` with the logo, the chama name and the pages; content up to 1,200 px wide.
- **Phone:** a top bar and a bottom bar with Overview, Members, Scan, Records and More; Scan is a round bead-shaped button in the middle.
- **Bead details:** a short bead row under each page title; the logo is three concentric bead rings; numbered steps sit in dotted bead rings.

### Motion, only where it means something

| Where | What moves | Why |
| --- | --- | --- |
| Sign-in page | A ring of beads (a collar) beside the form reacts to the pointer: beads part and spring back, a tap sends a colour ripple. A beaded figurine of women at a chama meeting sits behind it | The one memorable moment; the form works at once and never waits for it |
| Overview band strands | One bead per member on three strands. When new scores arrive, a bead that changed band slides to its new strand in 600 ms. Each bead is a keyboard-reachable link labelled with the member's name and band | Shows officials what changed |
| Scan status | A bead travels along a thread while the photo is read; it settles on "ready for review" or stops and turns red with an icon and the reason | Shows progress honestly |
| Pipeline timeline | Each step is a bead on a string: filled when done, a gentle pulse while running, red with "!" and text on failure | The steps read at a glance |
| Members list → member page | The member's name and band chip move into the member page header with the View Transitions API (250 ms); no effect in browsers without it | Keeps the person oriented |
| About the scores | The one scroll story: as you scroll, a collar of beads sorts into three strands sized 50 / 30 / 20 (Low, Medium, High), then one bead opens to show its three reasons. CSS scroll-driven animations, no library, static fallback | Explains the bands in a way officials remember |
| Banners and swaps | "New scores available" slides down once; HTMX swaps fade in over 150 ms | Calm feedback |

Rules: no smooth-scroll takeover and no scroll snapping on working pages. Bead canvas code is our own, vendored, under 20 KB, and pauses when the tab is hidden. With `prefers-reduced-motion`, every effect above becomes static or instant.

### Figurines

Women's everyday life drawn as beaded wire figurines (single-line SVG paths drawn as bead strings): a chama meeting with the ledger, cooking, singing, a market stall with a phone payment. They appear only on sign-in, empty states, the "not allowed" page and About the scores, in one bead colour at low opacity behind text. Build simple placeholder paths now; commissioned art from a Kenyan illustrator replaces them later without code changes. Show women as capable and modern, never in poverty imagery.

## 8. Server pieces

The pages need seven new tables, a worker, a second raw source, a scoring step and a small JSON API; nothing in the existing pipeline is copied.

### S-1 App tables \[S2\]

New `app` schema, created by a new file in `sql/`. Tables that can hold real names go in the restricted `private` schema.

| Table | Schema | Main columns |
| --- | --- | --- |
| `users` | app | id, identity\_id (Supabase, unique), email, role, chama\_id, member\_code (members only), active, created\_at |
| `uploads` | app | id, chama\_id, uploaded\_by, photo\_path (private storage), checksum (unique per chama), status, provider, model, idempotency\_key (unique), created\_at |
| `jobs` | app | id, kind (`read_photo` or `run_pipeline`), upload\_id, status, step, error\_code, error\_message, attempts, run\_after, locked\_at, created\_at, finished\_at |
| `draft_rows`, `draft_flags` | private | The extracted rows per sheet (JSON per row, a deleted flag) and their flags (column, level `check` or `hint`, message), plus each new name's match |
| `row_edits` | private | upload\_id, row, column, old value, new value, edited\_by, edited\_at; insert only (OFF-13) |
| `pipeline_runs`, `pipeline_steps` | app | One run per accepted upload (unique), each step's status, start, end and error |
| `risk_scores` | app | chama\_id, member\_code, meeting\_date, band, reasons (JSON: feature, sentence, effect), model\_run\_id, scored\_at; unique on member, meeting and run |

### S-2 Worker \[S2\]

`python -m chama.web.worker` takes jobs from the `jobs` table without Redis, using `SELECT … FOR UPDATE SKIP LOCKED`.

- `read_photo`: re-saves the photo without location data, calls `chama.extraction.run.read_photo` with the configured provider, runs `checks.check_page`, and writes draft rows and flags. A page that is not a ledger page ends as failed with that reason.
- `run_pipeline`: writes the accepted rows as raw rows (S-3), runs the existing steps (ingest, names, anonymise, clean with dbt checks), then scoring (S-4), recording each step in `pipeline_steps`.
- A rate limit or timeout from the provider is retried up to 3 times with a growing wait; then the job fails with a clear reason. Retries reuse the same job and upload.

### S-3 Scans as a second raw source \[S2\]

Today `excel_loader.load_to_raw` runs `DELETE FROM raw.<table> WHERE chama_id = :c` before reloading from Excel, which would wipe out accepted scans. Mark every raw row with its source (`excel` or `scan`, plus the upload ID) and delete only the `excel` rows on reload, or keep scans in separate raw tables that dbt reads alongside. Propose one in the plan. What happens when a scan covers a page already typed in Excel is open decision 2.

### S-4 Scoring step \[S2\]

`python -m chama.pipeline score`, also run by the worker:

1. Load the chosen model with `chosen_model("missed_repayment")` from `src/chama/models/chosen.py`, which returns the run, the model and the band cut-offs.
2. Take each member's latest row in `analytics.member_months` while they owe on a loan.
3. Assign the band from the stored cut-offs: High at or above `high`, Medium at or above `medium`, otherwise Low. Never store or show the raw score on a page.
4. Get the top 3 SHAP reasons with `explain.shap_values` and `explain.top_factors(n=3)`.
5. Turn each reason into a plain sentence with the template for its feature, filled with the member's own value, and save it to `risk_scores` with the meeting date, model run ID and time.

Prepared feature names can carry prefixes from the preparation step (for example `missingindicator_`); map each back to its base feature. Keep the templates in one file and add a test that fails if any model feature lacks one.

**Draft sentence templates** (Alvin to check the wording; confirm each feature's exact meaning in `member_months.yml`):

| Feature | Sentence |
| --- | --- |
| `months_since_last_miss` | "Last missed a repayment {n} months ago" |
| `missingindicator_months_since_last_miss` | "Has never missed a repayment" or "Has missed a repayment before" |
| `missed_last_3_meetings` | "Missed a repayment at {n} of the last 3 meetings" |
| `recent_missed` | "Missed repayments at {n} meetings in the past year" |
| `recent_missed_share` | "Missed repayments at {n} of {m} meetings in the past year" |
| `repayment_ratio_last_3_meetings` | "Repaid little of the balance over the last 3 meetings" or "Repaid steadily over the last 3 meetings" |
| `months_in_records` | "Has been in the records for {years} years" |
| `loans_so_far` | "Has taken {n} loans so far" |
| `prior_rolled_over` | "Rolled {n} earlier loans into bigger ones" |
| `open_loans` | "Has {n} loans running" |
| `outstanding_vs_chama_median` | "Owes more than most members" or "Owes less than most members" |
| `oldest_open_loan_months` | "Oldest running loan started {n} months ago" |
| `loan_started_this_meeting` | "Took a new loan at this meeting" |
| `has_emergency_loan` | "Has an emergency loan running" |
| `has_school_fees_loan` | "Has a school-fees loan running" |
| `recent_contribution_rate` | "Kept up monthly contributions" or "Missed some monthly contributions" |
| `chama_missed_share` | "Many members missed repayments at this meeting" or "Few members missed repayments at this meeting" |
| `month_of_year` | "School fees fall due this month" (January, May, September), otherwise "Time of year" |

Each sentence is followed by "raises risk" or "lowers risk" from the SHAP sign.

### S-5 Health check \[S2\]

`/health` returns ready only once the model has loaded and the database answers; otherwise it returns 503 with which part is not ready.

### S-6 JSON API \[S2\]

For the future mobile app, with the same sign-in and role checks as the pages: `GET /api/health`, `/api/members` (with bands, officials only), `/api/members/{code}`, `/api/uploads`, `/api/jobs/{id}`. The interactive API docs are visible to admins only.

### S-7 and S-8 \[S3\]

- S-7: data drift monitoring with Evidently.
- S-8: the model is loaded from the MLflow model registry by alias, and its checksum is recorded with each score.

## 9. Out of scope

Do not build these, even if they seem like a small addition.

| ID | Not in this milestone |
| --- | --- |
| N1 | No approve or reject, and no credit ratings for members |
| N2 | No probability percentages, no raw scores and no loan-default category |
| N3 | No mobile app (future work, report Chapter 6). No push notifications; in-page updates replace them |
| N4 | No payments and no M-Pesa |
| N5 | Accepted pages cannot be edited, except through a new scan or the edit record |

## 10. Scenarios to demo and test

Each scenario gets an automated test where possible and a short manual check for the demo; together they become the test record.

| ID | Scenario | Expected result | Covers |
| --- | --- | --- | --- |
| T1 | An official signs in | The overview appears in under 1 s | X1, X9, OFF-1 |
| T2 | An official opens a member page | Band, what it meant in testing, three reasons, and the meeting, model run and scored time are shown | OFF-3, G3, G4 |
| T3 | Scan a good page, review, fix a flagged cell, accept | The pipeline timeline runs to done and the bands update | OFF-8 to OFF-11, S-2 to S-4 |
| T4 | Upload a blurred or non-ledger photo | Rejected with the reason and a retake | OFF-10 |
| T5 | Upload a wrong file type or a file over 20 MB | An error appears next to the field | OFF-8, X3 |
| T6 | A member signs in, then opens an officials' URL | Only their own summary; the officials' URL gives "not allowed" | MEM-1, MEM-3, R2, R4 |
| T7 | The session expires during a review | Sign-in page with a message; the draft is still there afterwards | X1 |
| T8 | The extraction service is down or rate-limited | The job shows "failed" with the reason; Retry adds no duplicates | S-2, X4, X10 |
| T9 | Double click on Accept | Only one pipeline run starts | X10 |
| T10 | A scan has a new name | Accept stays unavailable until the name is matched | OFF-10 |

Also test: an official from another chama gets "not allowed" on every route; the edit record cannot be updated or deleted; logs contain no names; `DEMO_MODE` shows no real name on any page.

## 11. Stack and conventions

Build on what the repository already uses; add only the web pieces below.

| Area | Choice |
| --- | --- |
| Server | FastAPI with Jinja2 templates and HTMX, HTMX vendored in `static/` |
| Database | The existing PostgreSQL in Docker; new `app` schema, names only in `private` |
| Sign-in | Supabase Auth (free tier), verified on the server |
| Background work | The worker in S-2, using the `jobs` table; no Redis |
| Pipeline and models | The existing pipeline, dbt and MLflow, called, not copied |
| Environment | The conda `chama` environment; web libraries added as a `web` extra in `pyproject.toml`, installed with `pip install -e ".[web]"` |
| Quality | `ruff`; `pytest` with tests for roles and failure paths |

**Code layout:**

```text
src/chama/web/
├── app.py          FastAPI app, middleware (timing, CSRF, errors with reference numbers)
├── pages.py        HTML routes for /o/ and /m/
├── api.py          JSON routes under /api/
├── auth.py         Supabase sign-in, session cookie, the role dependency
├── worker.py       The job worker
├── services/       Business logic: scoring, reasons, scans, review, records, demo names
├── data/           Database access only, one module per area
├── templates/      Jinja2 pages and partials
└── static/         CSS, vendored HTMX, fonts, bead and figurine scripts, icons, manifest
```

Keep presentation (templates, pages), business logic (services), data access (data) and model calls (services/scoring) in separate modules. Templates never query the database.

**Running it:**

```powershell
uvicorn chama.web.app:app --reload     # the web interface
python -m chama.web.worker             # the job worker, in a second terminal
python -m chama.pipeline score         # score again by hand
python -m chama.pipeline web-stats     # median and 95th percentile page times
```

**New settings in `.env`** (names only; values come from Alvin): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `SESSION_SECRET`, `DEMO_MODE`, `PHOTO_DIR`. Add each to `.env.example` with a comment.

**Documentation and Git:**

- Add decision **D-026** to `docs/decisions.md`: the web interface replaces Streamlit, and the mobile app becomes future work, with the reasons (works on any phone browser, one code base, the JSON API keeps the mobile app possible).
- Update the README milestone table (M4 becomes the web interface) and add a "Running the web interface" section.
- Work on the branch `m4-web-interface`, one GitHub issue per slice in section 1, and keep the branch after merging.
- Alvin makes every commit himself. After each slice, propose the commit message, starting with `M4:`, and a `CHANGELOG.md` entry.

## 12. Open decisions

Ask Alvin about each of these in the plan (step 1); do not guess.

| # | Decision | Suggested answer |
| --- | --- | --- |
| 1 | Ledger photos show real names, so a real photo on the meeting or review page breaks G5 on a projector | For the demo, write a fictional ledger page by hand and scan it; in demo mode, never show a real photo |
| 2 | A scan of a page already typed into Excel | For Sprint II, refuse it as a duplicate by ledger page number and meeting date, with a clear message |
| 3 | The Supabase project | Alvin creates a free project, turns on email sign-in, and puts the keys in `.env` |
| 4 | Wording of the reason sentences in S-4 | Alvin checks each sentence against `member_months.yml` |
| 5 | Demo accounts | One official and one member account for chama B, emails from Alvin |
| 6 | The style reference | Alvin saves a screenshot of the Shanga design as `docs/reference/shanga.png` |
| 7 | Where uploaded photos are kept | A folder under the private, git-ignored `data/` folder, set by `PHOTO_DIR` |
| 8 | Time to the Sprint II review | In the plan, say which \[S2\] items are at risk and what could move to Sprint III |
