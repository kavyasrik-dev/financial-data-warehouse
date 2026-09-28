{{ config(materialized='table') }}

select
    fact_transactions.merchant_category,
    fact_transactions.transaction_type,
    fact_transactions.transaction_status,
    fact_transactions.currency,
    count(*) as total_transactions,
    sum(fact_transactions.amount) as total_transaction_amount,
    round(avg(fact_transactions.amount), 2) as average_transaction_amount,
    min(fact_transactions.amount) as minimum_transaction_amount,
    max(fact_transactions.amount) as maximum_transaction_amount
from {{ ref('fact_transactions') }} as fact_transactions
group by
    fact_transactions.merchant_category,
    fact_transactions.transaction_type,
    fact_transactions.transaction_status,
    fact_transactions.currency
