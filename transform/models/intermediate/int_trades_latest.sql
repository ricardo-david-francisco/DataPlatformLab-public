-- The current version of each trade: the latest amendment wins.
select *
from {{ ref('stg_custody__trades') }}
qualify row_number() over (partition by trade_id order by version desc) = 1
