"""DataPlatformLab's MCP server: an AI assistant can query the data product, run the checks, build with dbt and read
the code, without a shell. Read-only on the data (queries open the warehouse read-only); the actions it can run are a
fixed list (checks, dbt commands, the pipeline).

`query` and `tables` read the local DuckDB warehouse, or with target="snowflake" the Snowflake account of
docs/SNOWFLAKE.md: key-pair sign-in from ~/.snowflake/dpl.env, a read-only role, one SELECT, SHOW or DESCRIBE at a time.

    python mcp_server/server.py   # stdio; packaged for Claude Desktop as an .mcpb (mcp_server/bundle/)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import duckdb
from mcp.server.mcpserver import MCPServer

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = os.environ.get("DPL_WAREHOUSE", str(ROOT / "warehouse/lab.duckdb"))
MAX_ROWS = 200
DBT_COMMANDS = {"build", "test", "run", "compile", "ls", "snapshot", "parse"}
Target = Literal["local", "snowflake"]

# The Snowflake target: the settings file scripts/snowflake_env.sh reads, and a role that can only read the marts.
SNOWFLAKE_ENV = Path(os.environ.get("DPL_SNOWFLAKE_ENV") or Path.home() / ".snowflake/dpl.env")
SNOWFLAKE_ROLE = os.environ.get("DPL_SNOWFLAKE_ROLE") or "DPL_FINANCE_ANALYST"
READ_ONLY_COMMANDS = {"SHOW", "DESCRIBE", "DESC"}

server = MCPServer(
    name="dataplatformlab",
    title="DataPlatformLab",
    instructions=(
        "A post-trade data platform (dlt, dbt, DuckDB or Snowflake). Start with `tour` to see the steps, `tables` "
        "for what exists, `query` to read data (Snowflake SQL is accepted), `check` to verify a step of the tour. "
        "`tables` and `query` read the local DuckDB warehouse; target='snowflake' reads the Snowflake account instead "
        "(read-only, the marts in DPL.MARTS). "
        "The user writes the code; review it and explain, don't rewrite it unless asked."
    ),
)


def _run(cmd: list[str], cwd: Path = ROOT, timeout: int = 600) -> str:
    env = {**os.environ, "DBT_PROFILES_DIR": str(ROOT / "transform"), "DPL_WAREHOUSE": WAREHOUSE}
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
    return f"exit {r.returncode}\n{out[-6000:]}"


def _table(cols: list[str], rows: list[tuple]) -> str:
    more = f"\n-- first {MAX_ROWS} rows shown" if len(rows) > MAX_ROWS else ""
    return "\n".join([" | ".join(cols)] + [" | ".join(str(v) for v in r) for r in rows[:MAX_ROWS]]) + more


def _snowflake_settings() -> dict[str, str]:
    """The KEY=value lines of ~/.snowflake/dpl.env (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH)."""
    if not SNOWFLAKE_ENV.is_file():
        raise FileNotFoundError(f"no Snowflake settings: create {SNOWFLAKE_ENV} (docs/SNOWFLAKE.md)")
    settings = {}
    for line in SNOWFLAKE_ENV.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and not key.startswith("#"):
            settings[key.strip()] = value.strip().strip("'\"")
    return settings


def _read_only(sql: str) -> str:
    """Why the statement may not run on Snowflake, or "" when it is one SELECT, SHOW or DESCRIBE."""
    import sqlglot
    from sqlglot import exp

    logging.getLogger("sqlglot").setLevel(logging.ERROR)  # SHOW variants it doesn't model are parsed as commands
    try:
        statements = [s for s in sqlglot.parse(sql, read="snowflake") if s is not None]
    except sqlglot.errors.SqlglotError as e:
        return f"could not parse the query: {str(e).splitlines()[0]}"
    if len(statements) != 1:
        return "one statement at a time"
    stmt = statements[0]
    if isinstance(stmt, exp.Query | exp.Show | exp.Describe):
        return ""
    if isinstance(stmt, exp.Command) and stmt.name.upper() in READ_ONLY_COMMANDS:
        return ""
    return f"read-only: SELECT, SHOW or DESCRIBE only, not {stmt.key.upper()}"


def _snowflake(sql: str) -> tuple[list[str], list[tuple]]:
    """Run one statement on Snowflake as SNOWFLAKE_ROLE, and nothing else: the user's other roles stay out."""
    try:
        import snowflake.connector
    except ImportError:
        raise RuntimeError("the Snowflake target needs: pip install -r requirements-snowflake.txt") from None

    logging.getLogger("snowflake.connector").setLevel(logging.ERROR)
    s = _snowflake_settings()
    try:
        with snowflake.connector.connect(
            account=s["SNOWFLAKE_ACCOUNT"],
            user=s["SNOWFLAKE_USER"],
            authenticator="SNOWFLAKE_JWT",
            private_key_file=s["SNOWFLAKE_PRIVATE_KEY_PATH"],
            role=SNOWFLAKE_ROLE,
            warehouse=s.get("SNOWFLAKE_WAREHOUSE", "DPL_WH"),
            database=s.get("SNOWFLAKE_DATABASE", "DPL"),
            login_timeout=30,
            session_parameters={
                "QUERY_TAG": "dataplatformlab-mcp",
                "STATEMENT_TIMEOUT_IN_SECONDS": 120,  # a runaway query costs at most two warehouse minutes
                "ROWS_PER_RESULTSET": MAX_ROWS + 1,  # the row limit, applied by Snowflake
            },
        ) as con, con.cursor() as cur:
            # A user's default secondary roles are often ALL (ACCOUNTADMIN included): only the primary role may act.
            cur.execute("use secondary roles none")
            cur.execute(sql)
            return [d[0] for d in cur.description or []], cur.fetchmany(MAX_ROWS + 1)
    except snowflake.connector.errors.Error as e:
        msg = str(e)
        for secret in (s.get("SNOWFLAKE_USER"), s.get("SNOWFLAKE_USER_NAME")):
            msg = msg.replace(secret, "<user>") if secret else msg
        raise RuntimeError(f"Snowflake: {msg}") from None


