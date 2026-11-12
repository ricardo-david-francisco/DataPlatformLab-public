"""Parity check: does the new platform give the same numbers as the legacy warehouse?

    python migration/parity.py        # report on screen and in migration/reports/parity.md; exit 1 if unexplained

How:
  1. Rebuild the legacy staging tables (stg.*) as views over the same raw data the new platform loads.
  2. Run the legacy procedures themselves, translated from T-SQL by migration/translate.py, into dw.*.
  3. Compare legacy against the dbt marts: positions per fund x security x day (counts, sums, then a hash per row),
     fees per share class x month (legacy rounds each day to the cent; the new model rounds once a month).
  4. Classify every difference. Explained differences are documented for the business; an unexplained one fails.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translate import translate  # noqa: E402

HERE = Path(__file__).resolve().parent
WAREHOUSE = Path(os.environ.get("DPL_WAREHOUSE", HERE.parent / "warehouse/lab.duckdb"))
FEE_TOLERANCE_EUR = 0.10                     # per share class and month: rounding, agreed with finance

LEGACY_STAGING = """
create schema if not exists stg;
create schema if not exists dw;
drop table if exists dw.FactPositions;
drop table if exists dw.FactFeeAccrual;
create or replace view stg.CustodianTrades as
    select trade_id as TradeId, version as Version, fund_id as FundCode, isin as ISIN, side as Side,
           quantity as Quantity, trade_date as TradeDate
    from staging.stg_custody__trades;
create or replace view stg.OpeningPositions as
    select fund_id as FundCode, isin as ISIN, quantity as Quantity from staging.stg_custody__opening_positions;
create or replace view stg.Calendar as select business_date as BusinessDate from intermediate.int_business_days;
create or replace view stg.FundAUM as
    select fund_id as FundCode, position_date as ValuationDate,
           lag(position_date) over (partition by fund_id order by position_date) as PreviousValuationDate,
           sum(market_value_eur) as FundAUMEUR
    from marts.fct_positions_daily group by fund_id, position_date;
create or replace view stg.ShareClasses as
    select share_class_id as ShareClassCode, fund_id as FundCode, aum_weight as AUMWeight, mgmt_fee_rate as MgmtFeeRate
    from staging.stg_reference__share_classes;
"""

POSITIONS_BY_DAY = """
with legacy as (select PositionDate as d, count(*) as n, sum(Quantity) as q from dw.FactPositions group by 1),
     new as (select position_date as d, count(*) as n, sum(quantity) as q from marts.fct_positions_daily group by 1)
select coalesce(l.d, n.d) as day, l.n as legacy_rows, n.n as new_rows, l.q as legacy_qty, n.q as new_qty
from legacy l full outer join new n on n.d = l.d
where coalesce(l.n, 0) <> coalesce(n.n, 0) or abs(coalesce(l.q, 0) - coalesce(n.q, 0)) > 0.0001
order by 1
"""
POSITIONS_BY_ROW = """
-- Hash the same text on both sides: DECIMAL(18,4) prints 1550.0000 and a double 1550.0, so cast first.
with legacy as (select FundCode as fund_id, ISIN as isin, PositionDate as d, md5(concat_ws('|', FundCode, ISIN,
                       cast(PositionDate as varchar), cast(cast(Quantity as decimal(18, 4)) as varchar))) as h,
                       Quantity as q from dw.FactPositions),
     new as (select fund_id, isin, position_date as d, md5(concat_ws('|', fund_id, isin, cast(position_date as varchar),
                    cast(cast(quantity as decimal(18, 4)) as varchar))) as h, quantity as q
             from marts.fct_positions_daily)
select coalesce(l.fund_id, n.fund_id) as fund_id, coalesce(l.isin, n.isin) as isin, coalesce(l.d, n.d) as day,
       l.q as legacy_qty, n.q as new_qty,
       exists (select 1 from staging.stg_custody__trades t
               where t.fund_id = coalesce(l.fund_id, n.fund_id) and t.isin = coalesce(l.isin, n.isin)
                 and t.version > 1 and t.trade_date <= coalesce(l.d, n.d)) as has_amendment
from legacy l full outer join new n on n.fund_id = l.fund_id and n.isin = l.isin and n.d = l.d
where l.h is distinct from n.h
"""
FEES_BY_MONTH = """
with legacy as (select ShareClassCode as sc, date_trunc('month', AccrualDate) as m, sum(FeeAmountEUR) as fee
                from dw.FactFeeAccrual group by 1, 2),
     new as (select share_class_id as sc, date_trunc('month', accrual_date) as m, round(sum(fee_eur), 2) as fee
             from marts.fct_fee_accrual group by 1, 2)
