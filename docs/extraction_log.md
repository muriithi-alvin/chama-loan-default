# Extraction log — ledger photos to raw Excel

One entry per year extracted. No member names appear here; the raw files and
photos stay on the project computer only.

| Year | Chama | Photos | Meetings | Statement rows | New loans | Rows flagged unclear | Checked against paper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | chama_b | p001–p012 | 12 | 167 | 22 | 16 statements, 7 meetings, 7 loans | Pending |

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
