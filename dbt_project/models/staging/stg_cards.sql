with source as (
    select * from {{ source('raw', 'cards') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by nullif(trim(card_id), '')
            order by ingested_at desc, source_record_id desc
        ) as row_number
    from source
    where card_id is not null
),

cleaned as (
    select
        source_record_id,
        nullif(trim(card_id), '') as card_id,
        nullif(trim(customer_id), '') as customer_id,
        regexp_replace(coalesce(card_number, ''), '[^0-9]', '', 'g') as card_number,
        {{ mask_card("regexp_replace(coalesce(card_number, ''), '[^0-9]', '', 'g')") }} as card_number_masked,
        lower(nullif(trim(card_type), '')) as card_type,
        expiry_date::date as expiry_date,
        lower(nullif(trim(card_status), '')) as card_status,
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
where card_id is not null
  and customer_id is not null
  and length(card_number) between 12 and 19
  and expiry_date is not null
