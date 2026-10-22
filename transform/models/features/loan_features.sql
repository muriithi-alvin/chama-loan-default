-- One row per loan with a known issue month: what the Chama knew about the
-- member when the loan was given (the features) and how the loan ended (the
-- label). This is the table the models learn from (Milestone 2).
--
-- Point in time (decision D-018): every feature uses only meetings before the
-- issue month, and earlier loans as they stood then, so nothing from after the
-- decision leaks in. Loans already running on the first page have no issue
-- month and no history, so they are left out.
--
-- Label (provisional until agreed with the Chama, D-018):
--   defaulted      1 when the status is one of default_statuses
--                  (config/pipeline.yaml), 0 for the other finished loans,
--                  empty while the outcome is unknown (open, open_no_due_date)
--   in_training    true when the outcome is known, so models may learn from it
--   outcome_month  when the outcome became known: the month a loan was cleared,
--                  the month the loan it was rolled into was given, the month
--                  after it fell due unpaid (overdue), or max_pages_between_lines
--                  months after its last line (lost_track). A model tested on a
--                  year may only learn from loans whose outcome was known before
--                  that year (decision D-020).
--
-- "Recent" means the history_months before the issue month. A loan is open at
-- issue when its last line before the issue month, at most
-- max_pages_between_lines months back, carries a balance, and it has not been
-- rolled into a loan given before (its balance then lives in that loan).

{% set default_statuses = var('default_statuses') %}
{% set recent = "(" ~ var('history_months') ~ " * interval '1 month')" %}
{% set running = "(" ~ var('max_pages_between_lines') ~ " * interval '1 month')" %}

with loans as (
    select
        *,
        coalesce(amount_given, first_balance) as amount,
        -- loans running on the first page started before any later request
        coalesce(issued_month, first_month) as started_month
    from {{ ref('loans') }}
),

lines as (
    select * from {{ ref('loan_lines') }}
    where loan_id is not null
),

statements as (
    select chama_id, member_code, page_no, meeting_month, monthly_amount
    from {{ ref('statements') }}
    where member_code is not null
),

requests as (
    select * from loans
    where issued_month is not null
),

-- The member's loans that started before the request, with the month the
-- loan each was rolled into was given.
earlier as (
    select
        requests.loan_id as request_id,
        earlier.*,
        rolled_into.issued_month as rolled_into_month
    from requests
    inner join loans as earlier
        on earlier.chama_id = requests.chama_id
        and earlier.member_code = requests.member_code
        and earlier.started_month < requests.issued_month
    left join loans as rolled_into on rolled_into.loan_id = earlier.rolled_into_loan_id
),

history as (
    select
        requests.loan_id,
        count(earlier.loan_id) as prior_loans,
        count(*) filter (where earlier.cleared_month < requests.issued_month) as prior_repaid,
        count(*) filter (where earlier.cleared_month < requests.issued_month
            and earlier.status = 'repaid_late') as prior_repaid_late,
        count(*) filter (where earlier.rolled_into_month < requests.issued_month)
            as prior_rolled_over,
        count(*) filter (where earlier.loan_type = 'emergency'
            and earlier.issued_month >= requests.issued_month - {{ recent }})
            as recent_emergency_loans,
        count(*) filter (where earlier.loan_type = 'school_fees'
            and earlier.issued_month >= requests.issued_month - {{ recent }})
            as recent_school_fees_loans,
        max(earlier.amount) filter (where earlier.loan_type = requests.loan_type)
            as own_max_amount,
        bool_or(earlier.rolled_into_loan_id = requests.loan_id) as is_rollover
    from requests
    left join earlier on earlier.request_id = requests.loan_id
    group by requests.loan_id
),

open_at_issue as (
    select
        requests.loan_id,
        count(*) as open_loans_at_issue,
        sum(last_line.closing_balance) as outstanding_at_issue,
        max(
            (extract(year from age(requests.issued_month, earlier.started_month)) * 12
                + extract(month from age(requests.issued_month, earlier.started_month)))::int
        ) as oldest_open_loan_months
    from requests
    inner join earlier on earlier.request_id = requests.loan_id
    inner join lateral (
        select lines.closing_balance, lines.meeting_month
        from lines
        where lines.loan_id = earlier.loan_id
            and lines.meeting_month < requests.issued_month
        order by lines.line_seq desc
        limit 1
    ) as last_line on true
    where last_line.closing_balance > 0
        and last_line.meeting_month >= requests.issued_month - {{ running }}
        and coalesce(earlier.rolled_into_month >= requests.issued_month, true)
    group by requests.loan_id
),

repayments as (
    -- the member's statement lines on running loans in the recent months
    select
        requests.loan_id,
        count(*) as recent_balance_lines,
        count(*) filter (where coalesce(lines.repayment, 0) = 0) as recent_missed,
        avg(least(coalesce(lines.repayment, 0) / lines.opening_balance, 1))
            as recent_repayment_ratio
    from requests
    inner join lines
        on lines.chama_id = requests.chama_id
        and lines.member_code = requests.member_code
        and lines.meeting_month < requests.issued_month
        and lines.meeting_month >= requests.issued_month - {{ recent }}
        and lines.line_kind = 'balance'
        and lines.opening_balance > 0
    group by requests.loan_id
),

