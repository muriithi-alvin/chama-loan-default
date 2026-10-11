{#- Turn values typed exactly as written in the ledger into proper types.
    Each macro returns null when a value cannot be read, so the row can be
    flagged instead of dropped. -#}


{#- Amount -> number. Handles "40,000", "46 000", "59,000/=", "92,400/-", "Ksh. 43,571",
    "300k" and sums such as "5500 + 776". "-" and "nil" mean nothing (0). -#}
{% macro parse_amount(column) -%}
(
    select case
        when v is null then null
        when v in ('-', '–', '—', 'nil') then 0
        when v ~ '^[0-9]+(\.[0-9]+)?k$' then rtrim(v, 'k')::numeric * 1000
        when v ~ '^[0-9]+(\.[0-9]+)?(\+[0-9]+(\.[0-9]+)?)*$'
            then (select sum(part::numeric) from unnest(string_to_array(v, '+')) as part)
    end
    from (
        select nullif(regexp_replace(lower(trim({{ column }})), '^ksh\.?|/=|/-|,|\s', '', 'g'), '') as v
    ) as cleaned
)
{%- endmacro %}


{#- Day-first date -> date: "8/6/14", "3/8/2014". Impossible dates give null. -#}
{% macro parse_dmy(column) -%}
(
    select case when m between 1 and 12 and d between 1 and 31 then
        case when d <= extract(day from make_date(y, m, 1) + interval '1 month' - interval '1 day')
            then make_date(y, m, d)
        end
    end
    from (
        select
            split_part(v, '/', 1)::int as d,
            split_part(v, '/', 2)::int as m,
            case when length(split_part(v, '/', 3)) = 2
                then 2000 + split_part(v, '/', 3)::int
                else split_part(v, '/', 3)::int
            end as y
        from (select trim({{ column }}) as v) as raw_value
        where trim({{ column }}) ~ '^[0-9]{1,2}/[0-9]{1,2}/([0-9]{2}|[0-9]{4})$'
    ) as parts
)
{%- endmacro %}


{#- Date written in words -> date: "7th June 2015", "8th/March/2015".
    Needs a day, a month name and a four-digit year; otherwise null. -#}
{% macro parse_text_date(column) -%}
(
    select case when m is not null and d between 1 and 31 then
        case when d <= extract(day from make_date(y, m, 1) + interval '1 month' - interval '1 day')
            then make_date(y, m, d)
        end
    end
    from (
        select
            substring(v from '^([0-9]{1,2})')::int as d,
            {{ month_number("substring(v from '^[0-9]{1,2}[a-z]*[^a-z0-9]+([a-z]+)')") }} as m,
            substring(v from '([0-9]{4})$')::int as y
        from (select lower(trim({{ column }})) as v) as raw_value
        where lower(trim({{ column }})) ~ '^[0-9]{1,2}(st|nd|rd|th)?[^a-z0-9]+[a-z]+[^a-z0-9]+[0-9]{4}$'
    ) as parts
)
{%- endmacro %}


{#- Month and year without a day -> first of that month: "May 2016",
    "Nov. 2016", "Nov/17", "Nov '17" (two-digit years are 20xx). -#}
{% macro parse_month_year(column) -%}
(
    select make_date(case when length(y) = 2 then 2000 + y::int else y::int end, m, 1)
    from (
        select
            {{ month_number("substring(v from '^([a-z]+)')") }} as m,
            substring(v from '([0-9]{4}|[0-9]{2})$') as y
        from (select lower(regexp_replace(trim({{ column }}), '[.,]', '', 'g')) as v) as raw_value
        where lower(regexp_replace(trim({{ column }}), '[.,]', '', 'g'))
            ~ '^[a-z]+\s*[/''-]?\s*([0-9]{4}|[0-9]{2})$'
    ) as parts
    where m is not null
)
{%- endmacro %}


{#- Month name or abbreviation (lower case) -> 1..12, otherwise null. -#}
{% macro month_number(word) -%}
case {{ word }}
    when 'jan' then 1 when 'january' then 1
    when 'feb' then 2 when 'february' then 2
    when 'mar' then 3 when 'march' then 3
    when 'apr' then 4 when 'april' then 4
    when 'may' then 5
    when 'jun' then 6 when 'june' then 6
    when 'jul' then 7 when 'july' then 7
    when 'aug' then 8 when 'august' then 8
    when 'sep' then 9 when 'sept' then 9 when 'september' then 9
    when 'oct' then 10 when 'october' then 10
    when 'nov' then 11 when 'november' then 11
    when 'dec' then 12 when 'december' then 12
end
{%- endmacro %}


{#- Page number from a photo name such as "chama_b_p012.jpg" (decision D-005). -#}
{% macro page_number(column) -%}
substring(lower({{ column }}) from '_p([0-9]+)\.[a-z]+$')::int
{%- endmacro %}


{#- True when the ledger cell has something other than blank or a dash. -#}
{% macro is_written(column) -%}
coalesce(trim({{ column }}), '') not in ('', '-', '–', '—')
{%- endmacro %}
