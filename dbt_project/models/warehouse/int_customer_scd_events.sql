{{ config(materialized='view') }}

with prepared as (
    select
        source_record_id,
        customer_id,
        customer_name_masked,
        email,
        email_masked,
        phone,
        phone_masked,
        address,
        city,
        state,
        country,
        customer_status,
        created_at,
        source_record_hash,
        load_batch_id,
        ingested_at,
        {{ customer_scd_record_hash() }} as record_hash
    from {{ ref('stg_customers') }}
),

ordered as (
    select
        *,
        lag(record_hash) over (
            partition by customer_id
            order by created_at, source_record_id
        ) as previous_record_hash
    from prepared
),

changes as (
    select *
    from ordered
    where previous_record_hash is null
       or record_hash <> previous_record_hash
),

versioned as (
    select
        *,
        created_at as effective_from,
        coalesce(
            lead(created_at) over (
                partition by customer_id
                order by created_at, source_record_id
            ),
            '9999-12-31 00:00:00+00'::timestamptz
        ) as effective_to
    from changes
)

select
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
    effective_to = '9999-12-31 00:00:00+00'::timestamptz as is_current,
    record_hash,
    source_record_id,
    source_record_hash,
    load_batch_id,
    ingested_at
from versioned
