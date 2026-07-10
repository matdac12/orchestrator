-- Set the JWT GUCs used by PostgREST/PostgREST-adjacent SQL. Verbatim from the
-- official self-hosted docker/volumes/db/jwt.sql.
\set jwt_secret `echo "$JWT_SECRET"`
\set jwt_exp `echo "$JWT_EXP"`

ALTER DATABASE postgres SET "app.settings.jwt_secret" TO :'jwt_secret';
ALTER DATABASE postgres SET "app.settings.jwt_exp" TO :'jwt_exp';
