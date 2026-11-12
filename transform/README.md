# Transform: dbt

Staging (one model per source table: rename, cast) → intermediate (latest trade version, FX for every business day,
positions) → marts:

| Mart | What it is |
|---|---|
| `fct_positions_daily` | **The data product**: positions per fund x ISIN x day in EUR. Contract enforced |
| `fct_trades`, `fct_settlement_fails` | Trades in their current version, with the settlement outcome |
| `fct_reconciliation_breaks` | Our positions vs the custodian's |
| `fct_fee_accrual` | Management fees, accrued daily |
| `fct_fund_kpis_monthly` | **The semantic layer**: AUM month-end (semi-additive), net flows, fee income |
| `dim_fund` | SCD2, from the `snap_fund_attributes` snapshot |

57 nodes in `dbt build`: models, 32 data tests, 2 unit tests, the snapshot. Targets: `local` (DuckDB, also CI) and
`snowflake` (key-pair auth).
