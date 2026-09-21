select *
from {{ ref('dim_customer') }}
where (is_current and effective_to <> '9999-12-31 00:00:00+00'::timestamptz)
   or (not is_current and effective_to = '9999-12-31 00:00:00+00'::timestamptz)
