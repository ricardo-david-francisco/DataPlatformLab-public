-- Positions (IBOR, trade-date basis): opening quantity plus the running sum of every trade's signed quantity,
-- for every fund x security x business day.
with pairs as (
    select fund_id, isin from {{ ref('stg_custody__opening_positions') }}
    union
    select fund_id, isin from {{ ref('int_trades_latest') }}
),
grid as (
    select p.fund_id, p.isin, d.business_date
    from pairs p
    cross join {{ ref('int_business_days') }} d
),
daily_net as (
    select fund_id, isin, trade_date as business_date,
           sum(case when side = 'BUY' then quantity else -quantity end) as net_quantity
    from {{ ref('int_trades_latest') }}
    group by fund_id, isin, trade_date
)
select
    g.fund_id,
    g.isin,
    g.business_date,
    coalesce(o.quantity, 0)
      + sum(coalesce(n.net_quantity, 0)) over (
            partition by g.fund_id, g.isin order by g.business_date
            rows between unbounded preceding and current row) as quantity
from grid g
left join daily_net n
    on n.fund_id = g.fund_id and n.isin = g.isin and n.business_date = g.business_date
left join {{ ref('stg_custody__opening_positions') }} o
    on o.fund_id = g.fund_id and o.isin = g.isin
