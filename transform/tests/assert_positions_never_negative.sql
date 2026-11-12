-- The funds don't short: a negative position means a lost or duplicated trade.
select fund_id, isin, position_date, quantity
from {{ ref('fct_positions_daily') }}
where quantity < 0
