from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import create_engine, text

TENANT = UUID("70000000-0000-4000-8000-000000000001")
OWNER = UUID("70000000-0000-4000-8000-000000000002")
DISABLED_USER = UUID("70000000-0000-4000-8000-000000000003")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "verify"}:
        raise SystemExit("usage: organization_migration_regression.py seed|verify")
    engine = create_engine(os.environ["PMC_TEST_ADMIN_DATABASE_URL"])
    now = datetime.now(UTC)
    if sys.argv[1] == "seed":
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO tenants (id,name,slug,status,created_at,updated_at) "
                     "VALUES (:id,'Migration Regression','migration-regression','active',:now,:now)"),
                {"id": TENANT, "now": now},
            )
            connection.execute(
                text("INSERT INTO users (id,display_name,status,created_at) "
                     "VALUES (:id,'Migration Owner','active',:now), "
                     "(:disabled,'Pre-existing Disabled User','disabled',:now)"),
                {"id": OWNER, "disabled": DISABLED_USER, "now": now},
            )
            connection.execute(
                text("INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) "
                     "VALUES (:membership,:tenant,:owner,'owner','active',:now), "
                     "(:disabled_membership,:tenant,:disabled,'member','active',:now)"),
                {
                    "membership": UUID("70000000-0000-4000-8000-000000000004"),
                    "disabled_membership": UUID("70000000-0000-4000-8000-000000000005"),
                    "tenant": TENANT,
                    "owner": OWNER,
                    "disabled": DISABLED_USER,
                    "now": now,
                },
            )
        return
    with engine.begin() as connection:
        projection = connection.execute(
            text("SELECT membership_status,user_status FROM organization_member_directory_projection "
                 "WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT, "user": DISABLED_USER},
        ).one()
        assert tuple(projection) == ("active", "disabled")
        connection.execute(text("SELECT set_config('app.user_id', :user, true)"), {"user": str(OWNER)})
        connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(TENANT)})
        assert connection.scalar(
            text("SELECT count(*) FROM organization_member_directory() WHERE user_id=:user"),
            {"user": DISABLED_USER},
        ) == 0


if __name__ == "__main__":
    main()
