{{ config(materialized='table') }}

select
    dim_date.date_key,
    dim_date.full_date,
    dim_date.day,
    dim_date.month,
    dim_date.quarter,
    dim_date.year,
    dim_date.week,
    dim_date.day_of_week,
    count(*) as total_transactions,
    sum(fact_transactions.amount) as total_transaction_amount,
    round(avg(fact_transactions.amount), 2) as average_transaction_amount,
    count(*) filter (where fact_transactions.transaction_status = 'success') as successful_transactions,
    count(*) filter (where fact_transactions.transaction_status = 'failed') as failed_transactions,
    count(*) filter (where fact_transactions.transaction_status = 'pending') as pending_transactions
from {{ ref('fact_transactions') }} as fact_transactions
inner join {{ ref('dim_date') }} as dim_date
    on fact_transactions.date_key = dim_date.date_key
group by
    dim_date.date_key,
    dim_date.full_date,
    dim_date.day,
    dim_date.month,
    dim_date.quarter,
    dim_date.year,
    dim_date.week,
    dim_date.day_of_week
