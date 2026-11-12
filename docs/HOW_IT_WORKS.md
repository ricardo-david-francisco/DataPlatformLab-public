# How it works: layer by layer, and the same platform on Databricks

DataPlatformLab compares how the **two market-leading data platforms** build the same data platform: one realistic
domain (post-trade at a fictional asset manager), end to end, from source feeds to tested data products, with the
platform itself as code. One side is the Snowflake stack (Snowflake with dlt, dbt and Airflow around it); the other
is the Databricks lakehouse (Delta Lake, Unity Catalog, Lakeflow Jobs in Asset Bundles).

It is built in two phases, on the same example:

| Phase | Engine | Status |
|---|---|---|
| **1** | **Snowflake** (and DuckDB locally and in CI), with dlt, dbt, Airflow, Terraform, Docker and Kubernetes | **Done**: this repository runs end to end, locally and on a Snowflake account |
| **2** | **Databricks** (Delta Lake, Unity Catalog, Lakeflow Jobs in Asset Bundles), on the same data, models and checks | **Planned**: this page describes how each layer maps, with sketches; the code will land in the repository |

The point of phase 2 is not a second copy. It shows **which parts of a platform depend on the engine and which
don't**: the domain model, the tests, the reconciliation and the migration checks stay the same; storage, compute,
access control and deployment change. The README's [code, side by side](../README.md#the-code-side-by-side) shows four
of the steps on both engines.

---

## The flow in one picture

```
 sources                raw (bronze)          staging (silver)        marts (gold)              consumers
 ECB FX API   ─┐
 custodian    ─┤  dlt   raw_ecb, raw_custody,  dbt staging models     dbt marts:                 finance, operations,
 transfer agt ─┼──────► raw_reference, ...  ─► (rename, cast, test) ─► fct_positions_daily,  ─►  risk, BI, an AI assistant
 market data  ─┤        (merge on keys,        + intermediate          fct_reconciliation_breaks,  (MCP server)
 legacy DWH   ─┘         incremental)           (latest version, ...)  fct_fund_kpis_monthly, ...
                                                                        ▲
 migration lane: legacy T-SQL ─ sqlglot ─► run on the same inputs ─► parity report (counts, sums, row hashes)

 Airflow runs it nightly · Terraform creates the warehouse, schemas, roles and cost guard · Docker + Kubernetes run it
```

The layer names follow dbt (**raw → staging → marts**). In medallion terms that is **bronze → silver → gold**.

---

## 1. Ingestion: sources → raw, with dlt

