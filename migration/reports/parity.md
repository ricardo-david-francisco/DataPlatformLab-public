# Parity report: legacy SQL Server warehouse vs the new platform

## Positions (dw.FactPositions vs marts.fct_positions_daily): 225 days compared
- Days with a different count or total: **222**
- Rows that differ: **7564**, of which **7564 explained** and **0 unexplained**
- **Explanation:** every differing row is a fund and security with an **amended trade**. The legacy procedure keeps the first booking only (`t.[Version] = 1`); the new model applies the latest amendment (`int_trades_latest`). The new numbers are the right ones: they match the custodian.

| fund | isin | day | legacy qty | new qty |
|---|---|---|---|---|
| BOR-GQE | GB0009895292 | 2026-08-11 | 1,040 | 1,070 |
| BOR-GQE | GB00B10RZP78 | 2026-08-11 | 9,810 | 9,830 |
| BOR-GQE | US5949181045 | 2026-08-11 | 755 | 765 |
| BOR-GQE | US67066G1040 | 2026-08-11 | 2,050 | 2,060 |
| BOR-GQE | US4781601046 | 2026-08-11 | 1,670 | 1,680 |
| BOR-ECV | SYNCB000001 | 2026-08-11 | 13,100 | 13,110 |
| BOR-ECV | SYNCB000002 | 2026-08-11 | 9,800 | 9,810 |
| BOR-ECV | SYNCB000003 | 2026-08-11 | 30,600 | 30,630 |

## Fees (dw.FactFeeAccrual vs marts.fct_fee_accrual): 165 share-class months compared
- Months that differ: **111**; largest difference **0.04 EUR**; over the 0.10 EUR tolerance: **0**
- **Explanation:** rounding. The legacy procedure rounds every day's fee to the cent and sums the rounded amounts; the new model sums the exact daily accruals and rounds once per month. Finance agrees the tolerance.

| share class | month | legacy | new | difference |
|---|---|---|---|---|
| BOR-CLT-A-EUR | 2026-02 | 876.32 | 876.28 | -0.04 |
| BOR-GQE-I-EUR | 2026-02 | 491.00 | 491.03 | +0.03 |
| BOR-BAL-D-EUR | 2026-08 | 1,765.27 | 1,765.30 | +0.03 |
| BOR-ECV-A-EUR | 2026-05 | 2,078.30 | 2,078.33 | +0.03 |
| BOR-CLT-D-EUR | 2026-02 | 438.11 | 438.14 | +0.03 |

## Verdict
**PASS: every difference is explained.**
