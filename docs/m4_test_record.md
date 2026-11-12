# Milestone 4 test record (T1 to T16)

T1 to T10 are the scenarios from section 10 of `docs/m4_master_prompt.md`; T11 to
T16 cover what was added after the presentation (D-036 to D-043). Each has the
automated tests that cover it and a short manual check on the running site. Manual
checks run on the laptop release (`serve-release --address https://preview.localhost`,
then http://localhost:3000), which holds Humble Sister's copy to page 128 (D-036).
Until 5 Nov they used the fictional demo chama (D-028).

Automated tests run with `python -m pytest` and on every push (GitHub Actions). On
12 Nov 2026: 337 tests, all passing, 1 skipped on Windows (symbolic links; it runs on
GitHub's Linux).

**12 Nov 2026:** the browser checks could not be run on the project laptop: with the
site, a browser and the tools open it ran out of memory ("insufficient system
resources"). They are written below as steps; run them with only the release and one
browser open.

**Result:** Pass = expected behaviour seen; Partly = met with a stated
difference; To do = manual check still to run.

| Test | Scenario | Automated | Manual | Result |
| --- | --- | --- | --- | --- |
| T1 | An official signs in | none (timing) | measured from the request log | Partly |
| T2 | An official opens a member page | yes | data checked; browser check to do | Pass (data) |
| T3 | Scan, review, fix a cell, accept | yes | run to done on 24 Oct; full check to do | To do |
| T4 | Blurred or non-ledger photo | partly | to do | To do |
| T5 | Wrong file type or over 20 MB | yes | to do | Pass (automated) |
| T6 | A member opens an officials' URL | yes | done 26 Oct | Pass |
| T7 | Session expires during a review | yes | to do | To do |
| T8 | Extraction service down | yes | happened for real, 24 and 27 Oct | Pass |
| T9 | Double click on Accept | yes | done 24 Oct | Pass |
| T10 | A scan has a new name | yes | done 24 Oct | Pass |
| T11 | Sign in with Google, a password or a phone; officials type a texted code | yes (43) | to do | Pass (automated) |
| T12 | Humble Sister's copy: real names, two renamed, records to page 128 | yes | built and loaded 6 and 11 Nov | Pass |
| T13 | Type a page | yes | run to done on 6 Nov (page 129, chama B's real figures) | Pass |
| T14 | A meeting in two or three photos | yes | to do (needs Groq's paid plan, D-043) | Pass (automated) |
| T15 | Each step opens the next, through to the results | — (pages) | to do | To do |
| T16 | A real texted code through Africa's Talking | yes (14, fake service) | to do (needs an account with credit and a public address) | Pass (automated) |

## T1 An official signs in: the overview appears in under 1 s

- **Automated:** none; this is a timing.
- **Measured** (request log, the demo official's account, 24 to 27 Oct):
  the Overview's data comes from four requests. Medians: `/api/overview`
  116 ms, `/api/records-status` 94 ms, `/api/me` 41 ms, `/api/scores/latest`
  33 ms. 95th percentiles: 212, 373, 193 and 127 ms. In the built pages the
  sign-in page is usable 0.74 s after it starts loading (headless Chrome,
  26 Oct).
- **The difference:** signing in itself takes 1.8 s (median of 8 real
  sign-ins; up to 2.5 s), because Supabase checks the password on its own
  server. Once signed in, the Overview loads well within 1 s.
- **Manual check (to do):** sign in as the demo official on the built pages;
  the Overview should appear about 2 s after pressing Sign in.

## T2 An official opens a member page

- **Automated:** `test_web_auth.py::test_an_official_sees_only_their_own_chamas_members`;
  `test_web_reasons.py::test_every_feature_of_the_model_has_a_template`,
  `::test_sentences_use_the_members_own_values`.
- **Data check, 27 Oct:** for a High-band member of the demo chama the page
  data holds the band; what it meant ("In testing, about 1 in 3 High-band
  members missed a repayment within the next 3 meetings."); three reasons;
  and the source: ledger page 149 (5 April 2026), model run
  "random forest fc6ae3fe", scored 24 Oct 2026.
- **Manual check (to do):** open Members, then a High member. Check the band,
  its meaning, three reasons, and the meeting, model run and scored time.

## T3 Scan a good page, review, fix a flagged cell, accept

- **Automated:** `test_web_scans.py::test_flags_point_at_the_draft_row_and_use_plain_labels`;
  `test_web_db.py::test_one_pipeline_run_and_one_job_of_each_kind_per_upload`,
  `::test_accept_refuses_a_meeting_already_in_the_records`.
- **Earlier run, 24 Oct:** a typed page with fictional names was read in
  3.5 s with every amount right. After Accept the pipeline ran to done in
  48 s.
- **Manual check (to do):** the handwritten demo page. Upload it, correct the
  flagged cell, match any names, Accept. The timeline should run to done, and
  the Overview should show the new scores.

## T4 Upload a blurred or non-ledger photo

- **Automated:** `test_web_scans.py::test_uploads_are_refused_next_to_the_photo_field[not-an-image]`
  (a file that is not an image).
- **Manual check (to do):** upload a clear photo of something that is not a
  ledger page, and a very blurred page. Each should be refused with the reason
  and a way to take the photo again.

## T5 Upload a wrong file type or a file over 20 MB

- **Automated:** `test_web_scans.py::test_uploads_are_refused_next_to_the_photo_field`
  (a PDF, an empty file, a file over 20 MB, a file that is not an image): each
  refused with the error on the photo field.
- **Manual check (to do):** choose a PDF on Scan a page; the error should
  appear next to the field.

## T6 A member signs in, then opens an officials' URL

- **Automated:** `test_web_auth.py::test_a_member_gets_not_allowed_on_officials_routes`;
  `test_web_db.py::test_the_footer_status_gives_members_no_score_details`.
- **Manual check, 26 Oct (headless Chrome, demo member):** My summary and My
  loans showed only the member's own records. `/o/members` gave the "not
  allowed" page with HTTP 403.

## T7 The session expires during a review

- **Automated:** `test_web_auth.py::test_without_a_session_every_page_says_the_session_ended`,
  `::test_signing_out_ends_the_session`. Drafts are kept on the server
  (`app.draft_rows`), not in the browser.
- **Manual check (to do):** open a scan's review and correct one cell. Sign
  out in a second tab, then act in the first. The sign-in page should say
  "Your session ended. Sign in again to carry on." Sign in and open the scan
  again: the correction should still be there.

## T8 The extraction service is down or rate-limited

- **Automated:** `test_extraction.py::test_openai_style_extractor_explains_failures`;
  `test_web_db.py::test_one_pipeline_run_and_one_job_of_each_kind_per_upload`,
  `::test_jobs_are_taken_once`.
- **Seen for real, 24 and 27 Oct:** Groq could not be reached from the
  laptop's network. After 3 attempts each scan showed "failed" with "Could not
  reach the extraction service. Check the internet connection." Retry ran the
  same upload again: still one upload and one reading job.
- **Cause and fix:** this network dropped the bigger first handshake message
  that OpenSSL 3.5 sends (it includes a post-quantum key share). The extractor
  now offers only the X25519 key exchange, with certificates still checked
  (`test_extraction.py::test_the_smaller_handshake_still_checks_certificates`).

## T9 Double click on Accept

- **Automated:** `test_web_db.py::test_double_accept_starts_one_run`.
- **Manual check, 24 Oct:** Accept was sent twice in the same second. Both
  answers named the same run; one pipeline run took place.

## T10 A scan has a new name

- **Automated:** `test_web_scans.py::test_accept_waits_until_every_name_is_matched`,
  `::test_name_suggestions_come_from_the_chamas_members`.
- **Manual check, 24 Oct:** a misread name ("Kawira Mutembel") kept Accept
  unavailable until it was matched to the member.

## T11 Sign in with Google, a password or a phone; officials type a texted code (D-037)

- **Automated** (`test_web_auth.py`, fake Supabase): an official's password alone opens
  nothing until the texted code; wrong codes are counted and the fifth ends the sign-in;
  an official without a phone is told to ask for one; members sign in with a phone code
  alone; codes are texted only to numbers with an account; Google goes through Supabase
  with a PKCE challenge, and the code is exchanged with this browser's verifier;
  problems come back to the sign-in page in plain words; Kenyan numbers are read in
  every usual form.
- **Manual check (to do):** with Google and Phone on in Supabase and test numbers set
  (web_setup steps 6 and 7): Continue with Google as the treasurer, type the test code,
  see the Overview as Alvin Muriithi; type a wrong code once and see "4 tries left"; on
  the Phone tab, sign in as Alvin Wise with his test number and see My summary; try the
  treasurer's number on the Phone tab and see that officials start with Google or email.

## T12 Humble Sister's copy (D-036)

- **Automated** (`test_web_names.py`, `test_deploy.py`): real names kept except the two
  renamed; a rename must name a member and not take another's name; pages kept to the
  month in `records_until`; a fictional copy still hides every real name; the release
  serves the chamas marked `release: true`.
- **Run, 6 Nov:** `demo-chama` wrote 11 workbooks, 127 pages to page 128 (July 2024), 12
  members with real names, Beth Wamae shown as Alvin Muriithi and Esther Mwangi as Alvin
  Wise; every old spelling points to the copy's names. Loaded and scored on 6 and 11 Nov
  (7 members scored at page 128).

## T13 Type a page (D-038)

- **Automated** (`test_web_scans.py`, `test_web_db.py`): the page opens with each member
  once and a line for each other running loan, carrying the last balance; agreed names
  match at once; it needs no photo; no page for a future date or while an update runs;
  pages go in date order, also against pages accepted but not yet added.
- **Run, 6 Nov** (a throwaway database loaded like the release): page 129 (4 Aug 2024)
  typed with chama B's real figures; the carried balances matched the real page;
  no flags after typing; Accept; all five update steps done; bands at page 129; the
  records call it "Entered here".
- **Manual check (to do):** Type a page, choose 4 August 2024, type Alvin Wise's line
  (Monthly 350, Repaid 10,000, Balance after 30,000), Accept, and watch the results open.

## T14 A meeting in two or three photos (D-039)

- **Automated** (`test_web_scans.py`, `test_worker_parts.py`): parts joined in order into
  one draft; the date and totals from the first photo that has them, a different value
  on a later one noted for the reviewer; a line seen on two photos gets a hint; a rate
  limit on a later photo is waited out without reading the first again; a photo that is
  not a page fails the scan, naming the photo; four photos are refused.
- **Manual check (to do, needs Groq's paid plan, D-043):** cut a page photo into two
  overlapping parts along its lines (for example `chama_b_p130.jpg`, where the page is
  photographed sideways: left part with the date and lines 1 to 6, right part with lines
  6 to 11), send both, and check the review shows "Part 1 of 2" and "Part 2 of 2", all 11
  lines, and a hint on the repeated line 6.

## T15 Each step opens the next (D-040)

- **Automated:** none (page behaviour).
- **Manual check (to do):** after sending a photo, the status page opens the review by
  itself when reading ends; Accept opens the records update; when it finishes, "Who to
  follow up after page N" appears below with each member's colour and main reason, and
  buttons to see the whole chama or add the next page. The step bar at the top shows the
  current step on every page.

## T16 A real texted code through Africa's Talking (D-042)

- **Automated** (`test_sms_hook.py`, fake Africa's Talking): a signed request for a
  member's number is texted; the sandbox username uses the sandbox; an unsigned, old or
  altered request texts nothing; only numbers with an active account are texted;
  Africa's Talking's refusals and a bad key are reported to Supabase; without settings it
  says what to add; the code never reaches the log.
- **Manual check (to do):** on the live Space (or the laptop behind ngrok), with the
  Send SMS hook and `AFRICASTALKING_*` set (web_setup step 8): sign in as the treasurer
  with a number that is not a test number. With `sandbox`, the code appears in Africa's
  Talking's simulator; with a live app, on the phone. The API log shows
  `sms hook: code sent to the number ending ...`.
