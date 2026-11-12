"""The migration's translator: T-SQL in, Snowflake (and DuckDB) SQL out."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "migration"))
from translate import translate  # noqa: E402


def test_tsql_functions_become_snowflake():
    sql = translate("SELECT ISNULL([Quantity], 0), CONVERT(DATE, [TradeDate]) FROM [stg].[CustodianTrades]")[0]
    assert "COALESCE(Quantity, 0)" in sql
    assert "CAST(TradeDate AS DATE)" in sql
    assert "[" not in sql and '"' not in sql      # no brackets, no quoted (case-sensitive) names


def test_every_legacy_file_translates():
    legacy = Path(__file__).resolve().parents[1] / "migration" / "legacy"
    for path in legacy.glob("*.sql"):
        assert translate(path.read_text(encoding="utf-8")), path.name
