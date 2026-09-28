with fact_totals as (
    select
        merchant_category,
        transaction_type,
        transaction_status,
        currency,
        count(*) as total_transactions,
        sum(amount) as total_transaction_amount
    from {{ ref('fact_transactions') }}
    group by
        merchant_category,
        transaction_type,
        transaction_status,
        currency
)

select fact_totals.*
from fact_totals
left join {{ ref('mart_transaction_summary') }} as mart_transaction_summary
    on fact_totals.merchant_category = mart_transaction_summary.merchant_category
   and mart_transaction_summary.transaction_type = fact_totals.transaction_type
   and mart_transaction_summary.transaction_status = fact_totals.transaction_status
   and mart_transaction_summary.currency = fact_totals.currency
where mart_transaction_summary.merchant_category is null
   or mart_transaction_summary.total_transactions <> fact_totals.total_transactions
   or mart_transaction_summary.total_transaction_amount <> fact_totals.total_transaction_amount
