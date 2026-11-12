select
    cast(trade_id as bigint) as trade_id,
    cast(intended_settlement_date as date) as intended_settlement_date,
    try_cast(nullif(actual_settlement_date, '') as date) as actual_settlement_date,
    status
from {{ source('custody', 'settlements') }}
