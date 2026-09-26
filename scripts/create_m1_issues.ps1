# Creates the Milestone 1 (data pipeline) backlog on GitHub.
# Run once from the project folder:  .\scripts\create_m1_issues.ps1
$m = "M1 - Data pipeline"

function New-Issue($title, $label, $body) {
    gh issue create --title $title --label $label --milestone $m --body $body
}

New-Issue "Define the raw Excel format and template" "data-pipeline" @"
### Goal
One agreed layout for the Excel files extracted from the ledger photos, used by both the extraction and the pipeline.

### Tasks
- [ ] List the sheets and columns in one Python module (single source of truth)
- [ ] Script that generates an empty template workbook with a README sheet
- [ ] Every row keeps its source photo and an 'unclear' flag

### Done when
``python scripts/make_raw_template.py`` creates the template, and the loader uses the same column list.
"@

New-Issue "Test the Excel loader and report missing columns" "data-pipeline" @"
### Goal
The loader reads every sheet as text and warns when expected columns are missing.

### Tasks
- [ ] Report missing and unexpected columns per sheet
- [ ] Tests with a small fake workbook (no real data in tests)

### Done when
``pytest`` passes and a workbook with a missing column produces a clear message.
"@

New-Issue "Extract the test batch of ledger photos" "data-pipeline" @"
### Goal
Check extraction accuracy on 5-10 pages before doing the full ledgers.

### Tasks
- [ ] Photograph 5-10 pages (loans, repayments, minutes)
- [ ] Extract into the raw template
- [ ] Compare against paper; note the error rate and common misreads

### Done when
The test batch is in ``data/raw`` and its accuracy is recorded in this issue.
"@

New-Issue "Suggest name matches for member aliases" "data-pipeline" @"
### Goal
Group different spellings of the same member (e.g. 'J. Kamau', 'John Kamau') for human review.

### Tasks
- [ ] Fuzzy-match names within each Chama
- [ ] Write a review file of suggested matches
- [ ] Load the reviewed matches into private.member_aliases

### Done when
Every raw name maps to one canonical name after review.
"@

New-Issue "Anonymise: move raw data to staging with member codes" "data-pipeline" @"
### Goal
Replace names with member codes so nothing after this step sees real names.

### Tasks
- [ ] Build private.member_codes from the aliases
- [ ] Copy raw tables to staging with codes instead of names
- [ ] Test that no name appears in any staging table

### Done when
``python -m chama.pipeline anonymise`` fills staging and the test passes.
"@

New-Issue "Clean dates, amounts and statuses" "data-pipeline" @"
### Goal
Turn handwritten values into proper types.

### Tasks
- [ ] Parse the date styles found in the ledgers
- [ ] Parse amounts such as '300,000', '300000/=', '300k'
- [ ] Standardise attendance statuses
- [ ] Rows that cannot be parsed are flagged, not dropped

### Done when
Clean tables exist in analytics, with a count of flagged rows.
"@

New-Issue "Link repayments to their loans" "data-pipeline" @"
### Goal
Know, for every loan, what was repaid and when, so default can be defined.

### Tasks
- [ ] Match repayments to loans (by reference, or by member and date order)
- [ ] Apply the one-year due date rule
- [ ] Flag repayments that cannot be matched

### Done when
Each loan has its repayment history and an outstanding balance at the due date.
"@

New-Issue "Data quality checks and report" "data-pipeline" @"
### Goal
Automatic checks that catch bad data before modelling.

### Tasks
- [ ] pandera checks on staging and clean tables
- [ ] Simple report: row counts, flagged rows, missing values per Chama and year

### Done when
The pipeline stops with a clear message when a check fails, and the report is produced on success.
"@

New-Issue "Run the whole pipeline with one command and document it" "docs" @"
### Goal
``python -m chama.pipeline all`` runs every step in order; README and diagram match the code.

### Done when
A fresh database can be filled end to end with one command.
"@
