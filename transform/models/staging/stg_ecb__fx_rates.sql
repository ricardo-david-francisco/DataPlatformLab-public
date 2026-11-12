-- Units of each currency per 1 EUR, as published by the ECB (TARGET business days only).
select
    currency,
    cast(rate_date as date) as rate_date,
    cast(units_per_eur as double) as units_per_eur
from {{ source('ecb', 'fx_rates') }}
