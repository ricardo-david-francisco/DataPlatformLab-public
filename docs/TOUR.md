# The tour: run it, read it, check it (about 75 minutes)

Nine steps, start to end. In each one: **run** the command, **open** the files, and **check** it. A few steps have a
**Try it** task, and each ends with a design question worth thinking through. The checks tell you if it worked.

**Where:** a Linux terminal (or WSL) with the requirements installed (see the README), in the repository's folder:

```bash
cd DataPlatformLab-public
./run.sh            # the whole platform, end to end (about 30 s)
./run.sh check 0    # each step has a check: 0 to 8
./run.sh sql --snowflake "select ..."   # query the warehouse in Snowflake SQL
```

---

## 0. The whole thing, once (5 min)

**Run:** `./run.sh`, then `./run.sh summary`. **Check:** `./run.sh check 0`

**Look at:** the six stages it prints: data, dlt, dbt snapshot, the 11 Nov change and `dbt build` (57 models and
tests), the migration parity, the summary.

**Think about it:** *"What does this platform do, in one sentence?"*
> Custodian, transfer-agent and market data land in a raw layer with dlt; dbt turns them into tested marts: positions,
> trades, fees, fund KPIs; the legacy warehouse's logic is translated and compared, so we know we can switch.

## 1. The data (5 min)

**Open:** `scripts/generate_data.py`, then `data/reference/*.csv` and one `data/custody/trades/*.json`.
**Check:** `./run.sh check 1` (it validates every real ISIN's check digit).

**What's real:** the ECB FX rates (loaded live in step 2), the listed companies' ISINs, the SICAV-style fund and
share-class structure. **What's synthetic:** prices, trades (with amendments), settlements (some late),
custodian positions (3 planted breaks), subscriptions and redemptions.

**Think about it:** *"What is a trade's life in this data?"*
> Booked on T as version 1; sometimes amended the same day (version 2); settles at T+2 or late; changes the
> position; the custodian reports its own positions, and we reconcile.

## 2. Ingestion with dlt (10 min)

**Open:** `ingestion/pipelines.py`. **Check:** `./run.sh check 2` (it re-runs a load and proves nothing duplicates).

**Look at:**
- `ecb_fx_rates`: a REST API, `dlt.sources.incremental("rate_date")`: only new days are asked for; merge on (currency, date).
- `custodian_trades`: nested JSON (`execution.side` becomes `execution__side`); merge on (trade_id, version);
  `schema_contract` frozen: a new field in the feed fails the load instead of breaking a report.
- the `write_disposition` of each resource: append, replace, merge.

**Try it:** run `./run.sh sql "select * from raw_custody._dlt_loads"`. What is a load id for?

**Think about it:** *"How do you load a feed that sends amendments, without duplicates, every day?"*

## 3. dbt staging and tests (10 min)

**Open:** `transform/models/staging/` and `_staging.yml`. **Check:** `./run.sh check 3`

**Look at:** one model per source table: rename, cast, nothing clever. Tests next to the models: `unique`,
`not_null`, `accepted_values`, `relationships`.

**Try it:** add an `accepted_values` test on `stg_transfer_agent__flows.flow_type` (SUBSCRIPTION, REDEMPTION)
in `_staging.yml`, then `./run.sh check 3` again.

**Think about it:** *"How do you know the data is right before anyone uses it?"*

## 4. The marts: a data product, a snapshot, reconciliation (15 min)

**Open:** `transform/models/marts/fct_positions_daily.sql`, `_marts.yml`, `transform/snapshots/`,
`fct_reconciliation_breaks.sql`. **Check:** `./run.sh check 4`

**Look at:**
- `fct_positions_daily`: **the data product**. Grain fund x ISIN x day, valued in EUR with the ECB rate of the day.
  Its **contract** is enforced: change a column's type and the build fails.
- `int_trades_latest`: the latest amendment wins (QUALIFY); its **unit test** is in `_intermediate.yml`.
- `snap_fund_attributes` → `dim_fund`: **SCD2**. One fund changed manager and risk class on 11 Nov: both versions kept.
- `fct_reconciliation_breaks`: ours vs the custodian's, full outer join: **3 breaks**.

**Try it:** `./run.sh sql "select * from marts.fct_reconciliation_breaks"`. For each break, what would you ask
operations?

**Think about it:** *"What makes a gold table a data product?"*

## 5. The semantic layer: KPIs defined once (5 min)

**Open:** `transform/models/marts/fct_fund_kpis_monthly.sql` and its `meta` in `_marts.yml`. **Check:** `./run.sh check 5`

**Look at:** AUM month-end is **semi-additive** (the last business day, never a sum of days); net flows and fees
are additive; fees are rounded **once**, at the end of the month.

**Try it:** run this. Why is it wrong?
`./run.sh sql "select fund_id, sum(market_value_eur) from marts.fct_positions_daily where position_date between '2026-10-01' and '2026-10-31' group by 1"`

**Think about it:** *"What's a semantic model, and why does finance need one?"*

## 6. The warehouse migration: translate, run, compare (15 min)

**Open:** `migration/legacy/*.sql` (T-SQL), `migration/translated/snowflake/`, `migration/parity.py`,
then `migration/reports/parity.md`. **Check:** `./run.sh check 6`

**Look at:**
- `translate.py`: sqlglot turns T-SQL into Snowflake SQL (ISNULL → COALESCE, CONVERT → CAST, `[brackets]` dropped:
  quoted names would become case-sensitive in Snowflake).
- `parity.py` runs the **legacy procedures themselves** (translated) on the same inputs and compares per day:
  counts, sums, then a hash per row. It found two things:
  1. positions differ wherever a trade was **amended**: the legacy procedure keeps `Version = 1`;
  2. fees differ by **cents**: the legacy rounds every day, the new model once a month.
- One trap it hit: `DECIMAL(18,4)` prints `1550.0000` and a double `1550.0`. Cast before hashing.

**Try it:** in `migration/legacy/02_usp_load_fact_positions.sql`, make the legacy procedure use the latest
version (hint: it's in the WHERE clause), re-run `python migration/parity.py`, and watch the position differences
disappear. Then undo it (`git checkout migration/legacy`).

**Think about it:** *"How do you migrate a SQL Server warehouse, and prove it's right?"*

## 7. Orchestration: the Airflow DAG (5 min)

**Open:** `orchestration/dags/post_trade_daily.py`. **Check:** `./run.sh check 7`

**Look at:** the dlt loads run in parallel → dbt snapshot → dbt build → parity → publish. Retries, a failure
callback that alerts the owning team, and the data interval.

**Think about it:** *"What's in the DAG, and what happens at 02:00 when the custodian file is late?"*

## 8. The platform as code: Terraform, Docker, Kubernetes, CI (10 min)

**Open:** `platform/terraform/*.tf`, `deploy/Dockerfile`, `deploy/k8s/`, `.github/workflows/ci.yml`.
**Check:** `./run.sh check 8`

**Look at:**
- Terraform (Snowflake provider): a warehouse (XSMALL, auto-suspend 60 s), the database and schemas,
  **access roles vs functional roles**, grants, a **resource monitor** that caps the credits.
- The Dockerfile: multi-stage, non-root; the Kubernetes Job and CronJob run the same pipeline daily.
- CI: every pull request runs the tests, `dbt build` on DuckDB, `terraform validate` and `docker build`.

**Think about it:** *"How would a new domain team get their Snowflake database, roles and pipeline?"*

---

**Done?** Each part should now be clear: what it does, why, and what would change in production
(`docs/RUNBOOK.md`).
