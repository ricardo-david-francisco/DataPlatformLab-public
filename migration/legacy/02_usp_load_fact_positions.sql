-- dbo.usp_LoadFactPositions: the body of the legacy nightly procedure (SQL Agent job "DW - Positions", 02:00).
-- Positions = opening quantity + every booked trade up to the date, for each fund, security and business day.
INSERT INTO [dw].[FactPositions] ([FundCode], [ISIN], [PositionDate], [Quantity])
SELECT  o.[FundCode],
        o.[ISIN],
        c.[BusinessDate],
        ISNULL(o.[Quantity], 0)
          + ISNULL((SELECT SUM(CASE WHEN t.[Side] = 'BUY' THEN t.[Quantity] ELSE -t.[Quantity] END)
                    FROM   [stg].[CustodianTrades] t
                    WHERE  t.[FundCode] = o.[FundCode]
                      AND  t.[ISIN] = o.[ISIN]
                      AND  t.[Version] = 1
                      AND  CONVERT(DATE, t.[TradeDate]) <= c.[BusinessDate]), 0)
FROM    [stg].[OpeningPositions] o
CROSS JOIN [stg].[Calendar] c;
