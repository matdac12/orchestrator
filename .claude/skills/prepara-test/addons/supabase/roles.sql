-- Set the passwords for ONLY the roles this trimmed stack uses (auth + rest).
-- The full self-hosted roles.sql also sets pgbouncer/functions/storage admins,
-- but supabase_functions_admin/storage_admin aren't created by this Postgres image
-- variant unless their service migrations run — ALTERing a missing role aborts
-- initdb (exit 3). authenticator (PostgREST) + supabase_auth_admin (GoTrue) always exist.
\set pgpass `echo "$POSTGRES_PASSWORD"`

ALTER USER authenticator WITH PASSWORD :'pgpass';
ALTER USER supabase_auth_admin WITH PASSWORD :'pgpass';
