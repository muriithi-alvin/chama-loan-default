-- One row per loan: when it was given, when it fell due, what was repaid and
-- the balance outstanding at the due date.
--
-- loan_type: from the list of loans given, else the mark beside the name
--   (Em = emergency), else emergency when the rate is 5% or more or the loan is
--   repaid with a premium at its first appearance, else normal.
--
-- issue_source (when the loan was given):
--   loan_given_line  written into the statement table at the meeting it was given
--   before_records   already running on the first page of the records (date unknown)
--   new_loans_list   matched to the list of loans given at a meeting
--   estimated        the meeting before the loan first appears
-- due_source:
--   ledger                the due month written beside the loan (most common one)
--   ledger_year_inferred  written without a year
--   rule                  not written: loan_term_days (emergency_term_days for
--                         emergency loans) after it was given
-- status: repaid_on_time, repaid_late, repaid (no due date known),
--   topped_up (the unpaid balance was rolled into a bigger loan of the same
--   member and type that starts within max_pages_between_lines pages; see
--   rolled_into_loan_id), overdue, open (not yet due when the records end),
--   open_no_due_date, lost_track (the loan stops appearing while the records
--   go on)

with lines as (
    select * from {{ ref('loan_lines') }}
    where loan_id is not null
),

coverage as (
    select
        chama_id,
        min(page_no) as first_page,
        max(page_no) as last_page,
        max(meeting_month) as observed_until
    from {{ ref('meetings') }}
    group by chama_id
),

starts as (
    select * from lines where line_seq = 1
),

summary as (
    select
        loan_id,
        count(*) as line_count,
        max(page_no) as last_page,
        max(meeting_month) as last_month,
        min(meeting_month) filter (where closing_balance = 0) as cleared_month,
        max(interest_rate_pct) as max_interest_rate_pct,
        sum(coalesce(repayment, 0)) as total_repaid,
        sum(coalesce(top_up_amount, 0)) as total_top_ups,
        mode() within group (order by due_month)
            filter (where due_month is not null and not due_year_inferred) as due_written,
        mode() within group (order by due_month)
            filter (where due_month is not null) as due_any,
        bool_or(unclear) as any_unclear,
        -- type marked beside the name on any of the loan's lines
        max(loan_type) filter (where loan_type in ('emergency', 'school_fees')) as marked_type
    from lines
    group by loan_id
),

last_line as (
    select distinct on (loan_id) loan_id, closing_balance as last_balance
    from lines
    order by loan_id, line_seq desc
),

issued as (
    select
        starts.loan_id,
        starts.chama_id,
        starts.member_code,
        starts.page_no as first_page,
        starts.meeting_month as first_month,
        starts.loan_before as first_balance,
        starts.line_kind as first_line_kind,
        starts.repayment as first_repayment,
        listed.loan_type as listed_type,
        case
            when starts.line_kind = 'loan_given' then starts.meeting_month
            when starts.page_no = coverage.first_page then null
            when listed.loan_month is not null then listed.loan_month
            else coalesce(
                previous_meeting.meeting_month,
                (starts.meeting_month - interval '1 month')::date
            )
        end as issued_month,
        case
            when starts.line_kind = 'loan_given' then 'loan_given_line'
            when starts.page_no = coverage.first_page then 'before_records'
            when listed.loan_month is not null then 'new_loans_list'
            else 'estimated'
        end as issue_source,
        case
            when starts.line_kind = 'loan_given' then starts.loan_before
            else listed.amount
        end as amount_given,
        coverage.last_page as records_last_page,
        coverage.observed_until
    from starts
    inner join coverage on coverage.chama_id = starts.chama_id
    -- A loan is listed at the meeting it was given: the same page for a
    -- loan_given line, otherwise the page before it first appears (or the same
    -- page when the list is dated earlier, e.g. "?/6/2014" on the July page).
    left join lateral (
        select new_loans.loan_month, new_loans.loan_type, new_loans.amount
        from {{ ref('new_loans') }} as new_loans
        where new_loans.chama_id = starts.chama_id
            and new_loans.member_code = starts.member_code
            and abs(new_loans.amount - starts.loan_before)
                <= greatest(starts.loan_before * {{ var('carry_tolerance') }}, 100)
            and case
                when starts.line_kind = 'loan_given' then new_loans.page_no = starts.page_no
                else new_loans.page_no = starts.page_no - 1
                    or (new_loans.page_no = starts.page_no
                        and new_loans.loan_month < starts.meeting_month)
            end
        order by abs(new_loans.amount - starts.loan_before), new_loans.page_no desc
        limit 1
    ) as listed on true
    left join lateral (
        select meetings.meeting_month
        from {{ ref('meetings') }} as meetings
        where meetings.chama_id = starts.chama_id and meetings.page_no < starts.page_no
        order by meetings.page_no desc
        limit 1
    ) as previous_meeting on true
),

