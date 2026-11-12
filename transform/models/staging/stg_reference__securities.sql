select isin, name as security_name, country, currency, sector, asset_class
from {{ source('reference', 'securities') }}
