{{ config(materialized='table') }}

with scd_events as (
    select *
    from {{ ref('int_customer_scd_events') }}
)

select
    source_record_id as customer_sk,
    customer_id,
    customer_name_masked,
    email_masked,
    phone_masked,
    address,
    city,
    state,
    country,
    customer_status,
    effective_from,
    effective_to,
    is_current,
    record_hash,
    current_timestamp as created_at
from scd_events
