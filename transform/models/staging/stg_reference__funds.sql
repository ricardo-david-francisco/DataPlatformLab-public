select fund_id, fund_name, asset_class, base_currency, domicile, legal_form, custodian
from {{ source('reference', 'funds') }}