contribution_pages as (
    -- meetings where the Chama wrote down monthly contributions (from 2017)
    select chama_id, page_no, meeting_month
    from statements
    group by chama_id, page_no, meeting_month
    having bool_or(monthly_amount > 0)
),

contributions as (
    select
        requests.loan_id,
        count(*) as recent_contribution_meetings,
        count(paid.page_no) as recent_contributions_paid
    from requests
    inner join contribution_pages as pages
        on pages.chama_id = requests.chama_id
        and pages.meeting_month < requests.issued_month
        and pages.meeting_month >= requests.issued_month - {{ recent }}
    left join lateral (
        select statements.page_no
        from statements
        where statements.chama_id = pages.chama_id
            and statements.page_no = pages.page_no
            and statements.member_code = requests.member_code
            and statements.monthly_amount > 0
        limit 1
    ) as paid on true
    group by requests.loan_id
),

membership as (
    select
        requests.loan_id,
        min(statements.meeting_month) as first_seen_month
    from requests
    inner join statements
        on statements.chama_id = requests.chama_id
        and statements.member_code = requests.member_code
        and statements.meeting_month < requests.issued_month
    group by requests.loan_id
),

last_seen as (
    select loan_id, max(meeting_month) as last_line_month
    from lines
    group by loan_id
),

chama_typical as (
    -- the Chama's median loan of the same type in the recent months
    select
        requests.loan_id,
        percentile_cont(0.5) within group (order by others.amount) as chama_median_amount
    from requests
    inner join requests as others
        on others.chama_id = requests.chama_id
        and others.loan_type = requests.loan_type
        and others.issued_month < requests.issued_month
        and others.issued_month >= requests.issued_month - {{ recent }}
    group by requests.loan_id
)

select
    requests.loan_id,
    requests.chama_id,
    requests.member_code,
    requests.issued_month,
    extract(year from requests.issued_month)::int as issue_year,
    requests.issue_source,

    -- the request
    requests.loan_type,
    requests.amount::float as amount,
    coalesce(history.is_rollover, false) as is_rollover,
    round((requests.amount / nullif(history.own_max_amount, 0))::numeric, 3)::float
        as amount_vs_own_max,
    round((requests.amount / nullif(chama_typical.chama_median_amount, 0))::numeric, 3)::float
        as amount_vs_chama_median,

    -- the member's record before the request
    coalesce(
        (extract(year from age(requests.issued_month, membership.first_seen_month)) * 12
            + extract(month from age(requests.issued_month, membership.first_seen_month)))::int,
        0
    ) as months_in_records,
    history.prior_loans,
    history.prior_repaid,
    history.prior_repaid_late,
    history.prior_rolled_over,
    history.recent_emergency_loans,
    history.recent_school_fees_loans,
    coalesce(open_at_issue.open_loans_at_issue, 0) as open_loans_at_issue,
    coalesce(open_at_issue.outstanding_at_issue, 0)::float as outstanding_at_issue,
    open_at_issue.oldest_open_loan_months,
    coalesce(repayments.recent_balance_lines, 0) as recent_balance_lines,
    round((repayments.recent_missed::numeric / repayments.recent_balance_lines), 3)::float
        as recent_missed_share,
    round(repayments.recent_repayment_ratio::numeric, 3)::float as recent_repayment_ratio,
    round((contributions.recent_contributions_paid::numeric
        / contributions.recent_contribution_meetings), 3)::float as recent_contribution_rate,

    -- the outcome
    requests.status,
    case
        when requests.status in ('open', 'open_no_due_date') then null
        when requests.status in ('{{ default_statuses | join("', '") }}') then 1
        else 0
    end as defaulted,
    requests.status not in ('open', 'open_no_due_date') as in_training,
    case
        when requests.status in ('repaid_on_time', 'repaid_late', 'repaid')
            then requests.cleared_month
        when requests.status = 'topped_up' then rolled_into.issued_month
        when requests.status = 'overdue' then (requests.due_month + interval '1 month')::date
        when requests.status = 'lost_track' then (last_seen.last_line_month + {{ running }})::date
    end as outcome_month
from requests
inner join history on history.loan_id = requests.loan_id
left join loans as rolled_into on rolled_into.loan_id = requests.rolled_into_loan_id
left join last_seen on last_seen.loan_id = requests.loan_id
left join open_at_issue on open_at_issue.loan_id = requests.loan_id
left join repayments on repayments.loan_id = requests.loan_id
left join contributions on contributions.loan_id = requests.loan_id
left join membership on membership.loan_id = requests.loan_id
left join chama_typical on chama_typical.loan_id = requests.loan_id
