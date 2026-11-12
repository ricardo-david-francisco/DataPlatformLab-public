-- Trades in their current version, with the EUR consideration and the settlement outcome.
select
    t.trade_id,
    t.version,
    t.fund_id,
    t.isin,
    t.side,
    t.quantity,
    t.price,
    t.currency,
    t.trade_date,
    t.quantity * t.price / fx.units_per_eur as consideration_eur,
    s.intended_settlement_date,
    s.actual_settlement_date,
    s.status as settlement_status
from {{ ref('int_trades_latest') }} t
join {{ ref('int_fx_daily') }} fx on fx.currency = t.currency and fx.business_date = t.trade_date
left join {{ ref('stg_custody__settlements') }} s on s.trade_id = t.trade_id