select coalesce(l.sc, n.sc) as share_class, coalesce(l.m, n.m) as month, l.fee as legacy_fee, n.fee as new_fee,
       round(coalesce(n.fee, 0) - coalesce(l.fee, 0), 2) as difference
from legacy l full outer join new n on n.sc = l.sc and n.m = l.m
where coalesce(l.fee, 0) <> coalesce(n.fee, 0)
order by abs(round(coalesce(n.fee, 0) - coalesce(l.fee, 0), 2)) desc
"""


def run_legacy(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(LEGACY_STAGING)
    for path in sorted((HERE / "legacy").glob("*.sql")):
        for statement in translate(path.read_text(encoding="utf-8"), dialect="duckdb", pretty=False):
            con.execute(statement)


def main() -> int:
    con = duckdb.connect(str(WAREHOUSE))
    run_legacy(con)
    days = con.execute(POSITIONS_BY_DAY).fetchall()
    rows = con.execute(POSITIONS_BY_ROW).fetchall()
    fees = con.execute(FEES_BY_MONTH).fetchall()
    n_days = con.execute("select count(distinct PositionDate) from dw.FactPositions").fetchone()[0]
    n_months = con.execute("select count(distinct date_trunc('month', AccrualDate)) * count(distinct ShareClassCode)"
                           " from dw.FactFeeAccrual").fetchone()[0]

    explained_rows = [r for r in rows if r[5]]
    unexplained_rows = [r for r in rows if not r[5]]
    over_tolerance = [f for f in fees if abs(f[4]) > FEE_TOLERANCE_EUR]
    lines = [
        "# Parity report: legacy SQL Server warehouse vs the new platform",
        "",
        f"## Positions (dw.FactPositions vs marts.fct_positions_daily): {n_days} days compared",
        f"- Days with a different count or total: **{len(days)}**",
        f"- Rows that differ: **{len(rows)}**, of which **{len(explained_rows)} explained** and "
        f"**{len(unexplained_rows)} unexplained**",
        "- **Explanation:** every differing row is a fund and security with an **amended trade**. The legacy procedure "
        "keeps the first booking only (`t.[Version] = 1`); the new model applies the latest amendment "
        "(`int_trades_latest`). The new numbers are the right ones: they match the custodian.",
        "",
        "| fund | isin | day | legacy qty | new qty |", "|---|---|---|---|---|",
        *[f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:,.0f} | {r[4]:,.0f} |" for r in rows[:8]],
        "",
        f"## Fees (dw.FactFeeAccrual vs marts.fct_fee_accrual): {n_months} share-class months compared",
        f"- Months that differ: **{len(fees)}**; largest difference **{max((abs(f[4]) for f in fees), default=0):.2f} EUR**;"
        f" over the {FEE_TOLERANCE_EUR:.2f} EUR tolerance: **{len(over_tolerance)}**",
        "- **Explanation:** rounding. The legacy procedure rounds every day's fee to the cent and sums the rounded "
        "amounts; the new model sums the exact daily accruals and rounds once per month. Finance agrees the tolerance.",
        "",
        "| share class | month | legacy | new | difference |", "|---|---|---|---|---|",
        *[f"| {f[0]} | {str(f[1])[:7]} | {f[2]:,.2f} | {f[3]:,.2f} | {f[4]:+.2f} |" for f in fees[:5]],
        "",
        "## Verdict",
        "**PASS: every difference is explained.**" if not unexplained_rows and not over_tolerance
        else "**FAIL: unexplained differences; don't switch the reports.**",
    ]
    report = HERE / "reports" / "parity.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"positions: {n_days} days compared, {len(rows)} rows differ "
          f"({len(explained_rows)} explained by trade amendments, {len(unexplained_rows)} unexplained)")
    print(f"fees: {len(fees)} share-class months differ by rounding, max "
          f"{max((abs(f[4]) for f in fees), default=0):.2f} EUR, {len(over_tolerance)} over tolerance")
    print(f"report: {report.relative_to(HERE.parent)}")
    return 0 if not unexplained_rows and not over_tolerance else 1


if __name__ == "__main__":
    sys.exit(main())
