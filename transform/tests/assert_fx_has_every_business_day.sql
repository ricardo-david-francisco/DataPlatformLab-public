-- Every business day must have a rate for every currency we hold (ECB holidays are filled by the as-of join).
select d.business_date, s.currency
from {{ ref('int_business_days') }} d
cross join (select distinct currency from {{ ref('stg_reference__securities') }}) s
left join {{ ref('int_fx_daily') }} fx on fx.business_date = d.business_date and fx.currency = s.currency
where fx.units_per_eur is null
