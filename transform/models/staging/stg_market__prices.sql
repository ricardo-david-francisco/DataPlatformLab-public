select
    isin,
    cast(price_date as date) as price_date,
    cast(close_price as double) as close_price,
    currency
from {{ source('market', 'prices') }}
