-- Our positions against the custodian's, on each day the custodian reported: every difference is a break.
with ours as (
    select fund_id, isin, position_date, quantity from {{ ref('fct_positions_daily') }}
    where position_date in (select distinct position_date from {{ ref('stg_custody__custodian_positions') }})
),
theirs as (
    select fund_id, isin, position_date, quantity from {{ ref('stg_custody__custodian_positions') }}
)
select
    coalesce(o.fund_id, t.fund_id) as fund_id,
    coalesce(o.isin, t.isin) as isin,
    coalesce(o.position_date, t.position_date) as position_date,
    o.quantity as our_quantity,
    t.quantity as custodian_quantity,
    coalesce(o.quantity, 0) - coalesce(t.quantity, 0) as difference
from ours o
full outer join theirs t
    on t.fund_id = o.fund_id and t.isin = o.isin and t.position_date = o.position_date
where coalesce(o.quantity, 0) <> coalesce(t.quantity, 0)
