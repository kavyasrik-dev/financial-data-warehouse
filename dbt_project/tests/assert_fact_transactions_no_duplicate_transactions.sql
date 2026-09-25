select transaction_id
from {{ ref('fact_transactions') }}
group by transaction_id
having count(*) > 1
