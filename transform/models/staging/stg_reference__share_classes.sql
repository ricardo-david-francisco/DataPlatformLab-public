select
    share_class_id,
    fund_id,
    share_class,
    investor_type,
    cast(mgmt_fee_rate as double) as mgmt_fee_rate,
    cast(aum_weight as double) as aum_weight
from {{ source('reference', 'share_classes') }}
