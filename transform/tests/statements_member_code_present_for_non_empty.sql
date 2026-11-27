-- Every non-empty ledger statement must be linked to a member.
-- Empty ledger lines are retained for audit purposes.
select
    line_id,
    page_id,
    member_code,
    line_kind
from {{ ref('statements') }}
where member_code is null
  and coalesce(line_kind, '') != 'empty'
