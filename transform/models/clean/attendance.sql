-- One row per member per meeting from the minutes, with a standard status.

with source as (
    select * from {{ source('staging', 'attendance') }}
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
        source.meeting_date as meeting_date_text,
        {{ parse_dmy('source.meeting_date') }} as meeting_date,
        lower(trim(coalesce(source.status, ''))) as status_text,
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
        coalesce(date_trunc('month', typed.meeting_date)::date, meetings.meeting_month)
            as meeting_month,
        case
            when status_text in ('present', 'p', 'yes', 'attended', '✓') then 'present'
            when status_text like 'absent%' or status_text in ('a', 'x', 'no') then 'absent'
            when status_text like 'apolog%' then 'apology'
            when status_text like 'late%' then 'late'
        end as status
    from typed
    left join meetings on meetings.page_id = typed.page_id
)

select
    line_id,
    page_id,
    chama_id,
    page_no,
    meeting_month,
    meeting_date,
    member_code,
    status,
    unclear,
    nullif(concat_ws(', ',
        case when member_code is null then 'member_missing' end,
        case when meeting_month is null then 'meeting_month_missing' end,
        case when {{ is_written('meeting_date_text') }} and meeting_date is null
            then 'meeting_date_unparsed' end,
        case when status is null then 'status_unrecognised' end
    ), '') as issues,
    source_photo,
    source_file,
    source_row
from parsed
