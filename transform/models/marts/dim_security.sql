select isin, security_name, country, currency, sector, asset_class
from {{ ref('stg_reference__securities') }}
