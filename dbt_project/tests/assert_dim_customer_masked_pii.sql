select *
from {{ ref('dim_customer') }}
where email_masked !~ '^[^@]\*\*\*@[^@]+$'
   or phone_masked !~ '^\*+[0-9]{4}$'
   or customer_name_masked !~ '\*'
