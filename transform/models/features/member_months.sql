-- One row per member per meeting while the member carries a loan: what the
-- Chama knew after that meeting (the features) and whether the member missed a
-- repayment in the next warning_horizon_meetings meetings (the label). This is
-- the early-warning target (decision D-021), beside the loan-default target in
-- loan_features.
--
-- Point in time: features use this meeting and earlier ones only.
--
-- A missed repayment is a ledger line of a running loan (balance before above
-- 0) with no repayment written. Meetings are counted in order (meeting_seq),
-- not by page number: page numbers skip where a photo was retaken (p051).
--
-- Label:
--   missed_ahead   1 if a repayment is missed in the next warning_horizon_meetings
--                  meetings, 0 if not, empty when the records end too soon to know
--   in_training    the label is known
--   outcome_month  the month of the last of those meetings, when the label is
--                  known; a model tested on a year learns only from rows known
--                  before it
-- "Recent" means the history_months up to and including this meeting.

{% set horizon = var('warning_horizon_meetings') %}
{% set recent = "(" ~ var('history_months') ~ " * interval '1 month')" %}

with lines as (
    select * from {{ ref('loan_lines') }}
    where loan_id is not null
),

loans as (
    select
        *,
        coalesce(amount_given, first_balance) as amount,
        coalesce(issued_month, first_month) as started_month
    from {{ ref('loans') }}
),

pages as (
    select
        chama_id,
        page_no,
        meeting_month,
        row_number() over (partition by chama_id order by page_no) as meeting_seq
    from {{ ref('meetings') }}
),

records_end as (
    select chama_id, max(meeting_seq) as last_seq from pages group by chama_id
),

statements as (
    select chama_id, member_code, page_no, meeting_month, monthly_amount
    from {{ ref('statements') }}
    where member_code is not null
),

-- every meeting where a member had a loan running: was a repayment missed?
repayments as (
    select
        lines.chama_id,
        lines.member_code,
        pages.meeting_seq,
        lines.meeting_month,
        bool_or(coalesce(lines.repayment, 0) = 0) as missed,
        avg(least(coalesce(lines.repayment, 0) / lines.opening_balance, 1)) as repayment_ratio
    from lines
    inner join pages on pages.chama_id = lines.chama_id and pages.page_no = lines.page_no
    where lines.line_kind = 'balance' and lines.opening_balance > 0
    group by lines.chama_id, lines.member_code, pages.meeting_seq, lines.meeting_month
),

-- members carrying a loan after the meeting
observations as (
    select
        lines.chama_id,
        lines.member_code,
        lines.page_no,
        pages.meeting_seq,
        lines.meeting_month,
        count(distinct lines.loan_id) as open_loans,
        sum(lines.closing_balance) as outstanding,
        bool_or(lines.line_seq = 1) as loan_started_this_meeting,
        bool_or(loans.loan_type = 'emergency') as has_emergency_loan,
        bool_or(loans.loan_type = 'school_fees') as has_school_fees_loan,
        max(
            (extract(year from age(lines.meeting_month, loans.started_month)) * 12
                + extract(month from age(lines.meeting_month, loans.started_month)))::int
        ) as oldest_open_loan_months
    from lines
    inner join loans on loans.loan_id = lines.loan_id
    inner join pages on pages.chama_id = lines.chama_id and pages.page_no = lines.page_no
    where lines.closing_balance > 0
    group by lines.chama_id, lines.member_code, lines.page_no, pages.meeting_seq,
        lines.meeting_month
),

history as (
    select
        observations.chama_id,
        observations.member_code,
        observations.page_no,
        count(*) filter (where past.missed and past.meeting_seq > observations.meeting_seq - 3)
            as missed_last_3_meetings,
        count(*) filter (where past.missed
            and past.meeting_month > observations.meeting_month - {{ recent }}) as recent_missed,
        count(*) filter (where past.meeting_month > observations.meeting_month - {{ recent }})
            as recent_balance_lines,
        avg(past.repayment_ratio) filter (where past.meeting_seq > observations.meeting_seq - 3)
            as repayment_ratio_last_3_meetings,
        max(past.meeting_month) filter (where past.missed) as last_missed_month
    from observations
    inner join repayments as past
        on past.chama_id = observations.chama_id
        and past.member_code = observations.member_code
        and past.meeting_seq <= observations.meeting_seq
    group by observations.chama_id, observations.member_code, observations.page_no
),

chama_this_meeting as (
    select chama_id, meeting_seq, avg(missed::int) as chama_missed_share
    from repayments
    group by chama_id, meeting_seq
),

earlier_loans as (
    select
        observations.chama_id,
        observations.member_code,
        observations.page_no,
        count(*) filter (where loans.started_month <= observations.meeting_month) as loans_so_far,
        count(*) filter (where rolled_into.issued_month <= observations.meeting_month)
            as prior_rolled_over
    from observations
    inner join loans
        on loans.chama_id = observations.chama_id
        and loans.member_code = observations.member_code
    left join loans as rolled_into on rolled_into.loan_id = loans.rolled_into_loan_id
    group by observations.chama_id, observations.member_code, observations.page_no
),

