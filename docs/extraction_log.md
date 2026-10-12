# Extraction log — ledger photos to raw Excel

One entry per year extracted. No member names appear here; the raw files and
photos stay on the project computer only.

| Year | Chama | Photos | Meetings | Statement rows | New loans | Rows flagged unclear | Checked against paper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | chama_b | p001–p012 | 12 | 167 | 22 | 16 statements, 7 meetings, 7 loans | Pending |
| 2015 | chama_b | p013–p024 | 12 | 141 | 12 | 9 statements, 9 meetings, 2 loans | Pending |
| 2016 | chama_b | p025–p036 | 12 | 131 | 15 | 3 statements, 4 meetings, 2 loans | Pending |
| 2017 | chama_b | p037–p048 (+ p051, retake of p048) | 12 | 148 | 12 | 0 statements, 3 meetings, 0 loans | Pending |
| 2018 | chama_b | p049, p050, p052–p061 | 12 | 144 | 16 | 2 statements, 2 meetings, 2 loans | Pending |
| 2019 | chama_b | p062–p073 | 12 | 146 | 4 | 1 statement, 1 meeting, 0 loans | Pending |
| 2020 | chama_b | p074–p085 | 12 | 141 | 8 | 8 statements, 1 meeting, 1 loan | Pending |
| 2021 | chama_b | p086–p097 | 12 | 175 | 19 | 2 statements, 0 meetings, 4 loans | Pending |
| 2022 | chama_b | p098–p109 | 12 | 152 | 14 | 7 statements, 0 meetings, 2 loans | Pending |
| 2023 | chama_b | p110–p121 | 12 | 144 | 11 | 1 statement, 0 meetings, 0 loans | Pending |
| 2024 | chama_b | p122–p133 | 12 | 144 | 15 | 0 statements, 0 meetings, 1 loan | Pending |
| 2025 | chama_b | p134–p145 | 12 | 124 | 17 | 2 statements, 0 meetings, 1 loan | Pending |
| 2026 | chama_b | p146–p149 (Jan–Apr) | 4 | 42 | 9 | 2 statements, 0 meetings, 0 loans | Pending |

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

## 2016 (chama_b_p025 – p036)

**Coverage.** One page per month. p025 and p026 have no date; p027 ("6th
March") has no year; several pages give only the month ("May 2016"), which the
pipeline now reads as the meeting month.

**Layout seen.** The % column comes and goes. p025's due-month column is cut
off at the photo edge (only first letters visible), so due is left blank;
p034's due years are cut off, so only the month is typed. From December
(p036) a **Monthly** column records each member's contribution (300).

**New in the ledger:** emergency loans also marked `(E)` beside the amount or
`Emergency` in the due column (typed in `loan_type`); emergency lines written in
red ink on p031 (noted in `remarks`); "Cleared" with a date written beside a
balance (typed as `Cleared`); repayments written as sums (`6500 + 500`). Normal
loans grew to 100,000.

**Things to check against the paper:**
- p026 (written faintly): one repayment read as 10,330 (could look like
  11,130); the new-loan amount read as 82,000 (could be 22,000; the next page
  shows 100,000).
- p031: a repayment reads 2,150 but the balance implies about 20,000.
- p032: a repayment with "(+10,000 ...)" written beside it; one new loan of
  20,000 has its name cut off.

## 2017 (chama_b_p037 – p048, with p051)

**Retake.** p048 (December) is too blurred to read. The same page was
photographed again later as p051 (after the January and February 2018 pages).
December is typed under p048 so pages stay in ledger order; its meeting notes
name p051 (extraction rule 13). p051 has no rows of its own.

**Layout seen.** Monthly contributions on most pages (300, rising to 500 and
more). From May (p041) interest is written as an **amount** in its own column,
with the rate (1%) in a separate % column; the amount is typed in `interest`.
p037's first number column is headed "MONTHLY" but holds the loan balance.
Emergency repayments are sometimes written as prose under the table (kept in
the meeting notes). A "books review" on 5 June 2017 (p042) compares total debt:
540,400 (30 April 2015), 642,200 (1 November 2015), 677,940 (5 June 2017).

**Things to check:** p042's total-debt table; p046's date (24/10/17 written
over 24/9/17); names marked `*` on p047 (meaning not written).

## 2018 (chama_b_p049, p050, p052 – p061)

**Coverage.** January–December; p051 belongs to 2017 (above).

**Layout seen.** Emergency lines carry **E** in the line-number column or the
monthly column (typed in `loan_type`). **Due months are no longer written**
from 2018, so 2018 loans take their due date from the 12-month rule. Payments
by M-Pesa appear alongside cash. Normal loans reach 130,000.

**Things to check against the paper:**
- p052: two "?" written for an emergency repayment and balance.
- p053: one repayment on correction fluid, read as 4320+200 (could be
  4300+240); one line has no balance before.
- p056: a new loan of 44,000 with "130" written above it.
- p058: a new emergency loan of 5,000 to a name that matches no member (as
  written; see the name review); one repayment written over (read as 5,400).

**For the Chama (emergency loan term).** From 2017 emergency loans run 2–3
months at 3% (for example 30,000 repaid as 10,600, 10,600, 10,300), instead of
being repaid at the next meeting at 5%. With `emergency_term_days: 31` most of
them show as repaid late. Confirm the emergency term for these years.

## 2019 (chama_b_p062 – p073)

**Coverage.** January–December. p068 and p069 are two photos of one ledger
page: the July meeting at the top and the start of the August meeting at the
bottom. August is typed under p069, which shows all of it. p066 is dated
"/5/2019" with no day; the meeting month comes from the date and the previous
page's "next meeting" note.

**Layout seen.** Most pages have no headings; the columns are loan, repayment,
balance and then the monthly contribution (moved to the right). Interest and
due months are no longer written (two loans show "3/20"). Emergency lines are
marked E; in May they sit under an "Emergency" heading with only the amount.
Payments made after the meeting are listed with their dates under the table.
Few new loans are listed (4).

**Things to check against the paper:**
- p068: one balance read as 67,000 (could be 70,000; the next meeting's loan
  column has 70,000 crossed out and 67,000 written above).
- p069: an emergency line with no amounts (a faint, rubbed-out figure).
- p073: one line's figures crossed out in red (the loan moved to a later
  line); a short line with only a first name and a payment of 1,000.

