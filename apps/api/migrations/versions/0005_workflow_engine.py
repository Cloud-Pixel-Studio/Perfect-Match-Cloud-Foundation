# ruff: noqa: E501

"""Add tenant-scoped workflow definitions, immutable versions, and instances."""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_workflow_engine"
down_revision: str | None = "0004_organization_structure"
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
          'organization.assignment_deactivated', 'organization.assignment_reactivated',
          'workflow.definition_created', 'workflow.definition_updated', 'workflow.definition_retired',
          'workflow.version_created', 'workflow.version_updated', 'workflow.version_published',
          'workflow.instance_started', 'workflow.instance_transitioned',
          'workflow.instance_completed', 'workflow.instance_cancelled'
        ));

        CREATE TABLE workflow_definitions (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          code varchar(40) NOT NULL CHECK (length(btrim(code)) > 0),
          name varchar(160) NOT NULL CHECK (length(btrim(name)) > 0),
          description varchar(1000),
          status varchar(20) NOT NULL CHECK (status IN ('active', 'retired')),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE (id, tenant_id)
        );
        CREATE UNIQUE INDEX workflow_definitions_tenant_code_ci_idx
          ON workflow_definitions (tenant_id, lower(code));

        CREATE TABLE workflow_versions (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          definition_id uuid NOT NULL,
          version_number integer NOT NULL CHECK (version_number > 0),
          status varchar(20) NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
          created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          published_at timestamptz,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE (id, tenant_id),
          UNIQUE (tenant_id, definition_id, version_number),
          FOREIGN KEY (definition_id, tenant_id) REFERENCES workflow_definitions(id, tenant_id)
            ON DELETE RESTRICT
        );
        CREATE UNIQUE INDEX workflow_versions_one_draft_idx
          ON workflow_versions (tenant_id, definition_id) WHERE status = 'draft';

        CREATE TABLE workflow_steps (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          workflow_version_id uuid NOT NULL,
          step_key varchar(40) NOT NULL CHECK (length(btrim(step_key)) > 0),
          name varchar(160) NOT NULL CHECK (length(btrim(name)) > 0),
          description varchar(1000),
          step_type varchar(20) NOT NULL CHECK (step_type IN ('task', 'approval', 'end')),
          is_start boolean NOT NULL DEFAULT false,
          position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE (id, tenant_id), UNIQUE (workflow_version_id, step_key),
          FOREIGN KEY (workflow_version_id, tenant_id) REFERENCES workflow_versions(id, tenant_id)
            ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX workflow_steps_position_idx ON workflow_steps(workflow_version_id, position);

        CREATE TABLE workflow_transitions (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          workflow_version_id uuid NOT NULL,
          from_step_id uuid NOT NULL,
          to_step_id uuid NOT NULL,
          transition_key varchar(40) NOT NULL CHECK (length(btrim(transition_key)) > 0),
          label varchar(160) NOT NULL CHECK (length(btrim(label)) > 0),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE (id, tenant_id), UNIQUE (workflow_version_id, from_step_id, transition_key),
          FOREIGN KEY (workflow_version_id, tenant_id) REFERENCES workflow_versions(id, tenant_id)
            ON DELETE CASCADE,
          FOREIGN KEY (from_step_id, tenant_id) REFERENCES workflow_steps(id, tenant_id)
            ON DELETE CASCADE,
          FOREIGN KEY (to_step_id, tenant_id) REFERENCES workflow_steps(id, tenant_id)
            ON DELETE CASCADE,
          CHECK (from_step_id <> to_step_id)
        );

        CREATE TABLE workflow_step_assignments (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          workflow_version_id uuid NOT NULL,
          step_id uuid NOT NULL,
          target_type varchar(24) NOT NULL CHECK (target_type IN ('user', 'organization_unit', 'application_role')),
          target_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
          target_organization_unit_id uuid,
          target_application_role varchar(20) CHECK (target_application_role IN ('owner', 'admin', 'member')),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE (id, tenant_id),
          FOREIGN KEY (workflow_version_id, tenant_id) REFERENCES workflow_versions(id, tenant_id)
            ON DELETE CASCADE,
          FOREIGN KEY (step_id, tenant_id) REFERENCES workflow_steps(id, tenant_id) ON DELETE CASCADE,
          FOREIGN KEY (target_organization_unit_id, tenant_id)
            REFERENCES organization_units(id, tenant_id) ON DELETE RESTRICT,
          CHECK ((target_type = 'user' AND target_user_id IS NOT NULL AND target_organization_unit_id IS NULL AND target_application_role IS NULL)
              OR (target_type = 'organization_unit' AND target_user_id IS NULL AND target_organization_unit_id IS NOT NULL AND target_application_role IS NULL)
              OR (target_type = 'application_role' AND target_user_id IS NULL AND target_organization_unit_id IS NULL AND target_application_role IS NOT NULL))
        );

        CREATE TABLE workflow_instances (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          workflow_version_id uuid NOT NULL,
          title varchar(200) NOT NULL CHECK (length(btrim(title)) > 0),
          reference varchar(200),
          status varchar(20) NOT NULL CHECK (status IN ('active', 'completed', 'cancelled')),
          current_step_id uuid NOT NULL,
          row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
          started_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          started_at timestamptz NOT NULL,
          completed_at timestamptz,
          cancelled_at timestamptz,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE (id, tenant_id),
          FOREIGN KEY (workflow_version_id, tenant_id) REFERENCES workflow_versions(id, tenant_id)
            ON DELETE RESTRICT,
          FOREIGN KEY (current_step_id, tenant_id) REFERENCES workflow_steps(id, tenant_id)
            ON DELETE RESTRICT
        );

        CREATE TABLE workflow_instance_events (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
          instance_id uuid NOT NULL,
          event_type varchar(20) NOT NULL CHECK (event_type IN ('started', 'transitioned', 'completed', 'cancelled')),
          from_step_id uuid,
          to_step_id uuid,
          transition_id uuid,
          actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          request_id uuid NOT NULL,
          occurred_at timestamptz NOT NULL,
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          FOREIGN KEY (instance_id, tenant_id) REFERENCES workflow_instances(id, tenant_id)
            ON DELETE CASCADE,
          UNIQUE (id, tenant_id)
        );
        CREATE INDEX workflow_instances_tenant_status_idx ON workflow_instances(tenant_id, status, updated_at DESC);
        CREATE INDEX workflow_events_instance_idx ON workflow_instance_events(tenant_id, instance_id, occurred_at, id);

        CREATE FUNCTION reject_published_workflow_configuration() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM workflow_versions WHERE id = COALESCE(NULLIF(to_jsonb(OLD)->>'workflow_version_id', '')::uuid, OLD.id) AND status = 'published') THEN
            RAISE EXCEPTION 'published workflow configuration is immutable' USING ERRCODE = '23514';
          END IF;
          RETURN COALESCE(NEW, OLD);
        END;
        $$;
        CREATE TRIGGER workflow_versions_immutable BEFORE UPDATE OR DELETE ON workflow_versions
          FOR EACH ROW WHEN (OLD.status = 'published') EXECUTE FUNCTION reject_published_workflow_configuration();
        CREATE TRIGGER workflow_steps_published_guard BEFORE UPDATE OR DELETE ON workflow_steps
          FOR EACH ROW EXECUTE FUNCTION reject_published_workflow_configuration();
        CREATE TRIGGER workflow_transitions_published_guard BEFORE UPDATE OR DELETE ON workflow_transitions
          FOR EACH ROW EXECUTE FUNCTION reject_published_workflow_configuration();
        CREATE TRIGGER workflow_assignments_published_guard BEFORE UPDATE OR DELETE ON workflow_step_assignments
          FOR EACH ROW EXECUTE FUNCTION reject_published_workflow_configuration();

        CREATE FUNCTION validate_workflow_instance_start() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM workflow_versions v WHERE v.id = NEW.workflow_version_id
                         AND v.tenant_id = NEW.tenant_id AND v.status = 'published') THEN
            RAISE EXCEPTION 'workflow instance requires a published version' USING ERRCODE = '23514';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM workflow_steps s WHERE s.id = NEW.current_step_id
                         AND s.workflow_version_id = NEW.workflow_version_id AND s.tenant_id = NEW.tenant_id
                         AND s.is_start) THEN
            RAISE EXCEPTION 'workflow instance must start at the version start step' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER workflow_instances_start_guard BEFORE INSERT ON workflow_instances
          FOR EACH ROW EXECUTE FUNCTION validate_workflow_instance_start();

        CREATE FUNCTION reject_workflow_event_mutation() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog AS $$
        BEGIN RAISE EXCEPTION 'workflow instance history is append-only' USING ERRCODE = '55000'; END;
        $$;
        CREATE TRIGGER workflow_instance_events_immutable BEFORE UPDATE OR DELETE ON workflow_instance_events
          FOR EACH ROW EXECUTE FUNCTION reject_workflow_event_mutation();

        DROP TRIGGER IF EXISTS organization_units_archive_guard ON organization_units;
        DROP FUNCTION IF EXISTS prevent_organization_archive();
        CREATE FUNCTION prevent_organization_archive() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        BEGIN
          IF NEW.status = 'archived' AND OLD.status <> 'archived' AND (
            EXISTS (SELECT 1 FROM organization_units WHERE parent_id = NEW.id AND status = 'active')
            OR EXISTS (SELECT 1 FROM organization_unit_assignments WHERE unit_id = NEW.id AND status = 'active')
            OR EXISTS (SELECT 1 FROM workflow_instances i JOIN workflow_step_assignments a
              ON a.step_id = i.current_step_id AND a.workflow_version_id = i.workflow_version_id
              WHERE i.tenant_id = NEW.tenant_id AND i.status = 'active'
                AND a.target_type = 'organization_unit' AND a.target_organization_unit_id = NEW.id)
          ) THEN
            RAISE EXCEPTION 'organization unit has active dependencies' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER organization_units_archive_guard BEFORE UPDATE ON organization_units
          FOR EACH ROW EXECUTE FUNCTION prevent_organization_archive();

        REVOKE ALL ON workflow_definitions, workflow_versions, workflow_steps, workflow_transitions,
          workflow_step_assignments, workflow_instances, workflow_instance_events FROM PUBLIC;
        GRANT SELECT, INSERT, UPDATE ON workflow_definitions, workflow_versions, workflow_steps,
          workflow_transitions, workflow_step_assignments TO pmcloud_app;
        GRANT SELECT, INSERT, UPDATE ON workflow_instances TO pmcloud_app;
        GRANT SELECT, INSERT ON workflow_instance_events TO pmcloud_app;
        REVOKE DELETE, TRUNCATE ON workflow_definitions, workflow_versions, workflow_steps,
          workflow_transitions, workflow_step_assignments, workflow_instances, workflow_instance_events FROM pmcloud_app;

        ALTER TABLE workflow_definitions ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_definitions FORCE ROW LEVEL SECURITY;
        ALTER TABLE workflow_versions ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_versions FORCE ROW LEVEL SECURITY;
        ALTER TABLE workflow_steps ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_steps FORCE ROW LEVEL SECURITY;
        ALTER TABLE workflow_transitions ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_transitions FORCE ROW LEVEL SECURITY;
        ALTER TABLE workflow_step_assignments ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_step_assignments FORCE ROW LEVEL SECURITY;
        ALTER TABLE workflow_instances ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_instances FORCE ROW LEVEL SECURITY;
        ALTER TABLE workflow_instance_events ENABLE ROW LEVEL SECURITY; ALTER TABLE workflow_instance_events FORCE ROW LEVEL SECURITY;

        CREATE POLICY workflow_definitions_read ON workflow_definitions FOR SELECT USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_definitions.tenant_id
           AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_definitions_write ON workflow_definitions FOR INSERT WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_definitions.tenant_id
           AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')));
        CREATE POLICY workflow_definitions_update ON workflow_definitions FOR UPDATE USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_definitions.tenant_id
           AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')))
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

        CREATE POLICY workflow_versions_read ON workflow_versions FOR SELECT USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_versions.tenant_id
           AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_versions_write ON workflow_versions FOR INSERT WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_versions.tenant_id
           AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')));
        CREATE POLICY workflow_versions_update ON workflow_versions FOR UPDATE USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_versions.tenant_id
           AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')))
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

        CREATE POLICY workflow_steps_read ON workflow_steps FOR SELECT USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_steps.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_steps_write ON workflow_steps FOR INSERT WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS
          (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_steps.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')));
        CREATE POLICY workflow_steps_update ON workflow_steps FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_steps.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin'))) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY workflow_transitions_read ON workflow_transitions FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_transitions.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_transitions_write ON workflow_transitions FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_transitions.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')));
        CREATE POLICY workflow_transitions_update ON workflow_transitions FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_transitions.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin'))) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY workflow_assignments_read ON workflow_step_assignments FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_step_assignments.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_assignments_write ON workflow_step_assignments FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_step_assignments.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')));
        CREATE POLICY workflow_assignments_update ON workflow_step_assignments FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_step_assignments.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin'))) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

        CREATE POLICY workflow_instances_read ON workflow_instances FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_instances.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_instances_write ON workflow_instances FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND started_by_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_instances.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active' AND m.role IN ('owner','admin')));
        CREATE POLICY workflow_instances_update ON workflow_instances FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_instances.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active')) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY workflow_events_read ON workflow_instance_events FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_instance_events.tenant_id AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND m.status = 'active'));
        CREATE POLICY workflow_events_append ON workflow_instance_events FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND actor_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid AND EXISTS (SELECT 1 FROM memberships m WHERE m.tenant_id = workflow_instance_events.tenant_id AND m.user_id = workflow_instance_events.actor_user_id AND m.status = 'active'));
        """
    )


def downgrade() -> None:
    op.execute(
        r"""
        DROP TRIGGER IF EXISTS workflow_instance_events_immutable ON workflow_instance_events;
        DROP TRIGGER IF EXISTS workflow_instances_start_guard ON workflow_instances;
        DROP TRIGGER IF EXISTS workflow_assignments_published_guard ON workflow_step_assignments;
        DROP TRIGGER IF EXISTS workflow_transitions_published_guard ON workflow_transitions;
        DROP TRIGGER IF EXISTS workflow_steps_published_guard ON workflow_steps;
        DROP TRIGGER IF EXISTS workflow_versions_immutable ON workflow_versions;
        DROP FUNCTION IF EXISTS reject_workflow_event_mutation();
        DROP FUNCTION IF EXISTS validate_workflow_instance_start();
        DROP FUNCTION IF EXISTS reject_published_workflow_configuration();
        DROP TABLE IF EXISTS workflow_instance_events, workflow_instances, workflow_step_assignments,
          workflow_transitions, workflow_steps, workflow_versions, workflow_definitions;
        DROP TRIGGER IF EXISTS organization_units_archive_guard ON organization_units;
        DROP FUNCTION IF EXISTS prevent_organization_archive();
        CREATE FUNCTION prevent_organization_archive() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        BEGIN
          IF NEW.status = 'archived' AND OLD.status <> 'archived' AND (
            EXISTS (SELECT 1 FROM organization_units WHERE parent_id = NEW.id AND status = 'active')
            OR EXISTS (SELECT 1 FROM organization_unit_assignments WHERE unit_id = NEW.id AND status = 'active')
          ) THEN RAISE EXCEPTION 'organization unit has active dependencies' USING ERRCODE = '23514'; END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER organization_units_archive_guard BEFORE UPDATE ON organization_units
          FOR EACH ROW EXECUTE FUNCTION prevent_organization_archive();
        ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_action_check;
        ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK (action IN (
          'auth.tenant_selected', 'organization.unit_created', 'organization.unit_updated',
          'organization.unit_moved', 'organization.unit_archived', 'organization.unit_restored',
          'organization.assignment_created', 'organization.assignment_updated',
          'organization.assignment_deactivated', 'organization.assignment_reactivated'
        ));
        """
    )
