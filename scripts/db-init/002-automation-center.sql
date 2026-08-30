-- Automation Center's own database, separate from the one n8n uses.
-- Runs only on first initialisation of the postgres volume; the installer
-- creates it on already-provisioned machines (installer/lib.* -> ensure_ac_db).
SELECT 'CREATE DATABASE automation_center'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'automation_center')\gexec

-- Owned by the same role the stack already uses (POSTGRES_USER).
