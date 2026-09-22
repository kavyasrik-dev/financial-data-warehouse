select *
from {{ ref('dim_card') }}
where masked_card_number !~ '^\*+[0-9]{4}$'
   or masked_card_number ~ '^[0-9]+$'
