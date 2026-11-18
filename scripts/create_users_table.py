"""Example: create the `users` table with an explicit auto-increment id.

Use this file as a template for new "create table" scripts — copy it,
rename it, and change TABLE_NAME / CREATE_TABLE_SQL.

Run after the database container is up:
    python scripts/example_create_users_table.py

Note on auto-increment ids:
    `SERIAL` is just shorthand — Postgres itself creates a SEQUENCE and
    sets it as the column's DEFAULT via nextval(). Below we do the same
    thing explicitly (CREATE SEQUENCE -> CREATE TABLE -> ALTER TABLE
    ... SET DEFAULT), which is the pattern to reach for when you need
    control over the sequence itself (custom start value, increment,
    sharing a sequence across tables, etc.):

        CREATE SEQUENCE users_id_seq;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            ...
        );

        ALTER TABLE users
            ALTER COLUMN id SET DEFAULT nextval('users_id_seq');

        -- ties the sequence's lifecycle to the column, so
        -- DROP TABLE users also drops users_id_seq
        ALTER SEQUENCE users_id_seq OWNED BY users.id;
"""
from db_connection import get_connection

TABLE_NAME = "users"

CREATE_SEQUENCE_SQL = """
CREATE SEQUENCE IF NOT EXISTS users_id_seq;
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY DEFAULT nextval('users_id_seq'),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Ties the sequence to the column so it's dropped together with the table,
# and so tools like pg_dump/SERIAL-aware ORMs recognize it as "owned".
ALTER_SEQUENCE_OWNER_SQL = """
ALTER SEQUENCE users_id_seq OWNED BY users.id;
"""


def main():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SEQUENCE_SQL)
                cur.execute(CREATE_TABLE_SQL)
                cur.execute(ALTER_SEQUENCE_OWNER_SQL)
        print(f"Table '{TABLE_NAME}' created (or already exists), with sequence 'users_id_seq'.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
