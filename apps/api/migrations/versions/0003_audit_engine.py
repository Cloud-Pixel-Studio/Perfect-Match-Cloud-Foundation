"""Add immutable, tenant-scoped application audit events.

Revision ID: 0003_audit_engine
Revises: 0002_identity_binding_hardening
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_audit_engine"
down_revision: str | None = "0002_identity_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE audit_events (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            actor_user_id uuid NOT NULL REFERENCES
                users(id) ON DELETE RESTRICT,
            actor_display_name varchar(160) NOT NULL,
            actor_role varchar(20) NOT NULL CHECK
                (actor_role IN ('owner', 'admin', 'member', 'auditor')),
            action varchar(120) NOT NULL CHECK (action IN ('auth.tenant_selected')),
            resource_type varchar(80) NOT NULL,
            resource_id uuid,
            request_id uuid NOT NULL,
            schema_version integer NOT NULL CHECK (schema_version > 0),
            changed_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
            old_values jsonb,
            new_values jsonb,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX audit_events_tenant_time_idx ON audit_events
            (tenant_id, occurred_at DESC, id DESC);
        CREATE INDEX audit_events_action_idx ON audit_events
            (tenant_id, action, occurred_at DESC, id DESC);
        REVOKE ALL ON audit_events FROM PUBLIC;
        GRANT SELECT, INSERT ON audit_events TO pmcloud_app;
        REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM pmcloud_app;
        ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
        CREATE POLICY audit_events_reader ON audit_events FOR SELECT USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.tenant_id = audit_events.tenant_id
                  AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                  AND m.status = 'active'
                  AND m.role IN ('owner', 'admin', 'auditor')
            )
        );
        CREATE POLICY audit_events_append ON audit_events FOR INSERT WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND actor_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
            AND EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.tenant_id = audit_events.tenant_id
                  AND m.user_id = audit_events.actor_user_id
                  AND m.status = 'active'
                  AND m.role = audit_events.actor_role
            )
            AND actor_display_name = (
                SELECT u.display_name FROM users u
                WHERE u.id = audit_events.actor_user_id AND u.status = 'active'
            )
        );
        CREATE FUNCTION reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog AS $$
        BEGIN RAISE EXCEPTION 'audit_events is append-only'; END;
        $$;
        CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_events; DROP FUNCTION reject_audit_mutation();")
