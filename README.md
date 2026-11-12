<!-- brand:header:start -->
<h1 align="center">DataPlatformLab</h1>

<p align="center">
  <b>An asset manager's post-trade data platform, end to end,<br>compared on the two market leaders: the Snowflake stack and Databricks.</b>
</p>
<p align="center">
  Built and tested: dlt, dbt on Snowflake or DuckDB, Airflow, Terraform, Docker and Kubernetes, CI on every push.<br>Mapped layer by layer to Databricks (Delta Lake, Unity Catalog, Lakeflow Jobs, Asset Bundles): the Databricks build is phase 2.
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="dlt 1.32" src="https://img.shields.io/badge/dlt-1.32-5A5A5A">
  <img alt="dbt 1.12" src="https://img.shields.io/badge/dbt-1.12-FF694B?logo=dbt&logoColor=white">
  <img alt="Snowflake" src="https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white">
  <img alt="DuckDB" src="https://img.shields.io/badge/DuckDB-FFF000?logo=duckdb&logoColor=black">
  <img alt="Apache Airflow 3" src="https://img.shields.io/badge/Apache%20Airflow-3-017CEE?logo=apacheairflow&logoColor=white">
  <br>
  <img alt="Databricks phase 2" src="https://img.shields.io/badge/Databricks-phase%202-FF3621?logo=databricks&logoColor=white">
  <img alt="Apache Spark phase 2" src="https://img.shields.io/badge/Apache%20Spark-phase%202-E25A1C?logo=apachespark&logoColor=white">
  <img alt="Delta Lake phase 2" src="https://img.shields.io/badge/Delta%20Lake-phase%202-00ADD4">
  <br>
  <img alt="Terraform" src="https://img.shields.io/badge/Terraform-844FBA?logo=terraform&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white">
  <img alt="Kubernetes" src="https://img.shields.io/badge/Kubernetes-326CE5?logo=kubernetes&logoColor=white">
  <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white">
  <img alt="licence MIT" src="https://img.shields.io/badge/licence-MIT-blue">
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/dataplatformlab-architecture-dark.svg">
    <img alt="DataPlatformLab, the same layers on two engines. Sources: the ECB API, the custodian, the transfer agent, market data and a legacy SQL Server warehouse. The Snowflake stack, built and tested: dlt loads raw, dbt builds staging and marts, sqlglot and a parity check prove the migration; Airflow, Docker, Kubernetes, GitHub Actions and Terraform run and ship it. The Databricks lakehouse, the same design, not built yet: PySpark MERGE into Delta bronze, silver and gold, Lakeflow Jobs in Asset Bundles, Unity Catalog and serverless SQL warehouses. Consumers: finance, operations, risk, Power BI and an AI lab." src="docs/assets/dataplatformlab-architecture-light.svg" width="100%">
  </picture>
</p>

## At a glance

<table>
  <tr><td width="190"><b>What it is</b></td><td>The post-trade domain of a fictional European asset manager: custodian, transfer-agent and market feeds become tested data products (positions, trades, reconciliation breaks, fees, fund KPIs).</td></tr>
  <tr><td width="190"><b>How it's built</b></td><td>dlt loads the raw layer (incremental, merge, schema contracts); dbt builds staging, intermediate and marts with a model contract, an SCD2 snapshot, data and unit tests; Airflow runs it nightly.</td></tr>
  <tr><td width="190"><b>The migration</b></td><td>The legacy SQL Server warehouse's T-SQL is translated by sqlglot, run on the same inputs, and compared with the new marts per day. Every difference is explained.</td></tr>
  <tr><td width="190"><b>Platform as code</b></td><td>Terraform creates the Snowflake side (warehouse, roles, grants, resource monitor); Docker and a Kubernetes CronJob run the pipeline; CI checks every push.</td></tr>
  <tr><td width="190"><b>Two market leaders</b></td><td>One design, two engines. Phase 1 builds it on the Snowflake stack and runs it end to end; phase 2 builds the same example on Databricks (Delta Lake, Unity Catalog, Lakeflow Jobs in Asset Bundles). The translation, with code on both sides: <a href="#the-code-side-by-side">the code, side by side</a> and <a href="docs/HOW_IT_WORKS.md">how it works, layer by layer</a>.</td></tr>
</table>

<table>
  <tr>
    <td align="center"><b>57</b><br>dbt nodes per build<br>(models, tests, snapshot)</td>
    <td align="center"><b>34</b><br>real ISINs<br>+ live ECB FX rates</td>
    <td align="center"><b>0</b><br>unexplained differences<br>legacy vs new</td>
    <td align="center"><b>30 s</b><br>end to end<br>on a laptop</td>
  </tr>
</table>

## Tech stack

