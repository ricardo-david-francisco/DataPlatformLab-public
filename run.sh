#!/usr/bin/env bash
# The whole platform, end to end, with one command.
#
#   ./run.sh                     generate the data -> dlt -> dbt snapshot/build -> migration parity -> summary (DuckDB)
#   ./run.sh --offline           the same, ECB rates from data/sample (no internet)
#   ./run.sh --target snowflake  load and build in Snowflake (see platform/terraform and docs/SNOWFLAKE.md)
#   ./run.sh check <step>        the check of one step of docs/TOUR.md (0-8)
#   ./run.sh summary             what's in the warehouse now
#   ./run.sh snowflake-keys      make the key pair for Snowflake (docs/SNOWFLAKE.md)
#   ./run.sh snowflake-plan | snowflake-apply   Terraform for the Snowflake side (apply runs the saved plan)
#   ./run.sh sql [--snowflake] "select ..."   query the warehouse (Snowflake SQL translated to DuckDB)
#
# Environment: DPL_VENV (a virtualenv to use), DPL_WAREHOUSE (the DuckDB file, default warehouse/lab.duckdb).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"

# A virtualenv: DPL_VENV, else ./.venv, else /opt/de (a shared one, if the machine has it).
if [ -z "${DPL_VENV:-}" ]; then [ -d .venv ] && DPL_VENV=.venv || { [ -d /opt/de ] && DPL_VENV=/opt/de; }; fi
[ -n "${DPL_VENV:-}" ] && . "$DPL_VENV/bin/activate"
export DPL_WAREHOUSE="${DPL_WAREHOUSE:-$ROOT/warehouse/lab.duckdb}"
export DBT_PROFILES_DIR="$ROOT/transform"

OFFLINE=""
TARGET="local"
CMD="demo"
while [ $# -gt 0 ]; do
    case "$1" in
        --offline) OFFLINE="--offline" ;;
        --target) TARGET="$2"; shift ;;
        check) CMD="check"; STEP="${2:-}"; shift ;;
        summary) CMD="summary" ;;
        snowflake-keys) exec bash scripts/snowflake_keys.sh ;;
        snowflake-plan|snowflake-apply)
            . scripts/snowflake_env.sh
            # The provider also reads SNOWFLAKE_* (a warehouse it would create first): it gets only its TF_VAR_*.
            unset $(compgen -e | grep '^SNOWFLAKE_')
            cd platform/terraform && terraform init -input=false >/dev/null
            # plan saves what it shows; apply applies exactly that, nothing else.
            [ "$1" = "snowflake-plan" ] && exec terraform plan -input=false -out=tfplan
            exec terraform apply -input=false tfplan ;;
        sql) shift; exec python scripts/sql.py "$@" ;;
        *) echo "unknown argument: $1"; exit 2 ;;
    esac
    shift
done
export DPL_TARGET="$TARGET"
[ "$TARGET" = "snowflake" ] && . scripts/snowflake_env.sh
DEST="duckdb"; [ "$TARGET" = "snowflake" ] && DEST="snowflake"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
dbt_() { (cd transform && dbt "$@" --target "$TARGET"); }

case "$CMD" in
    check) exec python scripts/check.py "$STEP" ;;
    summary) exec python scripts/summary.py ;;
esac

step "1/6 Data: Boreal Asset Management, Jan-Nov 2026 (synthetic transactions on public reference data)"
python scripts/generate_data.py --out data

step "2/6 Ingestion (dlt): ECB FX rates, reference data, prices, custodian feeds, transfer agent -> raw ($DEST)"
python ingestion/pipelines.py --destination "$DEST" $OFFLINE --fund-attributes v1

step "3/6 dbt snapshot: fund attributes as they are on 10 Nov"
dbt_ snapshot

step "4/6 The 11 Nov change (a new portfolio manager and risk class for one fund), reloaded by dlt, then dbt build"
python ingestion/pipelines.py --destination "$DEST" --only reference --fund-attributes v2
dbt_ build

if [ "$TARGET" = "local" ]; then
    step "5/6 Migration: legacy T-SQL -> Snowflake SQL (sqlglot), then parity legacy vs new"
    python migration/translate.py
    python migration/parity.py
    step "6/6 Summary"
    python scripts/summary.py
else
    step "5/6 Migration parity runs on the local target (./run.sh); here: the marts are built in Snowflake"
fi
