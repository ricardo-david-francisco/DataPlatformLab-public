-- Funds with their attributes as they were over time (SCD2, from the snapshot).
select
    f.fund_id,
    f.fund_name,
    f.asset_class,
    f.legal_form,
    s.portfolio_manager,
    cast(s.risk_class as integer) as risk_class,
    s.sfdr_article,
    s.dbt_valid_from as valid_from,
    s.dbt_valid_to as valid_to,
    s.dbt_valid_to is null as is_current
from {{ ref('snap_fund_attributes') }} s
join {{ ref('stg_reference__funds') }} f on f.fund_id = s.fund_id
