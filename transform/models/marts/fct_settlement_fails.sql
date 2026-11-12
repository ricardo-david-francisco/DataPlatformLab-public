-- Trades that didn't settle on the intended date: what operations chase (and what T+1 makes harder).
select trade_id, fund_id, isin, trade_date, intended_settlement_date, actual_settlement_date, settlement_status,
       {{ dbt.datediff('intended_settlement_date', 'coalesce(actual_settlement_date, current_date)', 'day') }} as days_late
from {{ ref('fct_trades') }}
where settlement_status in ('SETTLED_LATE', 'FAILED')
