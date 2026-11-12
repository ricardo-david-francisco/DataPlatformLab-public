select
    fund_id,
    isin,
    cast(as_of_date as date) as as_of_date,
    cast(quantity as double) as quantity
from {{ source('custody', 'opening_positions') }}
