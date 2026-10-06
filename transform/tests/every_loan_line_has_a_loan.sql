-- Every line with a balance must belong to a loan; otherwise the linking in
-- loan_lines has a gap and loan histories would be incomplete.

select line_id, source_photo, line_kind
from {{ ref('loan_lines') }}
where line_kind in ('balance', 'loan_given')
    and member_code is not null
    and loan_id is null
