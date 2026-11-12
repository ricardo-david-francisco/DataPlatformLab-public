{{ config(contract={'enforced': target.type == 'duckdb'}) }}
-- THE data product of the post-trade domain: positions per fund x security x day, valued in EUR.
-- Grain: one row per fund_id, isin, position_date. Contract enforced: the columns and types below are a promise.
select
    cast(p.fund_id as varchar) as fund_id,
    cast(p.isin as varchar) as isin,
    cast(p.business_date as date) as position_date,
    cast(p.quantity as double) as quantity,
    cast(px.close_price as double) as close_price,
    cast(px.currency as varchar) as currency,
    cast(fx.units_per_eur as double) as units_per_eur,
    cast(p.quantity * px.close_price / fx.units_per_eur as double) as market_value_eur
from {{ ref('int_positions_daily') }} p
join {{ ref('stg_market__prices') }} px on px.isin = p.isin and px.price_date = p.business_date
join {{ ref('int_fx_daily') }} fx on fx.currency = px.currency and fx.business_date = p.business_date
