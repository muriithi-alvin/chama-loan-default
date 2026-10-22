-- A loan that stops appearing while another member's new loan starts within a
-- few pages at the same balance is usually one person under two spellings
-- that were not linked in the name review. Such loans show as lost_track and
-- would be wrongly counted as defaults. Check the two codes' names in
-- private.member_codes and, if they are one person, give both spellings the
-- same canonical_name in the review file. Warns rather than stops: two members
-- can borrow the same round amount.
{{ config(severity='warn') }}

select
    lost.loan_id as lost_loan_id,
    lost.member_code as lost_member_code,
    lost.last_page,
    lost.last_balance,
    picked_up.loan_id as next_loan_id,
    picked_up.member_code as next_member_code,
    picked_up.first_page,
    picked_up.first_balance
from {{ ref('loans') }} as lost
inner join {{ ref('loans') }} as picked_up
    on picked_up.chama_id = lost.chama_id
    and picked_up.member_code <> lost.member_code
    and picked_up.first_page > lost.last_page
    and picked_up.first_page <= lost.last_page + {{ var('max_pages_between_lines') }}
    and abs(picked_up.first_balance - lost.last_balance)
        <= greatest(lost.last_balance * {{ var('carry_tolerance') }}, 100)
where lost.status = 'lost_track'
