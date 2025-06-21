#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER kiddos_user WITH PASSWORD 'kiddos_pass';
    CREATE DATABASE kiddos_db WITH OWNER kiddos_user;
    GRANT ALL PRIVILEGES ON DATABASE kiddos_db TO kiddos_user;
    
    \c kiddos_db
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kiddos_user;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO kiddos_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kiddos_user;
EOSQL