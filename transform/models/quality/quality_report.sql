-- Data quality report: counts per Chama and year, printed and saved by
-- `python -m chama.pipeline clean`. One row per measure.

with meetings as (
    select *, extract(year from meeting_month)::int as year from {{ ref('meetings') }}
),

statements as (
    select *, extract(year from meeting_month)::int as year from {{ ref('statements') }}
),

new_loans as (
    select *, extract(year from meeting_month)::int as year from {{ ref('new_loans') }}
),

attendance as (
    select *, extract(year from meeting_month)::int as year from {{ ref('attendance') }}
),

loan_lines as (
    select *, extract(year from meeting_month)::int as year from {{ ref('loan_lines') }}
),

loans as (
    select *, extract(year from first_month)::int as year from {{ ref('loans') }}
),

measures as (
    select chama_id, year, 'meetings' as table_name, m.*
    from (
        select
            chama_id, year,
            count(*) as pages,
            count(*) filter (where issues is not null) as flagged,
            count(*) filter (where unclear) as unclear_in_ledger,
            count(*) filter (where date_source = 'previous_page') as dated_from_previous_page,
            count(*) filter (where date_source = 'estimated') as dated_by_estimate
        from meetings
        group by chama_id, year
    ) as agg
    cross join lateral (values
        (1, 'pages', pages),
        (2, 'flagged', flagged),
        (3, 'unclear in ledger', unclear_in_ledger),
        (4, 'dated from previous page', dated_from_previous_page),
        (5, 'dated by estimate', dated_by_estimate)
    ) as m(measure_order, measure, value)

    union all

    select chama_id, year, 'statements', m.*
    from (
        select
            chama_id, year,
            count(*) as lines,
            count(*) filter (where issues is not null) as flagged,
            count(*) filter (where unclear) as unclear_in_ledger,
            count(*) filter (where line_kind = 'empty') as empty_lines,
            count(*) filter (where line_kind = 'balance' and loan_after is null) as no_balance_after,
            count(*) filter (where line_kind = 'balance' and interest_rate_pct is null
                and interest_amount is null) as no_interest,
            count(*) filter (where line_kind in ('balance', 'loan_given')
                and due_month is null) as no_due_month,
            count(*) filter (where due_year_inferred) as due_year_inferred
        from statements
        group by chama_id, year
    ) as agg
    cross join lateral (values
        (10, 'lines', lines),
        (11, 'flagged', flagged),
        (12, 'unclear in ledger', unclear_in_ledger),
        (13, 'empty lines', empty_lines),
        (14, 'no balance after', no_balance_after),
        (15, 'no interest', no_interest),
        (16, 'no due month', no_due_month),
        (17, 'due year inferred', due_year_inferred)
    ) as m(measure_order, measure, value)

    union all

    select chama_id, year, 'new_loans', m.*
    from (
        select
            chama_id, year,
            count(*) as loans_listed,
            count(*) filter (where issues is not null) as flagged,
            count(*) filter (where member_code is null) as no_member
        from new_loans
        group by chama_id, year
    ) as agg
    cross join lateral (values
        (20, 'loans listed', loans_listed),
        (21, 'flagged', flagged),
        (22, 'no member', no_member)
    ) as m(measure_order, measure, value)

    union all

    select chama_id, year, 'attendance', m.*
    from (
        select
            chama_id, year,
            count(*) as rows_,
            count(*) filter (where issues is not null) as flagged
        from attendance
        group by chama_id, year
    ) as agg
    cross join lateral (values
        (30, 'rows', rows_),
        (31, 'flagged', flagged)
    ) as m(measure_order, measure, value)

    union all

    select chama_id, year, 'loan_lines', m.*
    from (
        select
            chama_id, year,
            count(*) filter (where link = 'start') as loan_starts,
            count(*) filter (where link like 'continued%') as continued,
            count(*) filter (where link = 'continued_with_top_up') as with_top_up,
            count(*) filter (where link = 'repayment_unlinked') as repayment_unlinked,
            count(*) filter (where link like 'continued%'
                and carry_difference > 0.02 * loan_before) as carry_difference_over_2pct
        from loan_lines
        group by chama_id, year
    ) as agg
    cross join lateral (values
        (40, 'loan starts', loan_starts),
        (41, 'continued', continued),
        (42, 'with top-up', with_top_up),
        (43, 'repayment unlinked', repayment_unlinked),
        (44, 'balance carried with >2% difference', carry_difference_over_2pct)
    ) as m(measure_order, measure, value)

    union all

    select chama_id, year, 'loans', m.*
    from (
        select
            chama_id, year,
            count(*) as loans,
            count(*) filter (where loan_type = 'normal') as normal,
            count(*) filter (where loan_type = 'emergency') as emergency,
            count(*) filter (where issue_source = 'before_records') as before_records,
            count(*) filter (where issue_source = 'estimated') as issue_month_estimated,
            count(*) filter (where status = 'repaid_on_time') as repaid_on_time,
            count(*) filter (where status = 'repaid_late') as repaid_late,
            count(*) filter (where status = 'overdue') as overdue,
            count(*) filter (where status in ('open', 'open_no_due_date')) as open,
            count(*) filter (where status = 'lost_track') as lost_track,
            count(*) filter (where loan_type = 'normal' and due_source = 'ledger'
                and rule_due_month is not null and due_month <> rule_due_month)
                as due_differs_from_rule
        from loans
        group by chama_id, year
    ) as agg
    cross join lateral (values
        (50, 'loans', loans),
        (51, 'normal', normal),
        (52, 'emergency', emergency),
        (53, 'started before records', before_records),
        (54, 'issue month estimated', issue_month_estimated),
        (55, 'repaid on time', repaid_on_time),
        (56, 'repaid late', repaid_late),
        (57, 'overdue', overdue),
        (58, 'open', open),
        (59, 'lost track', lost_track),
        (60, 'ledger due differs from loan_term_days', due_differs_from_rule)
    ) as m(measure_order, measure, value)
)

select chama_id, year, table_name, measure_order, measure, value::int as value
from measures
