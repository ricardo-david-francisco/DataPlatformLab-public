# Migration: from the legacy SQL Server warehouse

1. `legacy/*.sql`: the old warehouse's DDL and the bodies of two nightly procedures, in T-SQL.
2. `translate.py`: sqlglot translates them to Snowflake SQL (`translated/snowflake/`), a reviewed first draft.
3. `parity.py`: runs the legacy procedures themselves (translated to DuckDB) on the same inputs, compares them
   with the dbt marts per day (counts, sums, a hash per row) and writes `reports/parity.md`.

What it found:
- **Positions** differ wherever a trade was amended: the legacy procedure keeps `Version = 1`. The new model is
  right (it matches the custodian).
- **Fees** differ by cents: the legacy rounds each day, the new model once a month; within the agreed tolerance.
- A trap on the way: `DECIMAL(18,4)` prints `1550.0000` and a double `1550.0`. Cast before hashing.
