"""Create the auth tables (`role`, `user_sys`, `user_identity`) and seed roles.

Login is done with Google OAuth, so there is no password column:
    - role           : role name + access (JSON permission map)
    - user_sys       : one row per person in the system
    - user_identity  : one row per external login (provider = 'google', ...)
                       linked to user_sys by user_sys_id

Every new user is created with the 'user' role (see DEFAULT_ROLE in the server).

Run after the database container is up:
    python scripts/create_auth_tables.py

If an old `user_sys` table from the username/password system exists, it is
renamed to `user_sys_legacy` (not dropped) so its data is kept.
"""
import json

from db_connection import get_connection

# ---------------------------------------------------------------------------
# Sequences (same explicit-sequence pattern as create_users_table.py)
# ---------------------------------------------------------------------------
CREATE_SEQUENCES_SQL = """
CREATE SEQUENCE IF NOT EXISTS role_id_seq;
CREATE SEQUENCE IF NOT EXISTS user_sys_id_seq;
CREATE SEQUENCE IF NOT EXISTS user_identity_id_seq;
"""

# Old user_sys had username/password columns -> keep it aside as legacy
RENAME_LEGACY_USER_SYS_SQL = """
DO $$
DECLARE
    r RECORD;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'user_sys'
          AND column_name = 'password'
    ) THEN
        ALTER TABLE user_sys RENAME TO user_sys_legacy;
        -- index names (user_sys_pkey, ...) don't follow the table rename
        FOR r IN
            SELECT indexname FROM pg_indexes
            WHERE schemaname = current_schema() AND tablename = 'user_sys_legacy'
        LOOP
            EXECUTE format('ALTER INDEX %I RENAME TO %I', r.indexname, 'legacy_' || r.indexname);
        END LOOP;
        RAISE NOTICE 'Old user_sys renamed to user_sys_legacy';
    END IF;
END $$;
"""

CREATE_ROLE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS role (
    role_id INTEGER PRIMARY KEY DEFAULT nextval('role_id_seq'),
    role_name VARCHAR(200) NOT NULL UNIQUE,
    access JSON NOT NULL DEFAULT '{}',
    flag_valid BOOLEAN NOT NULL DEFAULT TRUE
);
"""

CREATE_USER_SYS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_sys (
    user_sys_id BIGINT PRIMARY KEY DEFAULT nextval('user_sys_id_seq'),
    email VARCHAR(100) NOT NULL UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role_id INTEGER NOT NULL REFERENCES role(role_id),
    flag_valid BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_USER_IDENTITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_identity (
    identity_id BIGINT PRIMARY KEY DEFAULT nextval('user_identity_id_seq'),
    user_sys_id BIGINT NOT NULL REFERENCES user_sys(user_sys_id) ON DELETE CASCADE,
    email VARCHAR(100),
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    role_id INTEGER REFERENCES role(role_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_user_id)
);
"""

ALTER_SEQUENCE_OWNER_SQL = """
ALTER SEQUENCE role_id_seq OWNED BY role.role_id;
ALTER SEQUENCE user_sys_id_seq OWNED BY user_sys.user_sys_id;
ALTER SEQUENCE user_identity_id_seq OWNED BY user_identity.identity_id;
"""

# ---------------------------------------------------------------------------
# Seed roles
# access = { resource: { read, create, update, delete } }  (see AccessControl
# in nio-perov-server/src/common/interface/access.interface.ts)
# ---------------------------------------------------------------------------
DATA_RESOURCES = ["visualize", "methods", "raw_data", "feature_data"]


def perm(read=False, create=False, update=False, delete=False):
    return {"read": read, "create": create, "update": update, "delete": delete}


def build_access(data_perm, users_perm):
    access = {resource: data_perm for resource in DATA_RESOURCES}
    access["users"] = users_perm
    return access


ROLES = [
    ("admin", build_access(perm(True, True, True, True), perm(True, True, True, True))),
    ("professor", build_access(perm(True, True, True, True), perm(read=True))),
    ("Research Assistant", build_access(perm(True, True, True), perm())),
    ("Assistant", build_access(perm(True, True), perm())),
    ("user", build_access(perm(read=True), perm())),
]

# ON CONFLICT DO NOTHING -> re-running never overwrites access edited later
INSERT_ROLE_SQL = """
INSERT INTO role (role_name, access, flag_valid)
VALUES (%s, %s, TRUE)
ON CONFLICT (role_name) DO NOTHING;
"""


def main():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(RENAME_LEGACY_USER_SYS_SQL)
                cur.execute(CREATE_SEQUENCES_SQL)
                cur.execute(CREATE_ROLE_TABLE_SQL)
                cur.execute(CREATE_USER_SYS_TABLE_SQL)
                cur.execute(CREATE_USER_IDENTITY_TABLE_SQL)
                cur.execute(ALTER_SEQUENCE_OWNER_SQL)
                for role_name, access in ROLES:
                    cur.execute(INSERT_ROLE_SQL, (role_name, json.dumps(access)))
        print("Tables 'role', 'user_sys', 'user_identity' created (or already exist).")
        print(f"Seeded roles: {', '.join(name for name, _ in ROLES)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