## 2020 (chama_b_p074 – p085)

**Coverage.** January–March are meetings. From April the pages are headed
"<month> 2020 contributions" with no meeting details (no gatherings in that
period); a letter after each name shows payment by cash (C) or bank (B), with
the key on the May page. These letters are noted in `remarks`, not typed in
the name.

**New in the ledger:** school-fees loans (November and December), typed as
`school fee` / `school fees` in `loan_type`. One member is written under a
different surname on two pages (see the name review).

**Things to check against the paper:**
- p075: one balance written "?? 59,500" over a crossed-out 60,000; the second
  new loan (45,000) has an unclear name.
- p076: one repayment with an overwritten first digit (7,250).
- p077: one repayment overwritten in red (10,9.0).
- p079: a balance read as 52,095 (could be 53,095).
- p081: several overwritten figures and correction fluid on one line.
- p083: total collection written "195,550 ?".
- p085: an emergency repayment read as 10,900 (10,300 would match 3%); a
  school-fees balance read as 30,000 (could be 80,000).

**Seen by the pipeline (to raise with the Chama).** One member stops
appearing after January 2020 with 89,640 outstanding (`lost_track`). Two
normal loans are overdue at the end of 2020 after months of interest-only
payments.

## 2021 (chama_b_p086 – p097)

**Coverage.** January–December; p086 (January) has no date, only "HAPPY NEW
YEAR 2021". Most pages give the month only.

**New in the ledger:** school-fees loans become regular (SF lines); normal loans
reach 150,000–200,000 from mid-year. A new loan can be written only in the
balance-after column ("- | - | 150,000"), typed as written (rule 16). A penalty
payment appears as its own line with "Penalty" in the monthly column (rule 17).
"=" is used for "nothing" on some lines.

**Things to check against the paper:**
- p086: a school-fees repayment corrected from 10,600 to 5,600.
- p089: a school-fees balance read as 30,000 (could be 80,000).
- p092: the third new loan of 200,000 is cut off at the page bottom.
- p093: a school-fees loan in the loans list is struck through.
- p097: the day of one loan date is unclear.

## 2022 (chama_b_p098 – p109)

**Coverage.** January–December; p098 (January) and p104 (July) have no date,
p109's heading is cut off; all three are placed by page order.

**Layout seen.** From July (p104) the table has an **Interest** column (an
amount) and the repayment column holds the principal only (headed "Loan
reduction" in September). Interest amounts go in `interest` (rule 19).

**Things to check against the paper:**
- p099: two repayments with overwritten digits (25,600 or 26,600; 11,300 or
  13,300) and a school-fees balance (17,000 or 14,000).
- p100: a school-fees loan read as 14,000 (could be 17,000).
- p101: an emergency balance read as 15,000 (the next page starts at 15,100).
- p102: a school-fees loan dated 19/5/2021 on the May 2022 page.
- p104: a repayment written as 90,000 where the balance implies 10,000; a note
  records 26,750 paid in error and counted in that day's repayment.
- p105: balances partly cut off at the right edge.

## 2023 (chama_b_p110 – p121)

**Coverage.** January–December; p110 (January) has only "2023".

**Layout seen.** Repayments include interest until August; the Interest column
returns from September. Two loans given in April are written in the table with
only the amount (p113). Members' prepaid contributions are recorded as notes
("Pre-paid January", "350 paid January").

**Things to check:** p111 a school-fees balance read as 26,000 (could be
25,000).

## 2024 (chama_b_p122 – p133)

**Coverage.** January–December, with an Interest column throughout.

**Notes of interest:** at the annual meeting on 1 May 2024 members agreed a
dividend of 10,000 each, paid by M-Pesa. Normal loans reach 290,000–350,000.
Several balances are written as the amount with "cleared" above it: the loan
was cleared after the meeting and a bigger loan taken (typed as `cleared`).

**Things to check:** p125 a loan dated "?/4/2023" on the April 2024 page.

## 2025 (chama_b_p134 – p145)

**Coverage.** January–December; p134 (January) has no date.

**Notes of interest:** loans of 300,000–350,000; several are "topped up" in
two instalments (for example 168,000 then 14,000 to make 350,000), noted in the
loans lists. Members who prepay contributions are written "Paid up to …".

**Things to check:**
- p135: the day of one loan date (300,000) is unclear.
- p136: one line with a crossed-out repayment and interest (the member paid
  two months' interest on 25/3/2025).
- p145: one monthly contribution could be read as 850.

## 2026 (chama_b_p146 – p149, January – April)

**Coverage.** January to 5 April 2026, the last page photographed.

**Things to check:**
- p149: a loan written "23000" (230,000 by the balance and interest).
- p149: an emergency balance read as 20,300 (could be 20,000); the line is
  marked "Em." but continues a school-fees loan.

## Names across the years

Some members' names are written differently over the years: a surname
misspelled on one page, a first name shortened, a different surname from 2023
or 2024. The name review file lists every spelling with the suggested member;
the pipeline's balance continuity shows which spellings belong together.
