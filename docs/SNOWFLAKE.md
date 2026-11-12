# Running DataPlatformLab on Snowflake

Same pipeline, same dbt models: only the target changes. Authentication is a **key pair**: no password is stored or
typed anywhere, and the private key never leaves the machine that runs the pipeline.

## 1. An account

A free 30-day trial: https://signup.snowflake.com/ (no card). Choose **Enterprise**, **AWS**, a **Europe** region.
Activate it from the e-mail and set your user name and password (yours; the pipeline never uses them).

In Snowsight, your name (bottom left) → **Account** → copy the **account identifier** (`ORGNAME-ACCOUNTNAME`).

## 2. The key pair

```bash
./run.sh snowflake-keys
```

It makes the key pair in `~/.snowflake` and prints one `ALTER USER … SET RSA_PUBLIC_KEY='…'` statement: run it in a
Snowsight worksheet with your user name. Then create `~/.snowflake/dpl.env`:

```bash
SNOWFLAKE_ACCOUNT=ORGNAME-ACCOUNTNAME
SNOWFLAKE_USER=YOUR_LOGIN_NAME
SNOWFLAKE_PRIVATE_KEY_PATH=/root/.snowflake/dpl_rsa_key.p8
# SNOWFLAKE_USER_NAME=your_user_name
```

**Login name or user name?** Key-pair sign-in uses the **login name**; grants go to the user's **name**. They are often
the same, but a sign-up can give you an e-mail as login and a lower-case name that only matches in double quotes
(`ALTER USER "your_user_name" …`). `SHOW USERS LIKE '…'` shows both (`login_name`, `name`): put the login in
`SNOWFLAKE_USER` and, if it differs, the name in `SNOWFLAKE_USER_NAME`.

## 3. The platform, as code

```bash
./run.sh snowflake-plan      # terraform plan: warehouse, database, schemas, roles, grants, resource monitor
./run.sh snowflake-apply     # applies exactly the plan just shown (role ACCOUNTADMIN, as your user)
```

## 4. The pipeline

```bash
pip install -r requirements-snowflake.txt
./run.sh --target snowflake  # dlt loads into DPL.RAW_*, dbt builds DPL.STAGING / MARTS with every test
```

Look at it in Snowsight: database `DPL`, schema `MARTS`, table `FCT_POSITIONS_DAILY`; warehouse `DPL_WH` suspends
itself after 60 seconds.

## 5. Cost

The warehouse is XSMALL (1 credit an hour while it runs, billed per second) and suspends after 60 s idle. The
resource monitor notifies at 75% and 90% of 20 credits a month and suspends the warehouse at 100%. A full run takes
well under a minute of warehouse time.

## 6. An AI assistant on Snowflake (the MCP server)

The MCP server ([`mcp_server/server.py`](../mcp_server/server.py)) reads the local DuckDB warehouse by default. Its
`query` and `tables` tools take `target="snowflake"` to read this account instead, with the same `~/.snowflake/dpl.env`
and key pair (`pip install -r requirements-snowflake.txt` next to `requirements-mcp.txt`). Ask Claude, for example:
*"count the rows of DPL.MARTS.FCT_POSITIONS_DAILY on Snowflake"*.

Read-only, three ways over:

- **The role.** It signs in as your user but works as `DPL_FINANCE_ANALYST`, which reads the marts and nothing else
  (`snowflake-apply` grants it to you), and it runs `USE SECONDARY ROLES NONE`: a new user's default secondary roles
  are `ALL`, so without it ACCOUNTADMIN would still be in the session. Another role: `DPL_SNOWFLAKE_ROLE` (in Claude
  Desktop, the extension's *Snowflake role* setting); `DPL_ENGINEER` sees every layer.
- **The statement.** One `SELECT`, `SHOW` or `DESCRIBE` at a time, checked by sqlglot before it is sent.
- **The session.** At most 200 rows (`ROWS_PER_RESULTSET`), a 120 s statement timeout, and `QUERY_TAG =
  'dataplatformlab-mcp'` so its queries are easy to find in the query history.
