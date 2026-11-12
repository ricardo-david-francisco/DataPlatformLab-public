-- The data product's grain: one row per fund, security and day.
select fund_id, isin, position_date, count(*) as n
from {{ ref('fct_positions_daily') }}
group by fund_id, isin, position_date
having count(*) > 1
