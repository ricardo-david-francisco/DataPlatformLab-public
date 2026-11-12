"""post_trade_daily: the post-trade domain's nightly run, every business day at 02:00 UTC.

    five dlt loads (in parallel) -> dbt snapshot -> dbt build (models + tests) -> migration parity -> publish

Each task is idempotent (dlt merges on business keys, dbt rebuilds), so a retry or a re-run of a day is safe.
A failed task retries twice, then calls notify_failure: the team that built it is the team that's alerted.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

REPO = os.environ.get("DPL_HOME", str(Path(__file__).resolve().parents[2]))
PY = os.environ.get("DPL_PYTHON", "python")
DBT = os.environ.get("DPL_DBT", "dbt")
ENV = {"DBT_PROFILES_DIR": f"{REPO}/transform", "PATH": os.environ.get("PATH", "")}


def notify_failure(context) -> None:
    """The owning team is alerted: in production this posts to the team's channel and opens a ticket."""
    ti = context["task_instance"]
    print(f"ALERT post-trade: {ti.dag_id}.{ti.task_id} failed for {context.get('logical_date')}. "
          "Runbook: docs/RUNBOOK.md")


default_args = {
    "owner": "post-trade-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="post_trade_daily",
    schedule="0 2 * * 1-5",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["post-trade", "dlt", "dbt"],
    doc_md=__doc__,
) as dag:
    loads = [
        BashOperator(task_id=f"load_{source}", env=ENV, append_env=True,
                     bash_command=f"cd {REPO} && {PY} ingestion/pipelines.py --only {source}")
        for source in ("ecb", "reference", "market", "custody", "transfer_agent")
    ]
    snapshot = BashOperator(task_id="dbt_snapshot", env=ENV, append_env=True,
                            bash_command=f"cd {REPO}/transform && {DBT} snapshot")
    build = BashOperator(task_id="dbt_build", env=ENV, append_env=True,
                         bash_command=f"cd {REPO}/transform && {DBT} build --exclude resource_type:snapshot")
    parity = BashOperator(task_id="migration_parity", env=ENV, append_env=True,
                          bash_command=f"cd {REPO} && {PY} migration/parity.py")
    publish = BashOperator(task_id="publish_positions_ready",
                           bash_command="echo 'fct_positions_daily is ready for {{ ds }}'")

    loads >> snapshot >> build >> parity >> publish
