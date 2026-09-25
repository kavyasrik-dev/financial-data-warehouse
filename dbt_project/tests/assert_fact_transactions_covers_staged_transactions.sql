select transactions.*
from {{ ref('stg_transactions') }} as transactions
left join {{ ref('fact_transactions') }} as fact_transactions
    on transactions.transaction_id = fact_transactions.transaction_id
where fact_transactions.transaction_id is null
