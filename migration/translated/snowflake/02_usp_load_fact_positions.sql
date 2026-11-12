-- Translated from migration/legacy/02_usp_load_fact_positions.sql by sqlglot (T-SQL -> Snowflake). Reviewed by a human before use.

/* dbo.usp_LoadFactPositions: the body of the legacy nightly procedure (SQL Agent job "DW - Positions", 02:00). */
/* Positions = opening quantity + every booked trade up to the date, for each fund, security and business day. */
INSERT INTO dw.FactPositions (
  FundCode,
  ISIN,
  PositionDate,
  Quantity
)
SELECT
  o.FundCode,
  o.ISIN,
  c.BusinessDate,
  COALESCE(o.Quantity, 0) + COALESCE(
    (
      SELECT
        SUM(CASE WHEN t.Side = 'BUY' THEN t.Quantity ELSE -t.Quantity END)
      FROM stg.CustodianTrades AS t
      WHERE
        t.FundCode = o.FundCode
        AND t.ISIN = o.ISIN
        AND t.Version = 1
        AND CAST(t.TradeDate AS DATE) <= c.BusinessDate
    ),
    0
  )
FROM stg.OpeningPositions AS o
CROSS JOIN stg.Calendar AS c;
