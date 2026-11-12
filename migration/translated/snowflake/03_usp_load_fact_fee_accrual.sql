-- Translated from migration/legacy/03_usp_load_fact_fee_accrual.sql by sqlglot (T-SQL -> Snowflake). Reviewed by a human before use.

/* dbo.usp_LoadFactFeeAccrual: the body of the legacy nightly procedure (SQL Agent job "DW - Fees", 03:00). */
/* Daily management fee per share class = fund AUM x the class's share x yearly rate / 365 x calendar days since the */
/* previous valuation day. */
INSERT INTO dw.FactFeeAccrual (
  ShareClassCode,
  AccrualDate,
  FeeAmountEUR
)
SELECT
  sc.ShareClassCode,
  a.ValuationDate,
  ROUND(
    a.FundAUMEUR * sc.AUMWeight * sc.MgmtFeeRate / 365.0 * DATEDIFF(
      DAY,
      CAST(COALESCE(a.PreviousValuationDate, DATEADD(DAY, -1, a.ValuationDate)) AS TIMESTAMP),
      CAST(a.ValuationDate AS TIMESTAMP)
    ),
    2
  )
FROM stg.FundAUM AS a
JOIN stg.ShareClasses AS sc
  ON sc.FundCode = a.FundCode;
