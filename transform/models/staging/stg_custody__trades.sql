-- One row per trade message: an amendment is a new version of the same trade_id (raw keeps them all).
select
    message_id,
    trade_id,
    version,
    fund_id,
    instrument__isin as isin,
    instrument__currency as currency,
    execution__side as side,
    cast(execution__quantity as double) as quantity,
    cast(execution__price as double) as price,
    execution__broker as broker,
    cast(trade_date as date) as trade_date,
    updated_at
from {{ source('custody', 'trades') }}
