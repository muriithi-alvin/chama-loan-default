# Extraction log — ledger photos to raw Excel

One entry per year extracted. No member names appear here; the raw files and
photos stay on the project computer only.

| Year | Chama | Photos | Meetings | Statement rows | New loans | Rows flagged unclear | Checked against paper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | chama_b | p001–p012 | 12 | 167 | 22 | 16 statements, 7 meetings, 7 loans | Pending |
| 2015 | chama_b | p013–p024 | 12 | 141 | 12 | 9 statements, 9 meetings, 2 loans | Pending |

## 2014 (chama_b_p001 – p012)

**Coverage.** One page per month, January to December 2014. Pages p001–p005
have no date at the top; p001 and p002 give the *next* meeting's date
(9 Feb, 9 Mar 2014), so their months can be worked out in cleaning. From June
(p006) each page carries a date and usually the host's name.

**Layout seen.** Name · balance before · repayment · balance after · month due
· interest %. Headings vary slightly (e.g. "Loan · Loan repayment · Loan
balance" from September). On p005 the last column is headed "Month due" but
holds percentages — the values were placed in `interest`.

**Loan types seen.** Normal loans (up to 60,000) at 1–2% per month; short
emergency loans (2,000–20,000) at 5%, usually repaid in full at the next
meeting; one top-up.

**Things to check against the paper** (all marked `unclear = Y` with a note in
`remarks`):
- p001: the % column is cut off at the page edge for two rows.
- p007: one member's repayment could be 5,300 or 5,200 and balance 32,000 or
  30,000 — the next page starts from 30,000.
- Several figures written over earlier figures (p002, p006, p009, p011, p012).
- Footer lines cut off at the bottom of p003, p008, p011.

**Automatic continuity check.** Each member's *balance after* on one page was
compared with their *balance before* on the next. Nearly all differences are
new loans starting that month. Two real differences remain and are left as
written, since raw data must match the ledger:
- p007 → p008: 32,000 (unclear) vs 30,000.
- p011 → p012: one balance written as 55,000 then carried forward as 56,000.

This check is a good candidate for an automatic data-quality rule in the
pipeline (issue "Data quality checks and report").

## 2015 (chama_b_p013 – p024)

**Coverage.** One page per month, January to December 2015. Pages p015–p024
were photographed sideways and read rotated. p014 is dated only "February",
p015's year is cut off at the photo edge ("8th/March/201") and p022 has no
date; the pipeline places all three in the right month from their neighbours.

**Layout seen.** The % column stops after p016 (May onwards has no interest
column). From June the table is numbered and has no headings on some pages.
p022's column headed "loan due" holds the balance after and the column headed
"%" holds the due month. The meeting host and date replace the headings on
several pages.

**New in the ledger** (rules added to the data dictionary):
- Emergency loans marked beside the name as `Em`, `Eme` or `(Em)` (from July):
  typed in the new `Statements.loan_type` column, not in the name.
- `cleared` / `Cleared` written as the balance after (typed as written; the
  pipeline reads it as 0).
- A member line of dashes only (no loan that month).
- Tick marks after figures (treasurer's checks): not typed.
- Names partly outside the photo (p016, p017): full name typed, with a remark.

**Loans.** Normal loans grew from 60,000 to 80,000 (from April). Due months
written in the ledger are 13–19 months after a loan is given; the Chama's rule
is 12 months, so these are extensions agreed per loan (decision D-012).

**Things to check against the paper** (all marked `unclear = Y` with a note in
`remarks` or `notes`):
- p013: one % value written over; the footer line 'M/B (Received 61,630)'.
- p014: a crossed-out balance of 5,000 on a line of dashes (the page note says
  that member cleared the loan after the meeting); one repayment could be
  5,262 or 4,242 (4,242 matches the balance).
- p014: the third new loan (38,000, cash) has its name cut off.
- p018: a balance before and repayment with overwritten digits; the new loan
  has 80,000 written above 100,000.
- p019: an emergency line (5,000 repaid with 5,750) shows a balance of 15,000.
- p021: a balance read as 35,000 that could be 39,000 (35,000 matches the sum
  and the next page).
- p022: one balance is only faint writing; another written over an earlier
  figure.
- p023: total collection with an overwritten digit.

**Automatic continuity check.** With the name review applied, every 2015
balance carries forward within 2%. The pipeline also flags one 2015 line
whose balance grows more than interest allows (p019, above). One 2014 loan of
5,000 shows as `lost_track`: it is the one cleared after the meeting on p014,
which the ledger line itself does not show.
