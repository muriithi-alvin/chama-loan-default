-- One row per loan listed as given at a meeting, with typed amount, a standard
-- loan type and the month it was given.
--
-- loan_month_source:
--   written    the date beside the loans list
--   month_only only the month is readable, e.g. "?/6/2014"
--   meeting    no date: the meeting the page belongs to

with source as (
    select * from {{ source('staging', 'new_loans') }}
),

meetings as (
    select page_id, page_no, meeting_month from {{ ref('meetings') }}
),

typed as (
    select
        source.chama_id || ':' || source.source_file || ':' || source.source_row as line_id,
        source.chama_id || ':' || source.source_photo as page_id,
        source.chama_id,
        source.member_code,
        source.loan_date as loan_date_text,
        {{ parse_dmy('source.loan_date') }} as loan_date,
        substring(trim(source.loan_date) from '^\?/([0-9]{1,2})/[0-9]{2,4}$')::int
            as month_only_month,
        substring(trim(source.loan_date) from '^\?/[0-9]{1,2}/([0-9]{2,4})$') as month_only_year,
        source.amount as amount_text,
        {{ parse_amount('source.amount') }} as amount,
        lower(trim(coalesce(source.loan_type, ''))) as loan_type_text,
        upper(coalesce(trim(source.unclear), '')) = 'Y' as unclear,
        source.source_photo,
        source.source_file,
        source.source_row
    from source
),

parsed as (
    select
        typed.*,
        meetings.page_no,
        meetings.meeting_month,
        case when month_only_month between 1 and 12 then make_date(
            case when length(month_only_year) = 2 then 2000 + month_only_year::int
                else month_only_year::int end,
            month_only_month, 1)
        end as month_only_date,
        case
            when loan_type_text in ('', 'normal') then 'normal'
            when loan_type_text like 'emerg%' then 'emergency'
            when loan_type_text in ('sf', 's/f', 's.f') or loan_type_text like 'school%'
                then 'school_fees'
            when loan_type_text like 'top%up%' then 'top_up'
            else 'other'
        end as loan_type
    from typed
    left join meetings on meetings.page_id = typed.page_id
)

select
    line_id,
    page_id,
    chama_id,
    page_no,
    meeting_month,
    member_code,
    amount,
    loan_type,
    loan_date,
    coalesce(date_trunc('month', loan_date)::date, month_only_date, meeting_month) as loan_month,
    case
        when loan_date is not null then 'written'
        when month_only_date is not null then 'month_only'
        when meeting_month is not null then 'meeting'
    end as loan_month_source,
    unclear,
    nullif(concat_ws(', ',
        case when member_code is null then 'member_missing' end,
        case when meeting_month is null then 'meeting_month_missing' end,
        case when {{ is_written('amount_text') }} and amount is null then 'amount_unparsed' end,
        case when amount_text is null or trim(amount_text) = '' then 'amount_missing' end,
        case when {{ is_written('loan_date_text') }} and loan_date is null and month_only_date is null
            then 'loan_date_unparsed' end,
        case when loan_type = 'other' then 'loan_type_unrecognised' end
    ), '') as issues,
    source_photo,
    source_file,
    source_row
from parsed
