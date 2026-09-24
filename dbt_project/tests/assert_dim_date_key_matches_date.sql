select *
from {{ ref('dim_date') }}
where date_key <> to_char(full_date, 'YYYYMMDD')::integer
