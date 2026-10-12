-- Every statement line, tied to the loan it belongs to.
--
-- The ledger has no loan numbers, so lines are chained: a line continues an
-- earlier line of the same member (up to max_pages_between_lines pages back)
-- when its balance before matches that line's closing balance, or that
-- balance plus a loan given to the member at that meeting (a top-up). The
-- difference may be up to carry_tolerance of the balance. Each line prefers an
-- earlier line of the same loan type (normal, emergency, school fees), then
-- the nearest page, then the closest balance, and each earlier line is
-- continued at most once (both must choose each other). A line that continues
-- nothing starts a new loan.
--
-- link:
--   start                     first line of a loan
--   continued                 same loan as an earlier line
--   continued_with_top_up     same loan, with a top-up given at the earlier meeting
--   repayment_unlinked        a repayment that cannot be tied to any loan
--   not_a_loan                an empty line

with recursive

lines as (
    select * from {{ ref('statements') }}
),

loan_lines as (
    select * from lines
    where member_code is not null
        and page_no is not null
        and line_kind in ('balance', 'loan_given')
),

new_loans_per_page as (
    select chama_id, member_code, page_no, sum(amount) as new_amount
    from {{ ref('new_loans') }}
    where member_code is not null and amount is not null and page_no is not null
    group by chama_id, member_code, page_no
),

candidates as (
    select
        cur.line_id,
        prev.line_id as previous_line_id,
        cur.page_no - prev.page_no as pages_apart,
        case when coalesce(nullif(cur.loan_type, 'top_up'), 'normal')
            = coalesce(nullif(prev.loan_type, 'top_up'), 'normal') then 0 else 1 end as type_mismatch,
        abs(cur.loan_before - prev.closing_balance) as plain_difference,
        abs(cur.loan_before - (prev.closing_balance + coalesce(topup.new_amount, 0)))
            as top_up_difference,
        topup.new_amount
    from loan_lines as cur
    inner join loan_lines as prev
        on prev.chama_id = cur.chama_id
        and prev.member_code = cur.member_code
        and prev.page_no < cur.page_no
        and prev.page_no >= cur.page_no - {{ var('max_pages_between_lines') }}
        and prev.closing_balance > 0
    left join new_loans_per_page as topup
        on topup.chama_id = prev.chama_id
        and topup.member_code = prev.member_code
        and topup.page_no = prev.page_no
    -- a balance-only line (loan_given) can also carry an unpaid balance forward;
    -- it starts a new loan only when no open balance matches
    where cur.line_kind in ('balance', 'loan_given')
        and cur.loan_before > 0
),

scored as (
    select
        *,
        least(plain_difference, top_up_difference) as difference,
        case when top_up_difference < plain_difference then new_amount end as top_up_amount
    from candidates
),

allowed as (
    select scored.*
    from scored
    inner join loan_lines as cur on cur.line_id = scored.line_id
    where scored.difference
        <= greatest(cur.loan_before * {{ var('carry_tolerance') }}, 100)
),

ranked as (
    select
        *,
        row_number() over (
            partition by line_id order by type_mismatch, pages_apart, difference, previous_line_id
        ) as rank_for_line,
        row_number() over (
            partition by previous_line_id order by type_mismatch, pages_apart, difference, line_id
        ) as rank_for_previous
    from allowed
),

links as (
    select line_id, previous_line_id, difference, top_up_amount
    from ranked
    where rank_for_line = 1 and rank_for_previous = 1
),

chains (line_id, start_line_id, line_seq) as (
    select loan_lines.line_id, loan_lines.line_id, 1
    from loan_lines
    left join links on links.line_id = loan_lines.line_id
    where links.line_id is null
    union all
    select links.line_id, chains.start_line_id, chains.line_seq + 1
    from chains
    inner join links on links.previous_line_id = chains.line_id
),

starts as (
    select
        line_id as start_line_id,
        chama_id || '-p' || lpad(page_no::text, 3, '0') || '-' || line_on_page as loan_id
    from lines
)

select
    starts.loan_id,
    chains.line_seq,
    lines.line_id,
    lines.chama_id,
    lines.member_code,
    lines.page_no,
    lines.meeting_month,
    lines.line_kind,
    lines.loan_type,
    lines.loan_before,
    lines.repayment,
    lines.interest_rate_pct,
    lines.interest_amount,
    lines.loan_after,
    lines.closing_balance,
    -- the loan's balance when this line opens (a new loan written only in the
    -- balance-after column opens at that balance)
    coalesce(nullif(lines.loan_before, 0), lines.closing_balance) as opening_balance,
    lines.closing_estimated,
    lines.due_month,
    lines.due_year_inferred,
    lines.unclear,
    links.previous_line_id,
    links.difference as carry_difference,
    links.top_up_amount,
    case
        when chains.line_seq = 1 then 'start'
        when links.top_up_amount is not null then 'continued_with_top_up'
        when chains.line_seq > 1 then 'continued'
        when lines.line_kind = 'repayment_only' and lines.repayment > 0 then 'repayment_unlinked'
        else 'not_a_loan'
    end as link,
    lines.source_photo,
    lines.source_row
from lines
left join chains on chains.line_id = lines.line_id
left join starts on starts.start_line_id = chains.start_line_id
left join links on links.line_id = lines.line_id
