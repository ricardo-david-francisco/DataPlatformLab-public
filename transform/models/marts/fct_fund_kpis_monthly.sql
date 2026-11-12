-- The semantic layer's measures, defined once (see _marts.yml for their definitions):
--   aum_month_end_eur  semi-additive: the AUM on the month's LAST business day, never a sum over days
--   net_flows_eur      additive: subscriptions minus redemptions
--   fee_income_eur     additive: the month's accrued fees, rounded once, at the end
with aum as (
    select fund_id, position_date, sum(market_value_eur) as aum_eur
    from {{ ref('fct_positions_daily') }}
    group by fund_id, position_date
),
aum_month_end as (
    select fund_id, cast(date_trunc('month', position_date) as date) as month, aum_eur as aum_month_end_eur,
           position_date as month_end_date
    from aum
    qualify row_number() over (partition by fund_id, date_trunc('month', position_date) order by position_date desc) = 1
),
flows as (
    select sc.fund_id, cast(date_trunc('month', f.trade_date) as date) as month, sum(f.signed_amount_eur) as net_flows_eur
    from {{ ref('stg_transfer_agent__flows') }} f
    join {{ ref('stg_reference__share_classes') }} sc on sc.share_class_id = f.share_class_id
    group by sc.fund_id, cast(date_trunc('month', f.trade_date) as date)
),
fees as (
    select fund_id, cast(date_trunc('month', accrual_date) as date) as month, round(sum(fee_eur), 2) as fee_income_eur
    from {{ ref('fct_fee_accrual') }}
    group by fund_id, cast(date_trunc('month', accrual_date) as date)
)
select
    m.fund_id,
    m.month,
    m.month_end_date,
    round(m.aum_month_end_eur, 2) as aum_month_end_eur,
    round(coalesce(fl.net_flows_eur, 0), 2) as net_flows_eur,
    fe.fee_income_eur
from aum_month_end m
left join flows fl on fl.fund_id = m.fund_id and fl.month = m.month
left join fees fe on fe.fund_id = m.fund_id and fe.month = m.month
