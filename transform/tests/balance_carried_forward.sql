-- A member's balance before should equal the balance carried from the last
-- meeting. Differences over 2% are usually misread or overwritten figures:
-- check them against the photos. Warns rather than stops, because raw data
-- must match the ledger even where the ledger is inconsistent.
{{ config(severity='warn') }}

select line_id, loan_id, source_photo, loan_before, carry_difference
from {{ ref('loan_lines') }}
where link like 'continued%'
    and carry_difference > 0.02 * loan_before
