-- Subscriptions add money to a share class, redemptions take it out: signed_amount_eur carries the sign.
select
    flow_id,
    share_class_id,
    cast(trade_date as date) as trade_date,
    flow_type,
    cast(amount as double) as amount_eur,
    case when flow_type = 'SUBSCRIPTION' then cast(amount as double) else -cast(amount as double) end as signed_amount_eur
from {{ source('transfer_agent', 'flows') }}
