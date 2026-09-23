with current_customers as (
    select distinct customer_id
    from {{ ref('dim_customer') }}
    where is_current
)

select cards.*
from {{ ref('dim_card') }} as cards
left join current_customers
    on cards.customer_id = current_customers.customer_id
where current_customers.customer_id is null
