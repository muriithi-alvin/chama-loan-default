-- One row per member line on a ledger page, with typed values.
-- Rows that cannot be read are kept and listed in `issues`, never dropped.
--
-- line_kind:
--   balance        a running loan: balance before, repayment, balance after
--   loan_given     only a balance is written: a loan given at this meeting
--   repayment_only a repayment with no balance (cannot be tied to a loan)
--   no_loan        only dashes: the member has no loan this month
--   empty          a name with nothing else

with source as (
    select * from {{ source('staging', 'statements') }}
),

meetings as (
    select page_id, page_no, meeting_month, meeting_date from {{ ref('meetings') }}
),

typed as (
    select
        source.chama_id || ':' || source.source_file || ':' || source.source_row as line_id,
        source.chama_id || ':' || source.source_photo as page_id,
        source.chama_id,
        source.member_code,
        source.line_no as line_no_text,
        case when trim(source.line_no) ~ '^[0-9]+$' then trim(source.line_no)::int end as line_no,
        source.monthly as monthly_text,
        {{ parse_amount('source.monthly') }} as monthly_amount,
        source.loan_before as loan_before_text,
        {{ parse_amount('source.loan_before') }} as loan_before,
        source.repayment as repayment_text,
        {{ parse_amount('source.repayment') }} as repayment,
        source.interest as interest_text,
        case when {{ is_written('source.interest') }}
            then {{ parse_amount("replace(source.interest, '%', '')") }}
        end as interest_value,
        coalesce(source.interest, '') like '%\%%' as interest_has_percent,
        source.loan_after as loan_after_text,
        -- "Cleared" written as the balance means nothing is left
        case when lower(trim(source.loan_after)) like 'clear%' then 0
            else {{ parse_amount('source.loan_after') }}
        end as loan_after,
        source.due as due_text,
        lower(regexp_replace(trim(source.due), '[.,]', '', 'g')) as due_clean,
        lower(regexp_replace(trim(coalesce(source.loan_type, '')), '[().]', '', 'g'))
            as loan_type_text,
        upper(coalesce(trim(source.unclear), '')) = 'Y' as unclear,
        source.source_photo,
        source.source_file,
        source.source_row
    from source
),

with_meeting as (
    select
        typed.*,
        meetings.page_no,
        meetings.meeting_month,
        meetings.meeting_date,
        row_number() over (
            partition by typed.page_id order by typed.source_file, typed.source_row
        ) as line_on_page
    from typed
    left join meetings on meetings.page_id = typed.page_id
),

due_parts as (
    select
        *,
        coalesce(
            {{ month_number("substring(due_clean from '^([a-z]+)')") }},
            case when due_clean ~ '^[0-9]{1,2}/([0-9]{2}|[0-9]{4})$' then split_part(due_clean, '/', 1)::int end
        ) as due_month_no,
        coalesce(
            -- a year cut off to three digits ("Sept 201") counts as no year
            substring(due_clean from '^[a-z]+\s*([0-9]{4}|[0-9]{2})$'),
            substring(due_clean from '^[0-9]{1,2}/([0-9]{4}|[0-9]{2})$')
        ) as due_year_text
    from with_meeting
),

parsed as (
    select
        *,
        -- Interest is a rate ("2%", or a small number) or, in later years, an amount
        case when interest_has_percent or interest_value <= 20 then interest_value end
            as interest_rate_pct,
        case when not interest_has_percent and interest_value > 20 then interest_value end
            as interest_amount,
        case when due_month_no between 1 and 12 then
            case
                when due_year_text is not null then make_date(
                    case when length(due_year_text) = 2 then 2000 + due_year_text::int
                        else due_year_text::int end,
                    due_month_no, 1)
                -- No year written ("Aug"): the next such month after the meeting
                when meeting_month is not null then make_date(
                    extract(year from meeting_month)::int
                        + case when due_month_no > extract(month from meeting_month) then 0 else 1 end,
                    due_month_no, 1)
            end
        end as due_month,
        due_month_no is not null and due_year_text is null as due_year_inferred,
        -- Mark beside the name: Em / Eme / (Em) / (E) = emergency
        case
            when loan_type_text = '' then null
            when loan_type_text = 'e' or loan_type_text like 'em%' then 'emergency'
            when loan_type_text in ('sf', 's/f') or loan_type_text like 'school%' then 'school_fees'
            when loan_type_text like 'top%up%' then 'top_up'
            else 'other'
        end as loan_type
    from due_parts
),

final as (
    select
        *,
        case
            when loan_before is null and repayment is null and loan_after is null then 'empty'
            when coalesce(loan_before, 0) = 0 and coalesce(repayment, 0) = 0
                and coalesce(loan_after, 0) = 0 then 'no_loan'
            when loan_before is null then 'repayment_only'
            -- only a balance written (a "?" or other unreadable value is not blank)
            when repayment is null and loan_after is null
                and not {{ is_written('repayment_text') }}
                and not {{ is_written('loan_after_text') }} then 'loan_given'
            else 'balance'
        end as line_kind
    from parsed
)

select
    line_id,
    page_id,
    chama_id,
    page_no,
    line_on_page,
    meeting_month,
    meeting_date,
    member_code,
    line_no,
    line_kind,
    loan_type,
    monthly_amount,
    case when {{ is_written('monthly_text') }} and monthly_amount is null
        then trim(monthly_text) end as monthly_note,
    loan_before,
    repayment,
    interest_rate_pct,
    interest_amount,
    loan_after,
    -- Balance carried to the next meeting. Written as "balance after" when
    -- there is one; otherwise worked out (closing_estimated = true).
    case
        when loan_after is not null then loan_after
        when line_kind = 'loan_given' then loan_before
        when repayment >= loan_before then 0
        when line_kind = 'balance' then
            loan_before - coalesce(repayment, 0)
            + coalesce(loan_before * interest_rate_pct / 100, interest_amount, 0)
    end as closing_balance,
    loan_after is null and line_kind = 'balance' and coalesce(repayment < loan_before, true)
        as closing_estimated,
    due_month,
    due_year_inferred,
    unclear,
    nullif(concat_ws(', ',
        case when member_code is null then 'member_missing' end,
        case when meeting_month is null then 'meeting_month_missing' end,
        case when {{ is_written('line_no_text') }} and line_no is null then 'line_no_unparsed' end,
        case when {{ is_written('loan_before_text') }} and loan_before is null
            then 'loan_before_unparsed' end,
        case when {{ is_written('repayment_text') }} and repayment is null
            then 'repayment_unparsed' end,
        case when {{ is_written('interest_text') }} and interest_value is null
            then 'interest_unparsed' end,
        case when {{ is_written('loan_after_text') }} and loan_after is null
            then 'loan_after_unparsed' end,
        case when {{ is_written('due_text') }} and due_month is null
            and due_clean not like 'clear%' then 'due_unparsed' end,
        case when loan_type = 'other' then 'loan_type_unrecognised' end,
        case when line_kind = 'empty' then 'empty_line' end
    ), '') as issues,
    source_photo,
    source_file,
    source_row
from final
