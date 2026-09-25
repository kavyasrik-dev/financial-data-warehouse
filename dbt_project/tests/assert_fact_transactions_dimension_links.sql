select fact_transactions.*
from {{ ref('fact_transactions') }} as fact_transactions
left join {{ ref('dim_customer') }} as dim_customer
    on fact_transactions.customer_sk = dim_customer.customer_sk
left join {{ ref('dim_card') }} as dim_card
    on fact_transactions.card_sk = dim_card.card_sk
left join {{ ref('dim_date') }} as dim_date
    on fact_transactions.date_key = dim_date.date_key
where dim_customer.customer_sk is null
   or dim_card.card_sk is null
   or dim_date.date_key is null
