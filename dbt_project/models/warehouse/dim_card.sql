{{ config(materialized='table') }}

with cards as (
    select *
    from {{ ref('stg_cards') }}
)

select
    source_record_id as card_sk,
    card_id,
    customer_id,
    card_number_masked as masked_card_number,
    card_type,
    expiry_date,
    card_status,
    current_timestamp as created_at
from cards
