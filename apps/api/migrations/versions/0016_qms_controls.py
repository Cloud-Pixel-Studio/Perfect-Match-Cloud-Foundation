# ruff: noqa: E501
"""Tenant-scoped control catalog and per-process implementation records."""

from alembic import op

revision = "0016_qms_controls"
down_revision = "0015_process_sites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK (capability IN (
 'documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete',
 'evidence.read','evidence.create','evidence.review','processes.read','processes.manage',
 'controls.read','controls.manage','control_instances.read','control_instances.manage'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
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
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read')));
$$;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN (
 'auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored',
 'organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated',
 'workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published',
 'workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated',
 'workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked',
 'process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated',
 'revision.submitted','revision.rejected','revision.approved','revision.released',
 'control.created','control.updated','control.activated','control.retired',
 'control_instance.created','control_instance.updated','control_instance.transitioned'));
CREATE TABLE qms_controls (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, process_id uuid NOT NULL,
 code varchar(40) NOT NULL CHECK(length(btrim(code))>0), name varchar(160) NOT NULL CHECK(length(btrim(name))>0),
 objective text NOT NULL CHECK(length(btrim(objective))>0 AND length(objective)<=4000),
 description text NOT NULL DEFAULT '' CHECK(length(description)<=4000),
 category varchar(30) NOT NULL CHECK(category IN ('governance','process','document_control','evidence','supplier','training','performance','improvement','other')),
 guidance_purpose text NOT NULL DEFAULT '' CHECK(length(guidance_purpose)<=4000),
 guidance_why text NOT NULL DEFAULT '' CHECK(length(guidance_why)<=4000),
 implementation_guidance text NOT NULL DEFAULT '' CHECK(length(implementation_guidance)<=4000),
 recommended_steps text NOT NULL DEFAULT '' CHECK(length(recommended_steps)<=4000),
 recommended_tools text NOT NULL DEFAULT '' CHECK(length(recommended_tools)<=4000),
 evidence_guidance text NOT NULL DEFAULT '' CHECK(length(evidence_guidance)<=4000),
 practical_notes text NOT NULL DEFAULT '' CHECK(length(practical_notes)<=4000),
 owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 state varchar(20) NOT NULL CHECK(state IN ('draft','active','retired')),
 row_version integer NOT NULL CHECK(row_version>0), created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id,process_id),
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT);
CREATE UNIQUE INDEX qms_control_code_unique ON qms_controls(tenant_id,lower(code));
CREATE INDEX qms_controls_scope_state ON qms_controls(tenant_id,unit_id,state,code);
REVOKE ALL ON qms_controls FROM PUBLIC; GRANT SELECT,INSERT,UPDATE ON qms_controls TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_controls FROM pmcloud_app;
ALTER TABLE qms_controls ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_controls FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_control_read ON qms_controls FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND
 (qms_has_capability('controls.read',unit_id) OR qms_has_capability('controls.manage',unit_id)));
CREATE POLICY qms_control_insert ON qms_controls FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id)
 AND state='draft' AND row_version=1 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_control_update ON qms_controls FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id));
CREATE FUNCTION validate_qms_control() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' AND (ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.created_by_user_id,NEW.created_at)
  IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.created_by_user_id,OLD.created_at)
  OR NEW.row_version<>OLD.row_version+1) THEN RAISE EXCEPTION 'control identity is immutable and version must advance once' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND OLD.state='retired' AND (NEW.state<>'retired' OR
  (to_jsonb(NEW)-ARRAY['row_version','updated_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','updated_at'])) THEN
  RAISE EXCEPTION 'retired controls are immutable' USING ERRCODE='23514'; END IF;
 IF NEW.owner_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id)
  AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'control owner must be an active tenant member' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' OR NEW.state IS DISTINCT FROM OLD.state THEN
  IF NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=NEW.process_id AND p.tenant_id=NEW.tenant_id AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'control requires an active scoped process' USING ERRCODE='23514'; END IF;
  IF TG_OP='UPDATE' AND NOT ((OLD.state='draft' AND NEW.state IN ('draft','active')) OR (OLD.state='active' AND NEW.state='retired')) THEN
   RAISE EXCEPTION 'invalid control state transition' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_control() FROM PUBLIC;
CREATE TRIGGER qms_control_validate BEFORE INSERT OR UPDATE ON qms_controls FOR EACH ROW EXECUTE FUNCTION validate_qms_control();

