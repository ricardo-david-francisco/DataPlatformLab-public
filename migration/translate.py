"""Translate the legacy T-SQL (migration/legacy/*.sql) into Snowflake SQL, the first draft of the migration.

    python migration/translate.py            # writes migration/translated/snowflake/*.sql and prints what changed

sqlglot parses SQL Server's dialect and writes Snowflake's: ISNULL -> COALESCE, CONVERT(DATE, x) -> CAST,
DATEDIFF(DAY, a, b) -> DATEDIFF(DAY, a, b), NVARCHAR -> VARCHAR, [brackets] -> plain names.

The brackets are a real trap. [FundCode] is a quoted identifier; kept quoted it becomes "FundCode" in Snowflake,
which is case-sensitive, and every query then has to quote it forever. Snowflake stores unquoted names in upper
case, so the translation drops the quotes on purpose. A human still reviews every translated file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import sqlglot
from sqlglot import exp

HERE = Path(__file__).resolve().parent
LEGACY = HERE / "legacy"


def unquote(tree: exp.Expression) -> exp.Expression:
    for ident in tree.find_all(exp.Identifier):
        ident.set("quoted", False)
    return tree


def translate(sql: str, dialect: str = "snowflake", pretty: bool = True) -> list[str]:
    """T-SQL statements -> the same statements in another dialect (snowflake, or duckdb to run them locally)."""
    return [unquote(tree).sql(dialect=dialect, pretty=pretty)
            for tree in sqlglot.parse(sql, read="tsql") if tree is not None]


def main() -> int:
    out = HERE / "translated" / "snowflake"
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(LEGACY.glob("*.sql")):
        statements = translate(path.read_text(encoding="utf-8"))
        target = out / path.name
        target.write_text(f"-- Translated from migration/legacy/{path.name} by sqlglot (T-SQL -> Snowflake). "
                          "Reviewed by a human before use.\n\n" + ";\n\n".join(statements) + ";\n", encoding="utf-8")
        print(f"{path.name}: {len(statements)} statement(s) -> {target.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
