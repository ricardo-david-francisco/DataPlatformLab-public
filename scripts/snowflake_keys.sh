#!/usr/bin/env bash
# Make the RSA key pair the platform uses to sign in to Snowflake (key-pair authentication: no password anywhere).
# The private key stays in ~/.snowflake (chmod 600, never in git); you paste the PUBLIC key into Snowflake once.
#
#   ./run.sh snowflake-keys
set -euo pipefail
DIR="${HOME}/.snowflake"
KEY="${DIR}/dpl_rsa_key.p8"
PUB="${DIR}/dpl_rsa_key.pub"
mkdir -p "$DIR" && chmod 700 "$DIR"
if [ ! -f "$KEY" ]; then
    openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -inform PEM -out "$KEY" -nocrypt
    openssl rsa -in "$KEY" -pubout -out "$PUB" 2>/dev/null
    chmod 600 "$KEY"
    echo "made a new key pair in $DIR"
else
    echo "the key pair already exists in $DIR (delete it to make a new one)"
fi
BODY=$(grep -v -- "-----" "$PUB" | tr -d '\n')
cat <<EOF

Run this once in a Snowsight worksheet (role ACCOUNTADMIN), with your user name:

ALTER USER <YOUR_USER_NAME> SET RSA_PUBLIC_KEY='${BODY}';

Then check it: DESC USER <YOUR_USER_NAME>;   (RSA_PUBLIC_KEY_FP is now filled in)
EOF
