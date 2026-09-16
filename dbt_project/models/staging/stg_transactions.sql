with source as (
    select * from {{ source('raw', 'transactions') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by nullif(trim(transaction_id), '')
            order by ingested_at desc, source_record_id desc
        ) as row_number
    from source
    where transaction_id is not null
),

cleaned as (
    select
        source_record_id,
        nullif(trim(transaction_id), '') as transaction_id,
        nullif(trim(customer_id), '') as customer_id,
        nullif(trim(card_id), '') as card_id,
        transaction_timestamp::timestamptz as transaction_timestamp,
        amount::numeric(18, 2) as amount,
        upper(nullif(trim(currency), '')) as currency,
        nullif(trim(merchant_name), '') as merchant_name,
        lower(nullif(trim(merchant_category), '')) as merchant_category,
        lower(nullif(trim(transaction_type), '')) as transaction_type,
        lower(nullif(trim(transaction_status), '')) as transaction_status,
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
where transaction_id is not null
  and customer_id is not null
  and card_id is not null
  and transaction_timestamp is not null
  and amount >= 0
