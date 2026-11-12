"""What's in the warehouse after a run: one screen, the numbers a reviewer would ask about."""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = os.environ.get("DPL_WAREHOUSE", str(ROOT / "warehouse/lab.duckdb"))

QUERIES = [
    ("Raw layer (dlt)", """
        select schema_name || '.' || table_name, estimated_size from duckdb_tables()
        where schema_name like 'raw_%' and schema_name not like '%_staging' and table_name not like '_dlt%' order by 1"""),
    ("Marts (dbt)", """
        select schema_name || '.' || table_name, estimated_size from duckdb_tables()
        where schema_name in ('marts', 'snapshots') order by 1"""),
    ("Latest ECB rates loaded (units per EUR)", """
        select currency, max(rate_date), arg_max(units_per_eur, rate_date) from staging.stg_ecb__fx_rates
        group by currency order by currency"""),
    ("Reconciliation breaks vs the custodian (planted: 3)", """
        select fund_id, isin, position_date, our_quantity, custodian_quantity, difference
        from marts.fct_reconciliation_breaks order by fund_id"""),
    ("Settlement fails", "select settlement_status, count(*) from marts.fct_settlement_fails group by 1"),
    ("dim_fund (SCD2): the fund whose attributes changed on 11 Nov", """
        select fund_id, portfolio_manager, risk_class, cast(valid_from as date), cast(valid_to as date), is_current
        from marts.dim_fund where fund_id = 'BOR-NEU' order by valid_from"""),
    ("Semantic KPIs, October 2026 (AUM month-end is semi-additive)", """
        select fund_id, month_end_date, aum_month_end_eur, net_flows_eur, fee_income_eur
        from marts.fct_fund_kpis_monthly where month = date '2026-10-01' order by fund_id"""),
]


def main() -> None:
    con = duckdb.connect(WAREHOUSE, read_only=True)
    for title, sql in QUERIES:
        print(f"\n{title}")
        for row in con.execute(sql).fetchall():
            print("   " + "  ".join(f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row))


if __name__ == "__main__":
    main()