| Area | Built: the Snowflake stack | The same on Databricks (phase 2) |
|---|---|---|
| **Ingestion** | dlt (dlthub): REST and file sources, incremental cursors, merge on business keys, schema contracts; DuckDB or Snowflake destinations | PySpark reads only what's new and MERGEs it into Delta on the same keys; Delta's schema enforcement is the contract |
| **Transformation** | dbt: staging, intermediate, marts; model contract, SCD2 snapshot, generic, singular and unit tests | Spark SQL on Delta (bronze, silver, gold), MERGE into gold; or the same dbt project on dbt-databricks |
| **Migration** | sqlglot T-SQL to Snowflake translation; a parity checker (counts, sums, row hashes) with explained differences | sqlglot T-SQL to Databricks SQL; the same parity checker |
| **Orchestration** | Apache Airflow 3: nightly DAG, parallel loads, retries, failure callback | A Lakeflow Job: tasks chained with <code>depends_on</code>, a cron schedule, retries, failure notifications |
| **Governance** | Access and functional roles, future grants | Unity Catalog: catalogs and schemas, grants to account groups |
| **Compute and cost** | XSMALL warehouse with auto-suspend; a resource monitor | Serverless SQL warehouse with auto-stop; budget policies and billing system tables |
| **Platform as code** | Terraform (snowflakedb/snowflake): warehouse, database, schemas, roles, grants, resource monitor | Asset Bundles for jobs and SQL warehouses; Terraform (databricks/databricks) for the workspace |
| **Delivery** | Docker (multi-stage, non-root), Kubernetes Job and CronJob, GitHub Actions CI | <code>databricks bundle deploy</code> from CI (GitHub Actions, Jenkins, ...); serverless jobs, no image to run |

---
<!-- brand:header:end -->

<p align="center">
  <a href="https://github.com/ricardo-david-francisco/DataPlatformLab-public/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/ricardo-david-francisco/DataPlatformLab-public/actions/workflows/ci.yml/badge.svg"></a>
</p>

## Contents

