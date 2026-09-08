# ruff: noqa: E501

"""Add tenant-scoped organization structure and assignments.

Revision ID: 0004_organization_structure
Revises: 0003_audit_engine
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_organization_structure"
down_revision: str | None = "0003_audit_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
        ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_action_check;
        ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK (action IN (
            'auth.tenant_selected', 'organization.unit_created', 'organization.unit_updated',
            'organization.unit_moved', 'organization.unit_archived', 'organization.unit_restored',
            'organization.assignment_created', 'organization.assignment_updated',
            'organization.assignment_deactivated', 'organization.assignment_reactivated'
        ));

        CREATE TABLE organization_units (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
            parent_id uuid,
            unit_type varchar(20) NOT NULL CHECK (unit_type IN ('site', 'department', 'team')),
            code varchar(40) NOT NULL CHECK (length(btrim(code)) > 0),
            name varchar(160) NOT NULL CHECK (length(btrim(name)) > 0),
            description varchar(500),
            status varchar(20) NOT NULL CHECK (status IN ('active', 'archived')),
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (id, tenant_id),
            FOREIGN KEY (parent_id, tenant_id) REFERENCES organization_units(id, tenant_id)
        );
        CREATE UNIQUE INDEX organization_units_tenant_code_ci_idx
            ON organization_units (tenant_id, lower(code));
        CREATE INDEX organization_units_parent_idx ON organization_units (tenant_id, parent_id);
        CREATE INDEX organization_units_tenant_status_idx ON organization_units (tenant_id, status);

        CREATE TABLE organization_unit_assignments (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
            unit_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            assignment_role varchar(20) NOT NULL CHECK (assignment_role IN ('member', 'lead')),
            is_primary boolean NOT NULL DEFAULT false,
            status varchar(20) NOT NULL CHECK (status IN ('active', 'inactive')),
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (id, tenant_id),
            FOREIGN KEY (unit_id, tenant_id) REFERENCES organization_units(id, tenant_id)
        );
        CREATE UNIQUE INDEX organization_assignments_primary_ci_idx
            ON organization_unit_assignments (tenant_id, user_id)
            WHERE status = 'active' AND is_primary;
        CREATE UNIQUE INDEX organization_assignments_active_user_unit_idx
            ON organization_unit_assignments (tenant_id, unit_id, user_id)
            WHERE status = 'active';
        CREATE INDEX organization_assignments_unit_idx ON organization_unit_assignments (tenant_id, unit_id);

        CREATE FUNCTION validate_organization_unit() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog AS $$
        BEGIN
            IF NEW.parent_id IS NOT NULL AND NEW.parent_id = NEW.id THEN
                RAISE EXCEPTION 'organization unit cannot parent itself' USING ERRCODE = '23514';
            END IF;
            IF NEW.parent_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM organization_units p
                WHERE p.id = NEW.parent_id AND p.status = 'archived' AND NEW.status = 'active'
            ) THEN
                RAISE EXCEPTION 'active organization unit cannot use archived parent'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                WITH RECURSIVE parents(id) AS (
                    SELECT NEW.parent_id
                    UNION ALL
                    SELECT u.parent_id FROM organization_units u JOIN parents p ON u.id = p.id
                    WHERE u.parent_id IS NOT NULL
                ) SELECT 1 FROM parents WHERE id = NEW.id
            ) THEN
                RAISE EXCEPTION 'organization unit hierarchy cycle is forbidden'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER organization_units_validate BEFORE INSERT OR UPDATE ON organization_units
            FOR EACH ROW EXECUTE FUNCTION validate_organization_unit();

        CREATE FUNCTION validate_organization_assignment() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM public.memberships m WHERE m.tenant_id = NEW.tenant_id
                  AND m.user_id = NEW.user_id AND m.status = 'active'
            ) THEN
                RAISE EXCEPTION 'organization assignment requires active tenant membership'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.organization_units u WHERE u.id = NEW.unit_id
                  AND u.tenant_id = NEW.tenant_id AND u.status = 'active'
            ) THEN
                RAISE EXCEPTION 'organization assignment requires active unit'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        REVOKE ALL ON FUNCTION validate_organization_assignment() FROM PUBLIC, pmcloud_app;
        CREATE TRIGGER organization_assignments_validate
            BEFORE INSERT OR UPDATE ON organization_unit_assignments
            FOR EACH ROW WHEN (NEW.status = 'active') EXECUTE FUNCTION validate_organization_assignment();

        CREATE FUNCTION prevent_organization_archive() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        BEGIN
            IF NEW.status = 'archived' AND OLD.status <> 'archived' AND (
                EXISTS (SELECT 1 FROM organization_units WHERE parent_id = NEW.id AND status = 'active')
                OR EXISTS (SELECT 1 FROM organization_unit_assignments
                           WHERE unit_id = NEW.id AND status = 'active')
            ) THEN
                RAISE EXCEPTION 'organization unit has active dependencies'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER organization_units_archive_guard BEFORE UPDATE ON organization_units
            FOR EACH ROW EXECUTE FUNCTION prevent_organization_archive();

        CREATE FUNCTION organization_member_directory()
        RETURNS TABLE (user_id uuid, display_name varchar, role varchar)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT m.user_id, u.display_name, m.role
            FROM public.memberships AS m
            JOIN public.users AS u ON u.id = m.user_id
            WHERE m.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
              AND m.status = 'active'
              AND u.status = 'active'
              AND EXISTS (
                  SELECT 1
                  FROM public.memberships AS actor_membership
                  WHERE actor_membership.tenant_id = m.tenant_id
                    AND actor_membership.user_id =
                        NULLIF(current_setting('app.user_id', true), '')::uuid
                    AND actor_membership.status = 'active'
              )
            ORDER BY lower(u.display_name), u.id;
        $$;
        REVOKE ALL ON FUNCTION organization_member_directory() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION organization_member_directory() TO pmcloud_app;

        REVOKE ALL ON organization_units, organization_unit_assignments FROM PUBLIC;
        GRANT SELECT, INSERT, UPDATE ON organization_units, organization_unit_assignments TO pmcloud_app;
        REVOKE DELETE, TRUNCATE ON organization_units, organization_unit_assignments FROM pmcloud_app;
        ALTER TABLE organization_units ENABLE ROW LEVEL SECURITY;
        ALTER TABLE organization_units FORCE ROW LEVEL SECURITY;
        ALTER TABLE organization_unit_assignments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE organization_unit_assignments FORCE ROW LEVEL SECURITY;
        CREATE POLICY organization_units_read ON organization_units FOR SELECT USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (
                SELECT 1 FROM memberships m WHERE m.tenant_id = organization_units.tenant_id
                AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND m.status = 'active' AND m.role IN ('owner', 'admin', 'auditor', 'member')
            )
        );
        CREATE POLICY organization_units_write ON organization_units FOR INSERT WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (
                SELECT 1 FROM memberships m WHERE m.tenant_id = organization_units.tenant_id
                AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND m.status = 'active' AND m.role IN ('owner', 'admin')
            )
        );
        CREATE POLICY organization_units_update ON organization_units FOR UPDATE USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (
                SELECT 1 FROM memberships m WHERE m.tenant_id = organization_units.tenant_id
                AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND m.status = 'active' AND m.role IN ('owner', 'admin')
            )
        ) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY organization_assignments_read ON organization_unit_assignments FOR SELECT USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (
                SELECT 1 FROM memberships m WHERE m.tenant_id = organization_unit_assignments.tenant_id
                AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND m.status = 'active' AND m.role IN ('owner', 'admin', 'auditor', 'member')
            )
        );
        CREATE POLICY organization_assignments_write ON organization_unit_assignments FOR INSERT WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (
                SELECT 1 FROM memberships m WHERE m.tenant_id = organization_unit_assignments.tenant_id
                AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND m.status = 'active' AND m.role IN ('owner', 'admin')
            )
        );
        CREATE POLICY organization_assignments_update ON organization_unit_assignments FOR UPDATE USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (
                SELECT 1 FROM memberships m WHERE m.tenant_id = organization_unit_assignments.tenant_id
                AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND m.status = 'active' AND m.role IN ('owner', 'admin')
            )
        ) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        r"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM audit_events
                WHERE action LIKE 'organization.%'
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade 0004: organization audit history would violate 0003'
                    USING ERRCODE = '55000';
            END IF;
        END;
        $$;
        DROP FUNCTION IF EXISTS organization_member_directory();
        DROP TRIGGER IF EXISTS organization_assignments_validate ON organization_unit_assignments;
        DROP TRIGGER IF EXISTS organization_units_archive_guard ON organization_units;
        DROP TRIGGER IF EXISTS organization_units_validate ON organization_units;
        DROP FUNCTION IF EXISTS validate_organization_assignment();
        DROP FUNCTION IF EXISTS prevent_organization_archive();
        DROP FUNCTION IF EXISTS validate_organization_unit();
        DROP TABLE IF EXISTS organization_unit_assignments;
        DROP TABLE IF EXISTS organization_units;
        ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_action_check;
        ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check
            CHECK (action IN ('auth.tenant_selected'));
        """
    )