chama_typical as (
    -- the Chama's median normal loan in the recent months
    select
        observations.chama_id,
        observations.page_no,
        percentile_cont(0.5) within group (order by loans.amount) as chama_median_loan
    from (select distinct chama_id, page_no, meeting_month from observations) as observations
    inner join loans
        on loans.chama_id = observations.chama_id
        and loans.loan_type = 'normal'
        and loans.issued_month <= observations.meeting_month
        and loans.issued_month > observations.meeting_month - {{ recent }}
    group by observations.chama_id, observations.page_no
),

contribution_pages as (
    select chama_id, page_no, meeting_month
    from statements
    group by chama_id, page_no, meeting_month
    having bool_or(monthly_amount > 0)
),

contributions as (
    select
        observations.chama_id,
        observations.member_code,
        observations.page_no,
        count(*) as recent_contribution_meetings,
        count(paid.page_no) as recent_contributions_paid
    from observations
    inner join contribution_pages as cp
        on cp.chama_id = observations.chama_id
        and cp.meeting_month <= observations.meeting_month
        and cp.meeting_month > observations.meeting_month - {{ recent }}
    left join lateral (
        select statements.page_no
        from statements
        where statements.chama_id = cp.chama_id
            and statements.page_no = cp.page_no
            and statements.member_code = observations.member_code
            and statements.monthly_amount > 0
        limit 1
    ) as paid on true
    group by observations.chama_id, observations.member_code, observations.page_no
),

membership as (
    select chama_id, member_code, min(meeting_month) as first_seen_month
    from statements
    group by chama_id, member_code
),

ahead as (
    -- the next warning_horizon_meetings meetings
    select
        observations.chama_id,
        observations.member_code,
        observations.page_no,
        coalesce(bool_or(next.missed), false) as missed_ahead
    from observations
    left join repayments as next
        on next.chama_id = observations.chama_id
        and next.member_code = observations.member_code
        and next.meeting_seq between observations.meeting_seq + 1
            and observations.meeting_seq + {{ horizon }}
    group by observations.chama_id, observations.member_code, observations.page_no
)

select
    o.chama_id || ':' || o.member_code || ':p' || lpad(o.page_no::text, 3, '0') as member_month_id,
    o.chama_id,
    o.member_code,
    o.page_no,
    o.meeting_month,
    extract(year from o.meeting_month)::int as meeting_year,
    extract(month from o.meeting_month)::int as month_of_year,

    -- the member's loans after this meeting
    o.open_loans,
    round((o.outstanding / nullif(chama_typical.chama_median_loan, 0))::numeric, 3)::float
        as outstanding_vs_chama_median,
    o.oldest_open_loan_months,
    o.loan_started_this_meeting,
    o.has_emergency_loan,
    o.has_school_fees_loan,

    -- the member's record up to this meeting
    (extract(year from age(o.meeting_month, membership.first_seen_month)) * 12
        + extract(month from age(o.meeting_month, membership.first_seen_month)))::int
        as months_in_records,
    earlier_loans.loans_so_far,
    earlier_loans.prior_rolled_over,
    coalesce(history.missed_last_3_meetings, 0) as missed_last_3_meetings,
    coalesce(history.recent_missed, 0) as recent_missed,
    round((history.recent_missed::numeric / nullif(history.recent_balance_lines, 0)), 3)::float
        as recent_missed_share,
    round(history.repayment_ratio_last_3_meetings::numeric, 3)::float
        as repayment_ratio_last_3_meetings,
    (extract(year from age(o.meeting_month, history.last_missed_month)) * 12
        + extract(month from age(o.meeting_month, history.last_missed_month)))::int
        as months_since_last_miss,
    round((contributions.recent_contributions_paid::numeric
        / contributions.recent_contribution_meetings), 3)::float as recent_contribution_rate,

    -- the Chama at this meeting
    round(chama_this_meeting.chama_missed_share::numeric, 3)::float as chama_missed_share,

    -- the label
    case when o.meeting_seq + {{ horizon }} <= records_end.last_seq
        then ahead.missed_ahead::int end as missed_ahead,
    o.meeting_seq + {{ horizon }} <= records_end.last_seq as in_training,
    case when o.meeting_seq + {{ horizon }} <= records_end.last_seq
        then horizon_page.meeting_month end as outcome_month
from observations as o
inner join records_end on records_end.chama_id = o.chama_id
inner join ahead
    on ahead.chama_id = o.chama_id and ahead.member_code = o.member_code
    and ahead.page_no = o.page_no
inner join earlier_loans
    on earlier_loans.chama_id = o.chama_id and earlier_loans.member_code = o.member_code
    and earlier_loans.page_no = o.page_no
left join history
    on history.chama_id = o.chama_id and history.member_code = o.member_code
    and history.page_no = o.page_no
left join chama_this_meeting
    on chama_this_meeting.chama_id = o.chama_id
    and chama_this_meeting.meeting_seq = o.meeting_seq
left join chama_typical
    on chama_typical.chama_id = o.chama_id and chama_typical.page_no = o.page_no
left join contributions
    on contributions.chama_id = o.chama_id and contributions.member_code = o.member_code
    and contributions.page_no = o.page_no
left join membership
    on membership.chama_id = o.chama_id and membership.member_code = o.member_code
left join pages as horizon_page
    on horizon_page.chama_id = o.chama_id
    and horizon_page.meeting_seq = o.meeting_seq + {{ horizon }}