CREATE TABLE qms_control_instances (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, process_id uuid NOT NULL, control_id uuid NOT NULL,
 code varchar(50) NOT NULL CHECK(length(btrim(code))>0), name varchar(160) NOT NULL CHECK(length(btrim(name))>0),
 owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 implementation_status varchar(24) NOT NULL CHECK(implementation_status IN ('not_started','in_progress','evidence_required','under_review','implemented','not_applicable')),
 applicability varchar(20) NOT NULL CHECK(applicability IN ('applicable','conditional','not_applicable')),
 justification text NOT NULL DEFAULT '' CHECK(length(justification)<=4000),
 target_date date, implementation_date date, review_date date,
 notes text NOT NULL DEFAULT '' CHECK(length(notes)<=4000), status varchar(20) NOT NULL CHECK(status IN ('active','archived')),
 row_version integer NOT NULL CHECK(row_version>0), created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id,process_id), UNIQUE(tenant_id,control_id,process_id), UNIQUE(tenant_id,code),
 FOREIGN KEY(control_id,tenant_id,unit_id,process_id) REFERENCES qms_controls(id,tenant_id,unit_id,process_id) ON DELETE RESTRICT,
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((implementation_status='not_applicable')=(applicability='not_applicable')
  AND (applicability<>'not_applicable' OR length(btrim(justification))>0)),
 CHECK(implementation_status<>'implemented' OR implementation_date IS NOT NULL));
CREATE INDEX qms_control_instances_scope_status ON qms_control_instances(tenant_id,unit_id,status,implementation_status);
REVOKE ALL ON qms_control_instances FROM PUBLIC; GRANT SELECT,INSERT,UPDATE ON qms_control_instances TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_control_instances FROM pmcloud_app;
ALTER TABLE qms_control_instances ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_control_instances FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_control_instance_read ON qms_control_instances FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND
 (qms_has_capability('control_instances.read',unit_id) OR qms_has_capability('control_instances.manage',unit_id)));
CREATE POLICY qms_control_instance_insert ON qms_control_instances FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id)
 AND status='active' AND implementation_status='not_started' AND row_version=1
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_control_instance_update ON qms_control_instances FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id));
CREATE FUNCTION validate_qms_control_instance() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' AND (ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.control_id,NEW.created_by_user_id,NEW.created_at)
  IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.control_id,OLD.created_by_user_id,OLD.created_at)
  OR NEW.row_version<>OLD.row_version+1) THEN RAISE EXCEPTION 'instance identity is immutable and version must advance once' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND OLD.status='archived' AND (NEW.status<>'active' OR
  (to_jsonb(NEW)-ARRAY['status','row_version','updated_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','row_version','updated_at'])) THEN
  RAISE EXCEPTION 'archived instances must be restored before editing' USING ERRCODE='23514'; END IF;
 IF NEW.owner_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id)
  AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'instance owner must be an active tenant member' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' OR NEW.implementation_status IS DISTINCT FROM OLD.implementation_status THEN
  IF NOT EXISTS(SELECT 1 FROM qms_controls c WHERE c.id=NEW.control_id AND c.tenant_id=NEW.tenant_id AND c.unit_id=NEW.unit_id AND c.process_id=NEW.process_id AND c.state='active') THEN
   RAISE EXCEPTION 'instance requires an active scoped control' USING ERRCODE='23514'; END IF;
  IF TG_OP='UPDATE' AND NOT (
   (OLD.implementation_status='not_started' AND NEW.implementation_status IN ('in_progress','not_applicable')) OR
   (OLD.implementation_status='in_progress' AND NEW.implementation_status IN ('evidence_required','under_review','not_applicable')) OR
   (OLD.implementation_status='evidence_required' AND NEW.implementation_status IN ('in_progress','under_review','not_applicable')) OR
   (OLD.implementation_status='under_review' AND NEW.implementation_status IN ('in_progress','implemented','not_applicable')))
   THEN RAISE EXCEPTION 'invalid implementation transition' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_control_instance() FROM PUBLIC;
CREATE TRIGGER qms_control_instance_validate BEFORE INSERT OR UPDATE ON qms_control_instances FOR EACH ROW EXECUTE FUNCTION validate_qms_control_instance();
""")


def downgrade() -> None:
    op.execute(r"""
DROP TABLE qms_control_instances;
DROP FUNCTION validate_qms_control_instance();
DROP TABLE qms_controls;
DROP FUNCTION validate_qms_control();
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK (capability IN (
 'documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete',
 'evidence.read','evidence.create','evidence.review','processes.read','processes.manage'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
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
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read')));
$$;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN (
 'auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored',
 'organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated',
 'workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published',
 'workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated',
 'workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked',
 'process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated',
 'revision.submitted','revision.rejected','revision.approved','revision.released'));
""")