typed as (
    select
        issued.*,
        summary.line_count,
        summary.last_page,
        summary.last_month,
        summary.cleared_month,
        summary.max_interest_rate_pct,
        summary.total_repaid,
        summary.total_top_ups,
        summary.due_written,
        summary.due_any,
        summary.any_unclear,
        last_line.last_balance,
        case
            when issued.listed_type in ('emergency', 'school_fees') then issued.listed_type
            when summary.marked_type is not null then summary.marked_type
            when issued.listed_type is not null then 'normal'
            when summary.max_interest_rate_pct >= 5 then 'emergency'
            -- a short loan repaid with a premium at its first appearance
            when summary.line_count = 1 and issued.first_repayment > issued.first_balance
                then 'emergency'
            else 'normal'
        end as loan_type
    from issued
    inner join summary on summary.loan_id = issued.loan_id
    inner join last_line on last_line.loan_id = issued.loan_id
),

due as (
    select
        *,
        date_trunc('month', issued_month + case when loan_type = 'emergency'
            then {{ var('emergency_term_days') }} else {{ var('loan_term_days') }} end
        )::date as rule_due_month
    from typed
),

with_due as (
    select
        *,
        coalesce(due_written, due_any, rule_due_month) as due_month,
        case
            when due_written is not null then 'ledger'
            when due_any is not null then 'ledger_year_inferred'
            when rule_due_month is not null then 'rule'
        end as due_source
    from due
),

rolled as (
    -- An unpaid loan followed within a few pages by a bigger loan of the same
    -- member and type: the balance was rolled into the new loan (a top-up
    -- that the list of new loans does not show).
    select distinct on (old.loan_id)
        old.loan_id,
        new.loan_id as rolled_into_loan_id
    from with_due as old
    inner join with_due as new
        on new.chama_id = old.chama_id
        and new.member_code = old.member_code
        and new.loan_type = old.loan_type
        and new.loan_id <> old.loan_id
        and new.first_page > old.last_page
        and new.first_page <= old.last_page + {{ var('max_pages_between_lines') }}
        and new.first_balance >= old.last_balance
    where old.cleared_month is null and old.last_balance > 0
    order by old.loan_id, new.first_page
),

at_due as (
    select distinct on (lines.loan_id)
        lines.loan_id,
        lines.closing_balance as balance_at_due
    from lines
    inner join with_due on with_due.loan_id = lines.loan_id
    where lines.meeting_month <= with_due.due_month
    order by lines.loan_id, lines.line_seq desc
)

select
    with_due.loan_id,
    with_due.chama_id,
    with_due.member_code,
    with_due.loan_type,
    with_due.issued_month,
    with_due.issue_source,
    with_due.amount_given,
    with_due.first_balance,
    with_due.total_top_ups,
    with_due.total_repaid,
    with_due.max_interest_rate_pct,
    with_due.due_month,
    with_due.due_source,
    with_due.rule_due_month,
    with_due.cleared_month,
    with_due.last_balance,
    -- 0 if repaid by the due month; otherwise only known when the due month
    -- falls inside the records (for a topped-up loan: before it was rolled over)
    case
        when with_due.cleared_month <= with_due.due_month then 0
        when rolled.loan_id is not null and with_due.due_month > with_due.last_month then null
        when with_due.due_month <= with_due.observed_until
            then coalesce(at_due.balance_at_due, with_due.first_balance)
    end as outstanding_at_due,
    case when with_due.cleared_month > with_due.due_month then
        (extract(year from age(with_due.cleared_month, with_due.due_month)) * 12
            + extract(month from age(with_due.cleared_month, with_due.due_month)))::int
    end as months_late,
    case
        when with_due.cleared_month is not null and with_due.due_month is null then 'repaid'
        when with_due.cleared_month <= with_due.due_month then 'repaid_on_time'
        when with_due.cleared_month is not null then 'repaid_late'
        when rolled.loan_id is not null then 'topped_up'
        when with_due.last_page
            < with_due.records_last_page - {{ var('max_pages_between_lines') }} then 'lost_track'
        when with_due.due_month is null then 'open_no_due_date'
        when with_due.due_month < with_due.observed_until then 'overdue'
        else 'open'
    end as status,
    rolled.rolled_into_loan_id,
    with_due.line_count,
    with_due.first_month,
    with_due.first_page,
    with_due.last_page,
    with_due.observed_until,
    with_due.any_unclear
from with_due
left join at_due on at_due.loan_id = with_due.loan_id
left join rolled on rolled.loan_id = with_due.loan_id
