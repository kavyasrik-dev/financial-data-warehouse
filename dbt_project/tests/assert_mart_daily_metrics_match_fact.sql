with fact_totals as (
    select
        date_key,
        count(*) as total_transactions,
        sum(amount) as total_transaction_amount
    from {{ ref('fact_transactions') }}
    group by date_key
)

select fact_totals.*
from fact_totals
left join {{ ref('mart_daily_transaction_metrics') }} as mart_daily_transaction_metrics
    on fact_totals.date_key = mart_daily_transaction_metrics.date_key
where mart_daily_transaction_metrics.date_key is null
   or mart_daily_transaction_metrics.total_transactions <> fact_totals.total_transactions
   or mart_daily_transaction_metrics.total_transaction_amount <> fact_totals.total_transaction_amount
