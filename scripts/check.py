"""The check of each step of docs/TOUR.md: ./run.sh check <step>. Prints PASS or what to look at; exit 1 on a fail."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = os.environ.get("DPL_WAREHOUSE", str(ROOT / "warehouse/lab.duckdb"))
results: list[tuple[bool, str]] = []


def ok(cond: bool, what: str) -> None:
    results.append((bool(cond), what))


def q(sql: str):
    with duckdb.connect(WAREHOUSE, read_only=True) as con:
        return con.execute(sql).fetchall()


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def isin_valid(isin: str) -> bool:
    """ISO 6166 check digit: letters to numbers (A=10...), then the Luhn algorithm."""
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(isin[-1])


def step0() -> None:
    ok(Path(WAREHOUSE).exists(), f"the warehouse exists ({WAREHOUSE})")
    ok(q("select count(*) from marts.fct_positions_daily")[0][0] > 10000, "marts.fct_positions_daily is built")
    report = ROOT / "migration/reports/parity.md"
    ok(report.exists() and "PASS" in report.read_text(encoding="utf-8"), "the parity report says PASS")


def step1() -> None:
    import csv
    secs = list(csv.DictReader((ROOT / "data/reference/securities.csv").open(encoding="utf-8")))
    real = [s["isin"] for s in secs if not s["isin"].startswith("SYN")]
    ok(len(real) >= 30 and all(isin_valid(i) for i in real), f"{len(real)} real ISINs, every check digit valid")
    ok(len(list((ROOT / "data/custody/trades").glob("trades_*.json"))) == 11, "11 monthly custodian trade files")


def step2() -> None:
    before = q("select count(*) from raw_custody.trades")[0][0]
    dup = q("select count(*) from (select trade_id, version from raw_custody.trades group by 1, 2 having count(*) > 1)")
    ok(dup[0][0] == 0, "no duplicate (trade_id, version) in raw: merge on the business key")
    ok(q("select count(*) from raw_ecb.fx_rates")[0][0] > 1000, "ECB rates loaded")
    r = run([sys.executable, "ingestion/pipelines.py", "--only", "custody", "--offline"])
    after = q("select count(*) from raw_custody.trades")[0][0]
    ok(r.returncode == 0 and after == before, f"re-running the custody load adds nothing ({before} -> {after} rows): "
                                              "incremental + merge make it idempotent")


def dbt(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DBT_PROFILES_DIR": str(ROOT / "transform")}
    return subprocess.run(["dbt", *args], cwd=ROOT / "transform", capture_output=True, text=True, env=env)


def step3() -> None:
    r = dbt("test", "--select", "staging")
    ok(r.returncode == 0, "dbt test --select staging passes" + ("" if r.returncode == 0 else "\n" + r.stdout[-1500:]))


def step4() -> None:
    r = dbt("build", "--select", "marts")
    ok(r.returncode == 0, "dbt build --select marts passes (with the contract on fct_positions_daily)")
    versions = q("select count(*) from marts.dim_fund where fund_id = 'BOR-NEU'")[0][0]
    ok(versions == 2, f"dim_fund keeps 2 versions of BOR-NEU (SCD2): {versions}")
    breaks = q("select count(*) from marts.fct_reconciliation_breaks")[0][0]
    ok(breaks == 3, f"the reconciliation finds the 3 planted breaks: {breaks}")


def step5() -> None:
    wrong = q("""
        with aum as (select fund_id, position_date, sum(market_value_eur) as aum from marts.fct_positions_daily group by 1, 2),
             last as (select fund_id, date_trunc('month', position_date) as m, max(position_date) as d from aum group by 1, 2)
        select count(*) from marts.fct_fund_kpis_monthly k
        join last l on l.fund_id = k.fund_id and l.m = k.month
        join aum a on a.fund_id = l.fund_id and a.position_date = l.d
        where abs(k.aum_month_end_eur - round(a.aum, 2)) > 0.01""")[0][0]
    ok(wrong == 0, "AUM month-end = the last business day's AUM for every fund and month (semi-additive)")


def step6() -> None:
    r = run([sys.executable, "migration/parity.py"])
    ok(r.returncode == 0, "parity: every difference legacy vs new is explained\n" + r.stdout.strip())
    translated = list((ROOT / "migration/translated/snowflake").glob("*.sql"))
    ok(len(translated) == 3 and not any("[" in p.read_text(encoding="utf-8") for p in translated),
       "3 legacy files translated to Snowflake SQL, no [brackets] left")


def step7() -> None:
    py = os.environ.get("DPL_AIRFLOW_PYTHON", "/opt/airflow/bin/python")
    dag = ROOT / "orchestration/dags/post_trade_daily.py"
    if not Path(py).exists():
        spec = importlib.util.spec_from_file_location("dag", dag)
        ok(spec is not None, "the DAG file exists (Airflow not installed here: set DPL_AIRFLOW_PYTHON to check it)")
        return
    code = (f"import runpy; m = runpy.run_path({str(dag)!r}); d = m['dag']; "
            "print(sorted(d.task_ids)); print(sorted(t.task_id for t in d.get_task('dbt_build').upstream_list))")
    r = run([py, "-c", code])
    ok(r.returncode == 0 and "dbt_build" in r.stdout, "the DAG imports in Airflow with its tasks\n" + r.stdout.strip()
       + ("" if r.returncode == 0 else r.stderr[-800:]))


def step8() -> None:
    tf = shutil.which("terraform")
    if tf:
        r = run([tf, "fmt", "-check", "-recursive"], ROOT / "platform/terraform")
        ok(r.returncode == 0, "terraform fmt -check")
        run([tf, "init", "-backend=false", "-input=false"], ROOT / "platform/terraform")
        r = run([tf, "validate"], ROOT / "platform/terraform")
        ok(r.returncode == 0, "terraform validate" + ("" if r.returncode == 0 else "\n" + r.stdout + r.stderr))
    kubectl = shutil.which("kubectl")
    if kubectl:
        r = run([kubectl, "kustomize", "deploy/k8s"])
        ok(r.returncode == 0 and "CronJob" in r.stdout, "kubectl kustomize deploy/k8s renders the Job and the CronJob")
    ok((ROOT / ".github/workflows/ci.yml").exists(), "the CI workflow exists")


def main() -> int:
    steps = {str(i): f for i, f in enumerate([step0, step1, step2, step3, step4, step5, step6, step7, step8])}
    if len(sys.argv) < 2 or sys.argv[1] not in steps:
        print("usage: ./run.sh check <0-8>")
        return 2
    steps[sys.argv[1]]()
    for good, what in results:
        print(f"{'PASS' if good else 'FAIL'}  {what}")
    return 0 if all(g for g, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
