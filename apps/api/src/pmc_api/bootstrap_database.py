from __future__ import annotations

import os
import re

from sqlalchemy import Connection, create_engine, text

ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


def _role_statement(connection: Connection, role: str, password: str) -> str:
    if not ROLE_PATTERN.fullmatch(role):
        raise ValueError("invalid PostgreSQL role name")
    result = connection.execute(
        text(
            "SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', "
            "CAST(:role AS text), CAST(:password AS text))"
        ),
        {"role": role, "password": password},
    )
    return str(result.scalar_one())


def ensure_role(connection: Connection, role: str, password: str, attributes: str) -> None:
    exists = connection.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role)"), {"role": role}
    ).scalar_one()
    if not exists:
        connection.exec_driver_sql(_role_statement(connection, role, password))
    password_sql = connection.execute(
        text(
            "SELECT format('ALTER ROLE %I PASSWORD %L', "
            "CAST(:role AS text), CAST(:password AS text))"
        ),
        {"role": role, "password": password},
    ).scalar_one()
    connection.exec_driver_sql(password_sql)
    connection.exec_driver_sql(f'ALTER ROLE "{role}" {attributes}')


def main() -> None:
    admin_url = os.environ["PMC_DATABASE_ADMIN_URL"]
    database = os.environ["POSTGRES_DB"]
    migration_role = os.environ.get("POSTGRES_MIGRATION_USER", "pmcloud_migrator")
    runtime_role = os.environ.get("POSTGRES_RUNTIME_USER", "pmcloud_app")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        ensure_role(
            connection,
            migration_role,
            os.environ["POSTGRES_MIGRATION_PASSWORD"],
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
        )
        ensure_role(
            connection,
            runtime_role,
            os.environ["POSTGRES_RUNTIME_PASSWORD"],
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
        )
        for role in (migration_role, runtime_role):
            grant = connection.execute(
                text(
                    "SELECT format('GRANT CONNECT ON DATABASE %I TO %I', "
                    "CAST(:db AS text), CAST(:role AS text))"
                ),
                {"db": database, "role": role},
            ).scalar_one()
            connection.exec_driver_sql(grant)
        grant_create = connection.execute(
            text(
                "SELECT format('GRANT CREATE ON DATABASE %I TO %I', "
                "CAST(:db AS text), CAST(:role AS text))"
            ),
            {"db": database, "role": migration_role},
        ).scalar_one()
        connection.exec_driver_sql(grant_create)
        schema_grant = connection.execute(
            text(
                "SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', CAST(:role AS text))"
            ),
            {"role": migration_role},
        ).scalar_one()
        connection.exec_driver_sql(schema_grant)


if __name__ == "__main__":
    main()
