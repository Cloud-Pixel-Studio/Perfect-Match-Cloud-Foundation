# ruff: noqa: E501
"""Explicit unit-scoped QMS capability grants."""

from alembic import op

revision = "0008_qms_capabilities"
down_revision = "0007_workflow_publication_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK (action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked'));
CREATE TABLE qms_access_grants (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL,
 capability varchar(40) NOT NULL CHECK (capability IN (
 'documents.read','documents.author','documents.review','documents.approve','documents.release',
 'evidence.read','evidence.create','evidence.review','processes.read','processes.manage')),
 status varchar(20) NOT NULL CHECK (status IN ('active','revoked')),
 granted_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 revoked_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 revoked_at timestamptz,
 FOREIGN KEY (unit_id,tenant_id) REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT,
 CHECK ((status='active' AND revoked_by_user_id IS NULL AND revoked_at IS NULL)
 OR (status='revoked' AND revoked_by_user_id IS NOT NULL AND revoked_at IS NOT NULL))
);
CREATE UNIQUE INDEX qms_access_active_unique ON qms_access_grants(tenant_id,user_id,unit_id,capability)
 WHERE status='active';
REVOKE ALL ON qms_access_grants FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_access_grants TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_access_grants FROM pmcloud_app;
ALTER TABLE qms_access_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_access_grants FORCE ROW LEVEL SECURITY;
CREATE FUNCTION qms_access_actor_is_active() RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.memberships m
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE m.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND m.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND m.status='active' AND u.status='active' AND t.status='active');
$$;
REVOKE ALL ON FUNCTION qms_access_actor_is_active() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION qms_access_actor_is_active() TO pmcloud_app;
CREATE POLICY qms_access_read ON qms_access_grants FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_access_actor_is_active() AND EXISTS (
 SELECT 1 FROM memberships m WHERE m.tenant_id=qms_access_grants.tenant_id
 AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND m.status='active'
 AND (qms_access_grants.user_id=m.user_id OR m.role='owner')));
CREATE POLICY qms_access_insert ON qms_access_grants FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_access_actor_is_active()
 AND user_id<>NULLIF(current_setting('app.user_id',true),'')::uuid
 AND granted_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND status='active' AND EXISTS (SELECT 1 FROM memberships m
 WHERE m.tenant_id=qms_access_grants.tenant_id
 AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND m.status='active' AND m.role='owner'));
CREATE POLICY qms_access_update ON qms_access_grants FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_access_actor_is_active() AND EXISTS (
 SELECT 1 FROM memberships m WHERE m.tenant_id=qms_access_grants.tenant_id
 AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND m.status='active' AND m.role='owner')) WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
CREATE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_access_validate BEFORE INSERT OR UPDATE ON qms_access_grants
 FOR EACH ROW EXECUTE FUNCTION validate_qms_access_grant();
CREATE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id
 JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read')));
$$;
REVOKE ALL ON FUNCTION qms_has_capability(text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION qms_has_capability(text,uuid) TO pmcloud_app;

""")


def downgrade() -> None:
    op.execute(r"""
DROP FUNCTION qms_has_capability(text,uuid);
DROP TABLE qms_access_grants;
DROP FUNCTION qms_access_actor_is_active();
DROP FUNCTION validate_qms_access_grant();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK (action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled'));
""")