@server.tool(description="The steps of the tour (docs/TOUR.md): what each one covers and how it's checked.")
def tour() -> str:
    return (ROOT / "docs/TOUR.md").read_text(encoding="utf-8")


@server.tool(description="Run the check of one tour step (0-8) and return PASS/FAIL lines.")
def check(step: int) -> str:
    if not 0 <= step <= 8:
        return "step must be 0-8"
    return _run([sys.executable, "scripts/check.py", str(step)])


@server.tool(description="List the warehouse's schemas and tables with their row counts. target: 'local' (DuckDB, "
                         "the default) or 'snowflake' (what the read-only role can see in database DPL).")
def tables(target: Target = "local") -> str:
    if target == "snowflake":
        try:
            _, rows = _snowflake("select table_schema, table_name, iff(table_type = 'VIEW', 'view', row_count::varchar) "
                                 "from information_schema.tables where table_schema <> 'INFORMATION_SCHEMA' "
                                 "and not endswith(table_schema, '_STAGING') order by 1, 2")
        except (FileNotFoundError, RuntimeError) as e:
            return str(e)
    else:
        with duckdb.connect(WAREHOUSE, read_only=True) as con:
            rows = con.execute("select schema_name, table_name, estimated_size from duckdb_tables() "
                               "where schema_name not like '%_staging' order by 1, 2").fetchall()
    return "\n".join(f"{s}.{t}  {n}" for s, t, n in rows)


@server.tool(description="Run a read-only SQL query and return up to 200 rows. target: 'local' (the DuckDB warehouse, "
                         "the default) or 'snowflake' (the Snowflake account: one SELECT, SHOW or DESCRIBE, as a role "
                         "that reads DPL.MARTS). On 'local' with snowflake_dialect=true (the default) the query is "
                         "Snowflake SQL, translated by sqlglot.")
def query(sql: str, target: Target = "local", snowflake_dialect: bool = True) -> str:
    if target == "snowflake":
        if err := _read_only(sql):
            return err
        try:
            cols, rows = _snowflake(sql)
        except (FileNotFoundError, RuntimeError) as e:
            return str(e)
        return f"-- on Snowflake as {SNOWFLAKE_ROLE}\n" + _table(cols, rows)
    text = sql
    if snowflake_dialect:
        import sqlglot
        text = ";\n".join(sqlglot.transpile(sql, read="snowflake", write="duckdb"))
    with duckdb.connect(WAREHOUSE, read_only=True) as con:
        cur = con.execute(text)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(MAX_ROWS + 1)
    return (f"-- ran as: {text}\n" if snowflake_dialect else "") + _table(cols, rows)


@server.tool(description="Run a dbt command in the project: build, test, run, compile, ls, snapshot or parse, with "
                         "an optional --select expression.")
def dbt(command: str, select: str = "") -> str:
    if command not in DBT_COMMANDS:
        return f"command must be one of {sorted(DBT_COMMANDS)}"
    cmd = ["dbt", command] + (["--select", select] if select else [])
    return _run(cmd, cwd=ROOT / "transform")


@server.tool(description="Run the whole pipeline end to end (./run.sh), offline (ECB sample) by default.")
def run_pipeline(offline: bool = True) -> str:
    return _run(["./run.sh"] + (["--offline"] if offline else []), timeout=900)


@server.tool(description="The latest migration parity report (legacy SQL Server warehouse vs the new marts).")
def parity_report() -> str:
    report = ROOT / "migration/reports/parity.md"
    return report.read_text(encoding="utf-8") if report.exists() else "no report yet: run the pipeline"


@server.tool(description="Translate T-SQL (SQL Server) into Snowflake SQL with sqlglot, as the migration does.")
def translate_tsql(sql: str) -> str:
    sys.path.insert(0, str(ROOT / "migration"))
    from translate import translate
    return ";\n\n".join(translate(sql))


@server.tool(description="Read a text file of the repository (a path relative to its root), to review code.")
def read_file(path: str) -> str:
    target = (ROOT / path).resolve()
    if ROOT not in target.parents or not target.is_file():
        return "only files inside the repository"
    if target.stat().st_size > 200_000:
        return "file too large"
    return target.read_text(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    server.run("stdio")
