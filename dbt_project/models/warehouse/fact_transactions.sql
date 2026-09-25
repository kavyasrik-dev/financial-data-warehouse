{{ config(materialized='table') }}

with transactions as (
    select *
    from {{ ref('stg_transactions') }}
),

dim_customer as (
    select *
    from {{ ref('dim_customer') }}
),

dim_card as (
    select *
    from {{ ref('dim_card') }}
),

dim_date as (
    select *
    from {{ ref('dim_date') }}
)

select
    transactions.source_record_id as transaction_sk,
    transactions.transaction_id,
    dim_customer.customer_sk,
    dim_card.card_sk,
    dim_date.date_key,
    transactions.transaction_timestamp,
    transactions.transaction_type,
    transactions.transaction_status,
    transactions.amount,
    transactions.currency,
    transactions.merchant_name,
    transactions.merchant_category,
    current_timestamp as created_at
from transactions
inner join dim_customer
    on transactions.customer_id = dim_customer.customer_id
   and transactions.transaction_timestamp >= dim_customer.effective_from
   and transactions.transaction_timestamp < dim_customer.effective_to
inner join dim_card
    on transactions.card_id = dim_card.card_id
   and transactions.customer_id = dim_card.customer_id
inner join dim_date
    on transactions.transaction_timestamp::date = dim_date.full_date