- [The same platform on the two market leaders](#the-same-platform-on-the-two-market-leaders)
- [The code, side by side](#the-code-side-by-side)
- [The 5-minute tour](#the-5-minute-tour)
- [Run it](#run-it)
- [The data](#the-data)
- [At a glance](#at-a-glance)
- [Tech stack](#tech-stack)
- [Status](#status)

---

## The same platform on the two market leaders

DataPlatformLab compares how the two market-leading data platforms build **the same data platform**: the Snowflake
stack (Snowflake with dlt, dbt and Airflow around it) and the Databricks lakehouse (Delta Lake, Unity Catalog,
Lakeflow Jobs). It is built in two phases, on the same example:

| Phase | Engine | Status |
|---|---|---|
| **1** | **Snowflake** (DuckDB locally and in CI) with dlt, dbt, Airflow, Terraform, Docker and Kubernetes | **Done**: runs end to end, locally and on a Snowflake account |
| **2** | **Databricks** (Delta Lake, Unity Catalog, Lakeflow Jobs in Asset Bundles) on the same data, models and checks | **Planned**: each layer is mapped below and in [How it works](docs/HOW_IT_WORKS.md) |

The comparison shows which parts of a platform depend on the engine and which don't. The domain model, the grain of
each table, the tests, the reconciliation and the migration checks stay the same; storage, compute, access control,
orchestration and deployment change. In the diagram, each column is one layer: the Snowflake lane on top is built
and tested, and the Databricks lane below it is dashed because it is the design, not built yet. The tech stack above
has both columns; **[How it works](docs/HOW_IT_WORKS.md)** walks through every layer with its code and the Databricks
equivalent.

## The code, side by side

Four steps of this repository, each followed by the same step on Databricks. The Snowflake-stack code is quoted from
this repository and runs in CI; the Databricks code is a sketch of phase 2 with standard Databricks APIs.

### 1. Loading the trades

**Snowflake stack: dlt** ([`ingestion/pipelines.py`](ingestion/pipelines.py))

```python
@dlt.resource(name="trades", primary_key=["trade_id", "version"], write_disposition="merge",
              schema_contract={"tables": "evolve", "columns": "freeze", "data_type": "freeze"})
def custodian_trades(folder: Path, updated_at=dlt.sources.incremental("updated_at", initial_value="2026-01-01T00:00:00Z")):
    for path in sorted(folder.glob("trades_*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))
```

**The same on Databricks: a notebook task that MERGEs into Delta**

```python
from delta.tables import DeltaTable
from pyspark.sql import functions as F

dbutils.widgets.text("since", "")                 # a job parameter; empty: continue from the table
since = dbutils.widgets.get("since") or spark.table("dpl.bronze.trades").agg(F.max("updated_at")).first()[0]

new = (spark.read.json("/Volumes/dpl/landing/custody/trades/")
            .where(F.col("updated_at") >= since))  # = dlt.sources.incremental("updated_at")

(DeltaTable.forName(spark, "dpl.bronze.trades").alias("t")
    .merge(new.alias("s"), "t.trade_id = s.trade_id and t.version = s.version")  # = primary_key + "merge"
    .whenMatchedUpdateAll()
    .whenNotMatchedInsertAll()
    .execute())
```

- **Stays the same:** only new messages are read, and the merge on `(trade_id, version)` means a re-run never
  duplicates a trade.
- **Differs:** dlt keeps its cursor in its own state and flattens nested JSON with `__`. On Databricks the window is a
  job parameter or the table's high-water mark, and nested JSON stays as structs until staging (`explode` for lists).
  Delta's schema enforcement rejects an unexpected column unless schema evolution is switched on: that is the
  frozen contract.

### 2. The latest version of each trade

**Snowflake stack: dbt** ([`int_trades_latest.sql`](transform/models/intermediate/int_trades_latest.sql))

```sql
select *
from {{ ref('stg_custody__trades') }}
qualify row_number() over (partition by trade_id order by version desc) = 1
```

**The same on Databricks: Databricks SQL, kept in a gold Delta table with a MERGE**

```sql
MERGE INTO dpl.gold.trades_latest AS t
USING (
  SELECT * FROM dpl.silver.trades
  QUALIFY row_number() OVER (PARTITION BY trade_id ORDER BY version DESC) = 1
) AS s
ON t.trade_id = s.trade_id
WHEN MATCHED AND s.version > t.version THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

- **Stays the same:** the rule (the latest amendment wins), written as the same window function.
- **Differs:** dbt turns the `SELECT` into the table and the merge; on Databricks the `MERGE` is written out.

### 3. The nightly order

**Snowflake stack: Airflow** ([`orchestration/dags/post_trade_daily.py`](orchestration/dags/post_trade_daily.py))

```python
loads >> snapshot >> build >> parity >> publish
```

**The same on Databricks: a Lakeflow Job, defined in an Asset Bundle** (Databricks now calls them Declarative
Automation Bundles)

```yaml
resources:
  jobs:
    post_trade_daily:
      name: post_trade_daily
      schedule:
        quartz_cron_expression: "0 0 2 ? * MON-FRI"   # the DAG's "0 2 * * 1-5"
        timezone_id: UTC
      tasks:
        - task_key: loads                            # the five loads, in parallel
          for_each_task:
            inputs: '["ecb", "reference", "market", "custody", "transfer_agent"]'
            concurrency: 5
            task:
              task_key: load_source
              notebook_task: { notebook_path: ../src/load.py, base_parameters: { source: "{{input}}" } }
              max_retries: 2
        - task_key: snapshot
          depends_on: [{ task_key: loads }]
          notebook_task: { notebook_path: ../src/snapshot.py }
        - task_key: build
          depends_on: [{ task_key: snapshot }]
          notebook_task: { notebook_path: ../src/build.py }
        - task_key: parity
          depends_on: [{ task_key: build }]
          notebook_task: { notebook_path: ../src/parity.py }
        - task_key: publish
          depends_on: [{ task_key: parity }]
          notebook_task: { notebook_path: ../src/publish.py }
```

- **Stays the same:** the dependency graph, the schedule in UTC and the retries.
- **Differs:** Airflow is a separate service that calls each tool; the Lakeflow Job runs inside the workspace, and the
  bundle is deployed like any other code.

### 4. The warehouse

**Snowflake stack: Terraform** ([`platform/terraform/main.tf`](platform/terraform/main.tf))

```hcl
resource "snowflake_warehouse" "dpl" {
  name                = "DPL_WH"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  # ...
}
```

**The same on Databricks: a SQL warehouse in the same Asset Bundle**

```yaml
resources:
  sql_warehouses:
    dpl:
      name: DPL_WH
      cluster_size: 2X-Small
      warehouse_type: PRO
      enable_serverless_compute: true
      auto_stop_mins: 1                  # = auto_suspend = 60 seconds
      max_num_clusters: 1
      permissions:
        - group_name: dpl_finance_analysts
          level: CAN_USE
```

CI (GitHub Actions, Jenkins or any other) deploys the jobs and the warehouse together:
`databricks bundle validate`, then `databricks bundle deploy -t prod` (`sql_warehouses` needs Databricks CLI 0.260
or later; Terraform's `databricks_sql_endpoint` does the same).

- **Stays the same:** the smallest size, stopped when idle, created as code, used by a group rather than a person.
- **Differs:** serverless starts in seconds; the cost cap is a budget policy instead of a resource monitor.

## The 5-minute tour

The domain: **post-trade at a European asset manager** (fictional, "Boreal Asset Management"). Five funds,
their trades, settlements, positions, fees, and an old SQL Server warehouse to migrate. One link per idea:

| # | Look at | What it shows |
|---|---|---|
| 1 | [`ingestion/pipelines.py`](ingestion/pipelines.py) | **dlt** loads a live REST API (ECB FX), nested custodian JSON and files: incremental, merge on business keys, a frozen schema contract. Re-runs never duplicate. |
| 2 | [`transform/models/marts/fct_positions_daily.sql`](transform/models/marts/fct_positions_daily.sql) | **The data product**: positions per fund x security x day in EUR. **dbt model contract** enforced, tested, documented. |
| 3 | [`transform/snapshots/`](transform/snapshots/snap_fund_attributes.yml) → [`dim_fund`](transform/models/marts/dim_fund.sql) | **SCD Type 2**: a fund's manager and risk class change; history kept. |
| 4 | [`fct_reconciliation_breaks.sql`](transform/models/marts/fct_reconciliation_breaks.sql) | **Post-trade reconciliation**: our positions vs the custodian's. It finds the 3 planted breaks. |
| 5 | [`fct_fund_kpis_monthly.sql`](transform/models/marts/fct_fund_kpis_monthly.sql) | **The semantic layer**: AUM month-end (semi-additive), net flows, fees, each defined once. |
| 6 | [`migration/`](migration/README.md) → [`parity.py`](migration/parity.py) | **The warehouse migration**: legacy T-SQL translated by sqlglot, run, and compared with the new marts. Every difference explained (trade amendments, fee rounding). |
| 7 | [`orchestration/dags/post_trade_daily.py`](orchestration/dags/post_trade_daily.py) | **Airflow**: loads → snapshot → build with tests → parity → publish, nightly, retries, failure alerts. |
| 8 | [`platform/terraform/main.tf`](platform/terraform/main.tf) | **Snowflake as code**: warehouse with auto-suspend, database and schemas, access vs functional roles, future grants, a resource monitor. |
| 9 | [`deploy/`](deploy/README.md), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | **Docker + Kubernetes** (CronJob) and **CI** on every push: lint, tests, dbt build, Terraform validate, image build. |
| 10 | [`mcp_server/server.py`](mcp_server/server.py) | **AI-ready**: an MCP server lets an assistant query the data product (read-only, Snowflake SQL accepted; local DuckDB or [Snowflake](docs/SNOWFLAKE.md#6-an-ai-assistant-on-snowflake-the-mcp-server)), run the checks and dbt. One-click install for Claude Desktop: `npx @anthropic-ai/mcpb pack mcp_server/bundle` builds the `.mcpb`. |

Deeper: [how it works, layer by layer](docs/HOW_IT_WORKS.md) (with the Databricks equivalent of each), the
step-by-step [tour with checks](docs/TOUR.md) and the [runbook](docs/RUNBOOK.md).

## Run it

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
./run.sh              # data -> dlt -> dbt snapshot + build (57 nodes) -> migration parity -> summary, about 30 s
./run.sh check 4      # each step of the tour has a check (0-8)
./run.sh sql --snowflake "select fund_id, iff(difference > 0, 'ours', 'custodian') from marts.fct_reconciliation_breaks"
```

On Snowflake: `platform/terraform` creates the account objects (key-pair auth), then
`pip install -r requirements-snowflake.txt` and `./run.sh --target snowflake`.

## The data

**Real, public reference data:** the ECB's euro FX reference rates (loaded live by dlt), well-known listed companies
with their real ISINs (check digits validated), funds and share classes modelled on a Luxembourg SICAV.
**Synthetic and seeded:** prices, trades with amendments, settlements (some late), custodian positions (with planted
breaks), subscriptions and redemptions, January to November 2026. *Synthetic transactions on public reference data:
no real fund's data.*

## Status

**Phase 1 (Snowflake): done.** Runs end to end on DuckDB locally and in CI, and on a Snowflake account: the same
dbt project and dlt pipelines target both, and Terraform creates the Snowflake objects.
**Phase 2 (Databricks): planned.** Every layer is mapped in [The code, side by side](#the-code-side-by-side) and
[How it works](docs/HOW_IT_WORKS.md); the same example will be built on Delta Lake, Unity Catalog and Lakeflow Jobs
in Asset Bundles.

<!-- brand:footer:start -->

---

<p align="center">
  <sub>Maintained by <a href="https://github.com/ricardo-david-francisco">Ricardo David Francisco</a> &nbsp;·&nbsp; MIT licence</sub>
</p>
<!-- brand:footer:end -->
