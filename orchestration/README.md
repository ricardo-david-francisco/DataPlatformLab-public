# Orchestration: Airflow

`dags/post_trade_daily.py` runs the domain every business day at 02:00 UTC: the five dlt loads in
parallel, then `dbt snapshot`, `dbt build` (models and their tests: a failing test stops the run), the migration
parity check, and a "ready" signal for the consumers.

Try it without a scheduler:

```bash
export AIRFLOW_HOME=/tmp/airflow DPL_PYTHON=$(which python) DPL_DBT=$(which dbt)
airflow db migrate
AIRFLOW__CORE__DAGS_FOLDER=$PWD/orchestration/dags airflow dags test post_trade_daily 2026-11-12
```
