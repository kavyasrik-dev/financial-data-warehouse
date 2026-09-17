with source as (
    select * from {{ source('raw', 'customers') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by source_record_hash
            order by ingested_at desc, source_record_id desc
        ) as row_number
    from source
    where source_record_hash is not null
),

cleaned as (
    select
        source_record_id,
        nullif(trim(customer_id), '') as customer_id,
        nullif(trim(customer_name), '') as customer_name,
        {{ mask_name("nullif(trim(customer_name), '')") }} as customer_name_masked,
        lower(nullif(trim(email), '')) as email,
        {{ mask_email("lower(nullif(trim(email), ''))") }} as email_masked,
        regexp_replace(coalesce(phone, ''), '[^0-9]', '', 'g') as phone,
        {{ mask_phone("regexp_replace(coalesce(phone, ''), '[^0-9]', '', 'g')") }} as phone_masked,
        nullif(trim(address), '') as address,
        nullif(trim(city), '') as city,
        nullif(trim(state), '') as state,
        nullif(trim(country), '') as country,
        lower(nullif(trim(customer_status), '')) as customer_status,
        created_at::timestamptz as created_at,
        source_system,
        source_file,
        source_extracted_at,
        source_record_hash,
        load_batch_id,
        ingested_at
    from deduped
    where row_number = 1
)

select *
from cleaned
where customer_id is not null
  and customer_name is not null
  and email is not null
  and phone is not null
  and created_at is not null
