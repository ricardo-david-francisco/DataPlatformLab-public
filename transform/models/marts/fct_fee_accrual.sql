-- Management fees accrue every calendar day: on each business day, the share class's AUM x yearly rate / 365 x
-- the calendar days since the previous business day (so a Monday carries the weekend). Not rounded here.
with fund_aum as (
    select fund_id, position_date as business_date, sum(market_value_eur) as fund_aum_eur
    from {{ ref('fct_positions_daily') }}
    group by fund_id, position_date
),
days as (
    select business_date,
           coalesce({{ dbt.datediff('lag(business_date) over (order by business_date)', 'business_date', 'day') }}, 1)
               as accrual_days
    from {{ ref('int_business_days') }}
)
select
    sc.share_class_id,
    sc.fund_id,
    a.business_date as accrual_date,
    a.fund_aum_eur * sc.aum_weight as class_aum_eur,
    sc.mgmt_fee_rate,
    d.accrual_days,
    a.fund_aum_eur * sc.aum_weight * sc.mgmt_fee_rate / 365.0 * d.accrual_days as fee_eur
from fund_aum a
join {{ ref('stg_reference__share_classes') }} sc on sc.fund_id = a.fund_id
join days d on d.business_date = a.business_date
