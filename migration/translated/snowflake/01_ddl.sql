-- Translated from migration/legacy/01_ddl.sql by sqlglot (T-SQL -> Snowflake). Reviewed by a human before use.

/* The legacy SQL Server warehouse's reporting tables (schema dw), as they were before the migration. */
CREATE TABLE dw.FactPositions (
  FundCode VARCHAR(20) NOT NULL,
  ISIN CHAR(12) NOT NULL,
  PositionDate DATE NOT NULL,
  Quantity DECIMAL(18, 4) NOT NULL
);

CREATE TABLE dw.FactFeeAccrual (
  ShareClassCode VARCHAR(30) NOT NULL,
  AccrualDate DATE NOT NULL,
  FeeAmountEUR DECIMAL(18, 2) NOT NULL
);
