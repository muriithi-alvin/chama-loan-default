-- A balance should not grow by more than one month's interest (at most 5%)
-- between before and after. A bigger jump is usually a misread figure.
{{ config(severity='warn') }}

select line_id, source_photo, loan_before, repayment, interest_rate_pct, loan_after
from {{ ref('statements') }}
where line_kind = 'balance'
    -- 1% slack for rounding
    and loan_after > loan_before * (1 + greatest(coalesce(interest_rate_pct, 0), 5) / 100) * 1.01
