select transactions.*
from {{ ref('stg_transactions') }} as transactions
left join {{ ref('dim_date') }} as dim_date
    on transactions.transaction_timestamp::date = dim_date.full_date
where dim_date.full_date is null
