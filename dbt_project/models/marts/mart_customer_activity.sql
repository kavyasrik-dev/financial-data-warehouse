{{ config(materialized='table') }}

select
    dim_customer.customer_sk,
    dim_customer.customer_id,
    dim_customer.customer_name_masked,
    dim_customer.customer_status,
    dim_customer.city,
    dim_customer.state,
    dim_customer.country,
    count(*) as total_transactions,
    sum(fact_transactions.amount) as total_transaction_amount,
    round(avg(fact_transactions.amount), 2) as average_transaction_amount,
    count(*) filter (where fact_transactions.transaction_status = 'success') as successful_transactions,
    count(*) filter (where fact_transactions.transaction_status = 'failed') as failed_transactions,
    min(fact_transactions.transaction_timestamp) as first_transaction_at,
    max(fact_transactions.transaction_timestamp) as last_transaction_at
from {{ ref('fact_transactions') }} as fact_transactions
inner join {{ ref('dim_customer') }} as dim_customer
    on fact_transactions.customer_sk = dim_customer.customer_sk
group by
    dim_customer.customer_sk,
    dim_customer.customer_id,
    dim_customer.customer_name_masked,
    dim_customer.customer_status,
    dim_customer.city,
    dim_customer.state,
    dim_customer.country
