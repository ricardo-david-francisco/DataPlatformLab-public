# Ingestion: dlt

`pipelines.py` loads every source into the raw layer, one dataset (schema) per source, into DuckDB or Snowflake:

| Resource | Source | How it loads |
|---|---|---|
| `fx_rates` | ECB Data Portal (REST, live) | incremental on `rate_date`, merge on (currency, rate_date) |
| `trades` | custodian messages (nested JSON) | incremental on `updated_at`, every version kept (merge on trade_id + version), schema contract frozen |
| `settlements`, `custodian_positions`, `flows`, `prices` | files | merge on their business keys |
| `funds`, `share_classes`, `securities` | reference files | replace |
| `fund_attributes` | reference file | merge on fund_id; dbt's snapshot keeps the history |

Re-running any load is safe: nothing is duplicated (`./run.sh check 2` proves it).