**What it does:** loads each source into its own raw schema, **incrementally** (only what's new) and **idempotently**
(re-running a load never duplicates rows).

**The code** ([`ingestion/pipelines.py`](../ingestion/pipelines.py)): the custodian's trade messages, where an
amendment arrives as a new version of the same trade:

```python
@dlt.resource(name="trades", primary_key=["trade_id", "version"], write_disposition="merge",
              schema_contract={"tables": "evolve", "columns": "freeze", "data_type": "freeze"})
def custodian_trades(folder: Path, updated_at=dlt.sources.incremental("updated_at", initial_value="2026-01-01T00:00:00Z")):
    """Custodian trade messages (nested JSON); amendments arrive as a new version of the same trade_id."""
    for path in sorted(folder.glob("trades_*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))
```

**How to read it:**
- `primary_key` + `write_disposition="merge"`: dlt writes a MERGE on `(trade_id, version)`, so a re-run updates
  rather than duplicates.
- `dlt.sources.incremental("updated_at")`: dlt remembers the highest `updated_at` it loaded (in its state, stored in
  the destination) and the next run skips older messages. A failed night doesn't leave a gap: the cursor only moves
  after a successful load.
- `schema_contract`: new tables may appear (`evolve`), but a **new column or a changed type fails the load**
  (`freeze`) instead of silently changing a report. Other modes are `discard_value` (drop the unexpected column) and
  `discard_row`.
- Nested JSON is flattened with `__`: `execution.side` becomes `execution__side`. Lists become child tables.
- Every load is recorded in `_dlt_loads` in the same dataset: the load log comes for free.

**The same on Databricks (phase 2):**

*Route A, same code:* dlt has a Databricks destination. Only the destination changes; the raw tables become Delta
tables in a Unity Catalog schema.

```python
pipeline = dlt.pipeline(pipeline_name="dpl_custody", destination="databricks", dataset_name="raw_custody")
```

*Route B, Databricks-native:* Auto Loader reads new files as they land; a checkpoint plays the role of the
incremental cursor, and a MERGE per micro-batch plays the role of `write_disposition="merge"`.

```python
from delta.tables import DeltaTable

trades = (spark.readStream.format("cloudFiles")
          .option("cloudFiles.format", "json")
          .option("cloudFiles.schemaLocation", "/Volumes/dpl/raw/_schemas/trades")
          .option("cloudFiles.schemaEvolutionMode", "failOnNewColumns")   # = the frozen schema contract
          .load("/Volumes/dpl/raw/landing/custody/trades/"))

def upsert(batch, _batch_id):                                          # = merge on (trade_id, version)
    (DeltaTable.forName(spark, "dpl.raw.trades").alias("t")
        .merge(batch.alias("s"), "t.trade_id = s.trade_id and t.version = s.version")
        .whenNotMatchedInsertAll().execute())

(trades.writeStream.foreachBatch(upsert)
    .option("checkpointLocation", "/Volumes/dpl/raw/_checkpoints/trades")  # = the incremental cursor
    .trigger(availableNow=True).start())
```

Spark keeps nested JSON as structs (`execution.side`), so the flattening moves to the staging model.

---

## 2. Staging: rename, cast, test (dbt)

**What it does:** one model per raw table. Rename, cast, nothing clever. Tests sit next to the models.

**The code** ([`stg_custody__trades.sql`](../transform/models/staging/stg_custody__trades.sql)):

```sql
select
    message_id, trade_id, version, fund_id,
    instrument__isin as isin,
    execution__side as side,
    cast(execution__quantity as double) as quantity,
    cast(execution__price as double) as price,
    cast(trade_date as date) as trade_date,
    updated_at
from {{ source('custody', 'trades') }}
```

**How to read it:** `{{ source(...) }}` points at the raw table dlt loaded; dbt resolves it per target (DuckDB or
Snowflake). `_staging.yml` declares the tests: `unique`, `not_null`, `accepted_values`, `relationships`. A failed
test stops `dbt build` before anything downstream is built.

**The same on Databricks:** dbt runs on Databricks too (the `dbt-databricks` adapter): add a `databricks` output to
[`profiles.yml`](../transform/profiles.yml) and the same models build Delta tables in Unity Catalog. Small dialect
differences: `varchar` becomes `string`, and nested fields are read as `execution.side`. The native alternative is a
Lakeflow Declarative Pipeline, where **expectations** (`EXPECT (quantity > 0) ON VIOLATION FAIL UPDATE`) play the
role of dbt tests.

---

## 3. Intermediate: the latest version of each trade

**The code** ([`int_trades_latest.sql`](../transform/models/intermediate/int_trades_latest.sql)):

```sql
-- The current version of each trade: the latest amendment wins.
select *
from {{ ref('stg_custody__trades') }}
qualify row_number() over (partition by trade_id order by version desc) = 1
```

**How to read it:** raw keeps every version (the audit trail); this model keeps one row per trade. `QUALIFY` filters
on a window function without a sub-query. `{{ ref(...) }}` is how dbt knows the build order: it reads the refs and
builds a graph, so nobody maintains the order by hand. A **unit test** in `_intermediate.yml` feeds it two versions
of one trade and expects only the second.

**The same on Databricks:** the SQL is unchanged (Databricks SQL supports `QUALIFY`). Natively, a declarative
pipeline does it with **AUTO CDC**:

```sql
CREATE OR REFRESH STREAMING TABLE trades_current;
CREATE FLOW trades_latest AS AUTO CDC INTO trades_current
FROM STREAM(dpl.raw.trades)
KEYS (trade_id)
SEQUENCE BY version
STORED AS SCD TYPE 1;
```

---

## 4. The data product: positions, with a contract

**The code** ([`fct_positions_daily.sql`](../transform/models/marts/fct_positions_daily.sql) and
[`_marts.yml`](../transform/models/marts/_marts.yml)):

```sql
select
    cast(p.fund_id as varchar) as fund_id,
    cast(p.isin as varchar) as isin,
    cast(p.business_date as date) as position_date,
    cast(p.quantity as double) as quantity,
    cast(p.quantity * px.close_price / fx.units_per_eur as double) as market_value_eur
from {{ ref('int_positions_daily') }} p
join {{ ref('stg_market__prices') }} px on px.isin = p.isin and px.price_date = p.business_date
join {{ ref('int_fx_daily') }} fx on fx.currency = px.currency and fx.business_date = p.business_date
```

```yaml
  - name: fct_positions_daily
    description: >
      The post-trade domain's data product: positions per fund x security x business day, valued in EUR ...
    config:
      contract:
        enforced: true
    columns:
      - name: fund_id
        data_type: varchar
        data_tests: [not_null]
```

**How to read it:** the grain is one row per fund, security and day, valued with the ECB rate of that day. The
**contract** is a promise to consumers: the column names and types are checked at build time, so an accidental
change fails the build instead of breaking a report. The description names the owner and the time it's ready.

**The same on Databricks:** the dbt contract works the same way on Databricks. Natively, the table's schema is
declared in the pipeline, and Unity Catalog adds an owner, comments, tags and lineage to every column.

---

## 5. History: SCD Type 2 with a snapshot

**The code** ([`snap_fund_attributes.yml`](../transform/snapshots/snap_fund_attributes.yml)):

```yaml
snapshots:
  - name: snap_fund_attributes
    relation: source('reference', 'fund_attributes')
    config:
      unique_key: fund_id
      strategy: check
      check_cols: [portfolio_manager, risk_class, sfdr_article]
```

**How to read it:** each run compares the three columns with the last version it saw; when one changes, the old row
is closed (`dbt_valid_to`) and a new one opened. `dim_fund` reads the snapshot, so a report can ask "who managed
this fund on 1 October?".

**The same on Databricks:** `dbt snapshot` works unchanged. Natively: `AUTO CDC ... STORED AS SCD TYPE 2` in a
declarative pipeline (or `create_auto_cdc_from_snapshot_flow` when the source is a full snapshot each day).

---

## 6. Reconciliation: ours against the custodian's

**The code** ([`fct_reconciliation_breaks.sql`](../transform/models/marts/fct_reconciliation_breaks.sql)):

```sql
select
    coalesce(o.fund_id, t.fund_id) as fund_id,
    coalesce(o.isin, t.isin) as isin,
    coalesce(o.position_date, t.position_date) as position_date,
    o.quantity as our_quantity,
    t.quantity as custodian_quantity,
    coalesce(o.quantity, 0) - coalesce(t.quantity, 0) as difference
from ours o
full outer join theirs t
    on t.fund_id = o.fund_id and t.isin = o.isin and t.position_date = o.position_date
where coalesce(o.quantity, 0) <> coalesce(t.quantity, 0)
```

**How to read it:** a **full outer join** finds three kinds of break: a quantity that differs, a position only we
have, and a position only the custodian has. The data has 3 planted breaks; the model finds all 3.

**The same on Databricks:** the same SQL. On top, Lakeflow expectations or data quality monitoring can alert when
the number of breaks jumps.

---

## 7. The semantic layer: KPIs defined once

**The code** ([`fct_fund_kpis_monthly.sql`](../transform/models/marts/fct_fund_kpis_monthly.sql)):

```sql
aum_month_end as (
    select fund_id, cast(date_trunc('month', position_date) as date) as month, aum_eur as aum_month_end_eur
    from aum
    qualify row_number() over (partition by fund_id, date_trunc('month', position_date)
                               order by position_date desc) = 1
),
fees as (
    select fund_id, cast(date_trunc('month', accrual_date) as date) as month,
           round(sum(fee_eur), 2) as fee_income_eur
    from {{ ref('fct_fee_accrual') }}
    group by fund_id, cast(date_trunc('month', accrual_date) as date)
)
```

**How to read it:** AUM is **semi-additive**: the month's value is the last business day's, never a sum of days.
Net flows and fees are additive; fees are rounded **once**, at the end of the month. Defining each measure once means
two reports can't disagree.

**The same on Databricks:** the same model; or a **Unity Catalog metric view** that defines the measures once for
dashboards and Genie. Snowflake's equivalent is a semantic view.

---

## 8. The warehouse migration: translate, run, compare

**The code** ([`migration/translate.py`](../migration/translate.py), [`migration/parity.py`](../migration/parity.py)):
sqlglot translates the legacy T-SQL procedures to Snowflake SQL; `parity.py` runs the **legacy logic itself** on the
same inputs and compares it with the new marts, per day: counts, sums, then a hash per row.

```sql
with legacy as (select FundCode as fund_id, ISIN as isin, PositionDate as d,
                       md5(concat_ws('|', FundCode, ISIN, ...)) as h from dw.FactPositions),
     new    as (select fund_id, isin, position_date as d,
                       md5(concat_ws('|', fund_id, isin, cast(position_date as varchar), ...)) as h
                from marts.fct_positions_daily)
```

**How to read it:** the comparison found two real differences and explained both
([`reports/parity.md`](../migration/reports/parity.md)): the legacy procedure ignores trade amendments (it keeps
version 1), and it rounds fees every day instead of once a month. One trap: `DECIMAL(18,4)` prints `1550.0000` and a
double `1550.0`, so values are cast before hashing.

**The same on Databricks:** sqlglot writes Databricks SQL too (`translate(sql, dialect="databricks")`), and the
parity check is plain SQL, so it runs on a SQL warehouse unchanged.

---

## 9. Orchestration: the nightly run (Airflow)

**The code** ([`orchestration/dags/post_trade_daily.py`](../orchestration/dags/post_trade_daily.py)):

```python
default_args = {
    "owner": "post-trade-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_failure,
}

with DAG(dag_id="post_trade_daily", schedule="0 2 * * 1-5", catchup=False, max_active_runs=1,
         default_args=default_args, ...) as dag:
    loads = [BashOperator(task_id=f"load_{source}", bash_command=f"... ingestion/pipelines.py --only {source}")
             for source in ("ecb", "reference", "market", "custody", "transfer_agent")]
    snapshot = BashOperator(task_id="dbt_snapshot", bash_command="... dbt snapshot")
    build = BashOperator(task_id="dbt_build", bash_command="... dbt build --exclude resource_type:snapshot")
    parity = BashOperator(task_id="migration_parity", bash_command="... migration/parity.py")
    publish = BashOperator(task_id="publish_positions_ready", ...)

    loads >> snapshot >> build >> parity >> publish
```

**How to read it:** the five loads run **in parallel**, then the steps run in order: `>>` declares the dependency, so
the build never starts before the loads finish. Every task is idempotent (merges, rebuilds), so a retry or a re-run of
a day is safe. After two retries, `notify_failure` alerts the owning team.

**The same on Databricks:** a **Lakeflow Job** declared in a bundle (`databricks.yml`), deployed by CI:

```yaml
resources:
  jobs:
    post_trade_daily:
      schedule: {quartz_cron_expression: "0 0 2 ? * MON-FRI", timezone_id: UTC}
      tasks:
        - task_key: load_custody
          notebook_task: {notebook_path: ../ingestion/load_custody.py}
          max_retries: 2
        - task_key: dbt_build
          depends_on: [{task_key: load_custody}]
          dbt_task: {project_directory: ../transform, commands: ["dbt deps", "dbt build"]}
```

Or Airflow stays the orchestrator and triggers the Databricks job (`DatabricksRunNowOperator`): useful when the
company already runs Airflow for everything else.

---

## 10. The platform as code: Terraform

**The code** ([`platform/terraform/main.tf`](../platform/terraform/main.tf)):

```hcl
# Compute: the smallest size, suspended after 60 s idle, resumed by the next query.
resource "snowflake_warehouse" "dpl" {
  name           = "DPL_WH"
  warehouse_size = "XSMALL"
  auto_suspend   = 60
}

# Cost guard: notify at 75% and 90% of the monthly credits, suspend the warehouse at 100%.
resource "snowflake_resource_monitor" "dpl" {
  name            = "DPL_MONITOR"
  credit_quota    = var.monthly_credit_quota
  notify_triggers = [75, 90]
  suspend_trigger = 100
}

# Access roles hold privileges; functional roles are what people and services get.
resource "snowflake_grant_account_role" "analyst_reads" {
  role_name        = snowflake_account_role.marts_read.name
  parent_role_name = snowflake_account_role.finance_analyst.name
}
```

**How to read it:** compute is separate from storage and costs nothing while suspended. **Access roles**
(`DPL_ALL_WRITE`, `DPL_MARTS_READ`) hold privileges, and **functional roles** (`DPL_ENGINEER`,
`DPL_FINANCE_ANALYST`) get access roles, so a new team is one grant, not twenty. Future grants cover tables that
don't exist yet. The resource monitor caps the monthly spend.

**The same on Databricks** (the `databricks/databricks` provider):

```hcl
resource "databricks_sql_endpoint" "dpl" {          # = the virtual warehouse
  name                      = "DPL_WH"
  cluster_size              = "2X-Small"
  auto_stop_mins            = 10
  enable_serverless_compute = true
}

resource "databricks_catalog" "dpl" { name = "dpl" }   # = the database

resource "databricks_schema" "layer" {               # = raw, staging, marts
  for_each     = toset(["raw", "staging", "marts"])
  catalog_name = databricks_catalog.dpl.name
  name         = each.key
}

resource "databricks_grants" "marts" {               # = the read access role
  schema = "${databricks_catalog.dpl.name}.marts"
  grant {
    principal  = "finance-analysts"
    privileges = ["USE_SCHEMA", "SELECT"]
  }
}
```

Unity Catalog privileges are inherited down the hierarchy, so a grant on a schema covers its future tables (Snowflake
needs explicit future grants). Groups come from the identity provider (SCIM). Cost is guarded by budgets, tags on
compute and the `system.billing.usage` table rather than a resource monitor.

---

## 11. Delivery: Docker, Kubernetes, CI

**The code** ([`deploy/k8s/cronjob.yaml`](../deploy/k8s/cronjob.yaml), [`ci.yml`](../.github/workflows/ci.yml)):

```yaml
kind: CronJob
spec:
  schedule: "0 2 * * 1-5"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          securityContext: {runAsNonRoot: true, runAsUser: 10001}
          containers:
            - name: pipeline
              image: dataplatformlab:latest
```

**How to read it:** the whole pipeline is one image (multi-stage, non-root). Kubernetes runs it every business day,
never two at once, retrying twice. CI checks every push: lint, the pipeline on DuckDB with the tour's checks, the
unit tests, the DAG import, `terraform validate`, the image build and the manifests.

**The same on Databricks:** compute is serverless jobs, so there's no image to run the pipeline. CI runs
`databricks bundle validate` on every pull request and `databricks bundle deploy -t prod` on release; the jobs run as
a service principal, not as a person. Docker and Kubernetes remain only for what runs outside Databricks (Airflow,
if it stays).

---

## 12. Serving and AI: the MCP server

**The code** ([`mcp_server/server.py`](../mcp_server/server.py)): an MCP server exposes read-only tools over the
marts (query, list tables, run the checks, run dbt), on DuckDB or Snowflake, so an AI assistant can answer questions
from the data product without write access.

**The same on Databricks:** the same server, pointed at a SQL warehouse; or a Genie space on the marts, with the
metric view as its vocabulary.

---

## The map, side by side

| Layer | Phase 1: this repository (Snowflake) | Phase 2: Databricks | Stays the same |
|---|---|---|---|
| Storage | Snowflake tables (micro-partitions); DuckDB locally | Delta tables in Unity Catalog | The raw → staging → marts layers |
| Compute | Virtual warehouse, XSMALL, auto-suspend | Serverless SQL warehouse and serverless jobs | Pay only while it runs |
| Ingestion | dlt: incremental cursor, merge, schema contract | dlt (Databricks destination), a PySpark notebook task + MERGE, Auto Loader + MERGE, or Lakeflow Connect | Idempotent, incremental loads |
| Transformation | dbt on Snowflake | dbt on Databricks, or Lakeflow Declarative Pipelines | The models and the grain |
| Tests | dbt data tests, unit tests, model contract | The same dbt tests, or pipeline expectations | What "correct" means |
| History | dbt snapshot (SCD2) | dbt snapshot, or AUTO CDC SCD TYPE 2 | The fund's history |
| Semantic layer | One dbt model of measures | The same model, or a metric view | Each KPI defined once |
| Migration | sqlglot to Snowflake SQL + parity | sqlglot to Databricks SQL + the same parity | The proof that the numbers match |
| Orchestration | Airflow DAG | Lakeflow Job in a bundle, or Airflow triggering it | The dependency graph |
| Access | Access and functional roles, future grants | Unity Catalog grants to groups, inherited | Least privilege, as code |
| Cost guard | Resource monitor | Budgets, compute tags, billing system tables | A cap and an alert |
| Platform as code | Terraform (Snowflake provider) | Terraform (Databricks provider) + bundles | Nothing created by hand |
| Delivery | Docker image, Kubernetes CronJob, CI | Bundle deploy from CI, serverless jobs | Every change goes through CI |
| Recovery | Time Travel, zero-copy clone | Delta time travel, shallow and deep clone | Undo a bad load |
| Sharing | Secure Data Sharing | Delta Sharing | Share without copying |
| AI | MCP server on the marts | The MCP server, or a Genie space | Read-only access to a governed product |
