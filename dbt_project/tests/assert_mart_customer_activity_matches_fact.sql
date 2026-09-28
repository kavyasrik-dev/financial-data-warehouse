with fact_totals as (
    select
        customer_sk,
        count(*) as total_transactions,
        sum(amount) as total_transaction_amount
    from {{ ref('fact_transactions') }}
    group by customer_sk
)

select fact_totals.*
from fact_totals
left join {{ ref('mart_customer_activity') }} as mart_customer_activity
    on fact_totals.customer_sk = mart_customer_activity.customer_sk
where mart_customer_activity.customer_sk is null
   or mart_customer_activity.total_transactions <> fact_totals.total_transactions
   or mart_customer_activity.total_transaction_amount <> fact_totals.total_transaction_amount
