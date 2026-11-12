-- An FX rate for every business day and currency: the latest ECB rate on or before that day (an as-of join),
-- because ECB holidays and our calendar don't match. EUR is 1.
with days as (
    select business_date from {{ ref('int_business_days') }}
),
rates as (
    select currency, rate_date, units_per_eur from {{ ref('stg_ecb__fx_rates') }}
),
matched as (
    select d.business_date, r.currency, r.units_per_eur, r.rate_date
    from days d
    join rates r on r.rate_date <= d.business_date
    qualify row_number() over (partition by d.business_date, r.currency order by r.rate_date desc) = 1
)
select business_date, currency, units_per_eur, rate_date as rate_source_date from matched
union all
select business_date, 'EUR' as currency, cast(1.0 as double) as units_per_eur, business_date as rate_source_date from days
