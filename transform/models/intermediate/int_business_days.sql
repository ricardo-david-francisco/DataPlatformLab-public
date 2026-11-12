-- The valuation calendar: the days the market data has prices for.
select distinct price_date as business_date
from {{ ref('stg_market__prices') }}
