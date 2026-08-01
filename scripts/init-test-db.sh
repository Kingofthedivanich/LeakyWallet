#!/bin/sh
# Runs once, only on a brand-new postgres data volume (docker-entrypoint-initdb.d
# convention). Creates a separate database for pytest so `tests/conftest.py`'s
# drop_all/create_all never touches the dev database - see conftest.py's
# _test name guard for the other half of that safety net.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "${POSTGRES_DB}_test";
EOSQL
