#!/usr/bin/env bash
# Sourced by run.sh for --target snowflake (and the platform commands): one settings file feeds dbt, dlt and Terraform.
#
# ~/.snowflake/dpl.env (outside git) holds three lines, and an optional fourth:
#   SNOWFLAKE_ACCOUNT=ORGNAME-ACCOUNTNAME     # Snowsight: your name (bottom left) -> Account -> Account identifier
#   SNOWFLAKE_USER=YOUR_LOGIN_NAME            # what you sign in with (SHOW USERS: login_name), maybe an e-mail
#   SNOWFLAKE_PRIVATE_KEY_PATH=/root/.snowflake/dpl_rsa_key.p8
#   SNOWFLAKE_USER_NAME=your_user_name        # only if the user's name differs from the login (SHOW USERS: name)
ENV_FILE="${DPL_SNOWFLAKE_ENV:-${HOME}/.snowflake/dpl.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "No Snowflake settings: create $ENV_FILE (see docs/SNOWFLAKE.md)" >&2
    return 1 2>/dev/null || exit 1
fi
set -a; . "$ENV_FILE"; set +a

# What Terraform creates (platform/terraform) and the pipeline uses.
export SNOWFLAKE_ROLE="${SNOWFLAKE_ROLE:-DPL_ENGINEER}" SNOWFLAKE_WAREHOUSE="${SNOWFLAKE_WAREHOUSE:-DPL_WH}"
export SNOWFLAKE_DATABASE="${SNOWFLAKE_DATABASE:-DPL}"

# dlt keeps incremental cursors per pipeline: Snowflake gets its own, so a local run never makes it skip data.
export DPL_DLT_DIR="${DPL_DLT_DIR:-${HOME}/.dlt/pipelines_snowflake}"

# dlt's Snowflake destination.
export DESTINATION__SNOWFLAKE__CREDENTIALS__HOST="$SNOWFLAKE_ACCOUNT"
export DESTINATION__SNOWFLAKE__CREDENTIALS__USERNAME="$SNOWFLAKE_USER"
export DESTINATION__SNOWFLAKE__CREDENTIALS__PRIVATE_KEY_PATH="$SNOWFLAKE_PRIVATE_KEY_PATH"
export DESTINATION__SNOWFLAKE__CREDENTIALS__DATABASE="$SNOWFLAKE_DATABASE"
export DESTINATION__SNOWFLAKE__CREDENTIALS__WAREHOUSE="$SNOWFLAKE_WAREHOUSE"
export DESTINATION__SNOWFLAKE__CREDENTIALS__ROLE="$SNOWFLAKE_ROLE"

# Terraform: the account identifier is ORGNAME-ACCOUNTNAME.
export TF_VAR_organization_name="${SNOWFLAKE_ACCOUNT%%-*}" TF_VAR_account_name="${SNOWFLAKE_ACCOUNT#*-}"
export TF_VAR_user="$SNOWFLAKE_USER" TF_VAR_private_key_path="$SNOWFLAKE_PRIVATE_KEY_PATH"
export TF_VAR_user_name="${SNOWFLAKE_USER_NAME:-$SNOWFLAKE_USER}"
