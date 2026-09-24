with ordered as (
    select
        full_date,
        lead(full_date) over (order by full_date) as next_full_date
    from {{ ref('dim_date') }}
)

select *
from ordered
where next_full_date is not null
  and next_full_date <> full_date + interval '1 day'
