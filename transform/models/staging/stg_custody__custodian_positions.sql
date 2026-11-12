select
    fund_id,
    isin,
    cast(position_date as date) as position_date,
    cast(quantity as double) as quantity
from {{ source('custody', 'custodian_positions') }}
