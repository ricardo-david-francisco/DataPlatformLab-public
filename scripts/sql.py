"""Query the warehouse: ./run.sh sql "select ..."   or, written in Snowflake SQL:   ./run.sh sql --snowflake "..."

With --snowflake the query is Snowflake SQL (QUALIFY, IFF, DATEADD, PARSE_JSON(...):path...), translated to DuckDB by
sqlglot and run locally on the same data: write Snowflake syntax without an account.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    snowflake = "--snowflake" in argv
    query = " ".join(a for a in argv if a != "--snowflake").strip()
    if not query:
        print(__doc__)
        return 2
    if snowflake:
        import sqlglot
        query = ";\n".join(sqlglot.transpile(query, read="snowflake", write="duckdb"))
        print(f"-- as DuckDB: {query}\n")
    con = duckdb.connect(os.environ.get("DPL_WAREHOUSE", str(ROOT / "warehouse/lab.duckdb")), read_only=True)
    cur = con.execute(query)
    cols = [d[0] for d in cur.description or []]
    rows = cur.fetchmany(50)
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c)) for i, c in enumerate(cols)]
    print("  ".join(str(c).ljust(w) for c, w in zip(cols, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths, strict=True)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
