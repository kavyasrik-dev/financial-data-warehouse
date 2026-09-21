with ordered as (
    select
        customer_id,
        effective_from,
        effective_to,
        lead(effective_from) over (
            partition by customer_id
            order by effective_from
        ) as next_effective_from
    from {{ ref('dim_customer') }}
)

select *
from ordered
where next_effective_from is not null
  and effective_to > next_effective_from
