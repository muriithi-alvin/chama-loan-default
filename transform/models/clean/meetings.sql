-- One row per ledger page (one monthly meeting), with typed amounts and a
-- meeting month for every page.
--
-- Where the page has no date, the month is worked out in this order:
--   previous_page : the previous page's "next meeting" note gives the day
--   estimated     : one page per month, counted from the nearest dated page

with source as (
    select * from {{ source('staging', 'meetings') }}
),

pages as (
    select
        chama_id || ':' || source_photo as page_id,
        chama_id,
        {{ page_number('source_photo') }} as page_no,
        source_photo,
        source_file,
        source_row,
        meeting_date as meeting_date_text,
        coalesce({{ parse_dmy('meeting_date') }}, {{ parse_text_date('meeting_date') }}) as written_date,
        column_headers,
        contribution_total as contribution_total_text,
        {{ parse_amount('contribution_total') }} as contribution_total,
        brought_forward as brought_forward_text,
        {{ parse_amount('brought_forward') }} as brought_forward,
        total_collection as total_collection_text,
        {{ parse_amount('total_collection') }} as total_collection,
        cash as cash_text,
        {{ parse_amount('cash') }} as cash,
        banked as banked_text,
        {{ parse_amount('banked') }} as banked,
        next_meeting_date as next_meeting_text,
        upper(coalesce(trim(unclear), '')) = 'Y' as unclear
    from source
),

anchored as (
    select
        pages.*,
        anchor.page_no as anchor_page,
        anchor.written_date as anchor_date
    from pages
    left join lateral (
        select dated.page_no, dated.written_date
        from pages as dated
        where dated.chama_id = pages.chama_id
            and dated.written_date is not null
        order by abs(dated.page_no - pages.page_no), dated.page_no
        limit 1
    ) as anchor on true
),

with_note as (
    select
        *,
        (date_trunc('month', anchor_date)
            + (page_no - anchor_page) * interval '1 month')::date as estimated_month,
        lower(regexp_replace(
            lag(next_meeting_text) over (partition by chama_id order by page_no),
            '[.,]| of ', ' ', 'g'
        )) as note
    from anchored
),

note_parts as (
    select
        *,
        -- "9th feb", "9th march 2014"
        substring(note from '^\s*([0-9]{1,2})[a-z]*\s')::int as note_day,
        {{ month_number("substring(note from '^\\s*[0-9]{1,2}[a-z]*\\s+([a-z]+)')") }} as note_month,
        substring(note from '([0-9]{4})\s*$')::int as note_year,
        {{ parse_dmy('note') }} as note_dmy
    from with_note
),

note_dates as (
    select
        *,
        case
            when note_dmy is not null
                and date_trunc('month', note_dmy) = estimated_month then note_dmy
            when note_month = extract(month from estimated_month)
                and note_day between 1 and extract(
                    day from estimated_month + interval '1 month' - interval '1 day'
                )
                then make_date(
                    coalesce(note_year, extract(year from estimated_month)::int),
                    note_month,
                    note_day
                )
        end as note_date
    from note_parts
),

final as (
    select
        *,
        coalesce(written_date, note_date) as meeting_date,
        date_trunc('month', coalesce(written_date, note_date, estimated_month))::date
            as meeting_month,
        case
            when written_date is not null then 'written'
            when note_date is not null then 'previous_page'
            when estimated_month is not null then 'estimated'
        end as date_source
    from note_dates
)

select
    page_id,
    chama_id,
    page_no,
    meeting_month,
    meeting_date,
    date_source,
    contribution_total,
    brought_forward,
    total_collection,
    cash,
    banked,
    column_headers,
    unclear,
    nullif(concat_ws(', ',
        case when page_no is null then 'page_number_unknown' end,
        case when meeting_month is null then 'meeting_month_missing' end,
        case when {{ is_written('meeting_date_text') }} and written_date is null
            then 'meeting_date_unparsed' end,
        case when {{ is_written('contribution_total_text') }} and contribution_total is null
            then 'contribution_total_unparsed' end,
        case when {{ is_written('brought_forward_text') }} and brought_forward is null
            then 'brought_forward_unparsed' end,
        case when {{ is_written('total_collection_text') }} and total_collection is null
            then 'total_collection_unparsed' end,
        case when {{ is_written('cash_text') }} and cash is null then 'cash_unparsed' end,
        case when {{ is_written('banked_text') }} and banked is null then 'banked_unparsed' end
    ), '') as issues,
    source_photo,
    source_file,
    source_row
from final
