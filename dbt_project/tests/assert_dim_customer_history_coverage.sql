select customers.*
from {{ ref('stg_customers') }} as customers
left join {{ ref('dim_customer') }} as dim_customer
    on customers.customer_id = dim_customer.customer_id
   and customers.created_at >= dim_customer.effective_from
   and customers.created_at < dim_customer.effective_to
where dim_customer.customer_id is null
