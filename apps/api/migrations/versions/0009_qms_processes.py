# ruff: noqa: E501
"""Scoped QMS processes with controlled hierarchy and audit."""

from alembic import op

revision = "0009_qms_processes"
down_revision = "0008_qms_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored'));
CREATE TABLE qms_processes (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, parent_id uuid, owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 code varchar(40) NOT NULL CHECK(length(btrim(code))>0),
 name varchar(160) NOT NULL CHECK(length(btrim(name))>0),
 process_type varchar(20) NOT NULL CHECK(process_type IN ('management','core','support','other')),
 sequence integer NOT NULL CHECK(sequence BETWEEN 0 AND 10000), department varchar(160) NOT NULL DEFAULT '',
 description text NOT NULL DEFAULT '' CHECK(length(description)<=4000),
 inputs text NOT NULL DEFAULT '' CHECK(length(inputs)<=4000), outputs text NOT NULL DEFAULT '' CHECK(length(outputs)<=4000),
 status varchar(20) NOT NULL CHECK(status IN ('active','archived')),
 row_version integer NOT NULL CHECK(row_version>0),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(unit_id,tenant_id) REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT,
 FOREIGN KEY(parent_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK(parent_id IS DISTINCT FROM id)
);
CREATE UNIQUE INDEX qms_process_code_unique ON qms_processes(tenant_id,lower(code));
CREATE INDEX qms_process_scope_status ON qms_processes(tenant_id,unit_id,status,sequence);
REVOKE ALL ON qms_processes FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_processes TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_processes FROM pmcloud_app;
ALTER TABLE qms_processes ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_processes FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_process_read ON qms_processes FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND(qms_has_capability('processes.read',unit_id) OR qms_has_capability('processes.manage',unit_id)));
CREATE POLICY qms_process_insert ON qms_processes FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('processes.manage',unit_id) AND status='active' AND row_version=1
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_process_update ON qms_processes FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('processes.manage',unit_id)) WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('processes.manage',unit_id));
CREATE FUNCTION lock_qms_process_scope(requested_unit uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NOT public.qms_has_capability('processes.manage',requested_unit) THEN
  RAISE EXCEPTION 'process scope authority denied' USING ERRCODE='42501';
 END IF;
 PERFORM id FROM public.organization_unit_integrity_projection
 WHERE id=requested_unit AND tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND status='active' FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'process scope must be active' USING ERRCODE='23514';
 END IF;
END; $$;
REVOKE ALL ON FUNCTION lock_qms_process_scope(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION lock_qms_process_scope(uuid) TO pmcloud_app;
CREATE FUNCTION validate_qms_process() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' AND (
  ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.created_by_user_id,NEW.created_at)
  IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.created_by_user_id,OLD.created_at)
  OR NEW.row_version<>OLD.row_version+1) THEN
  RAISE EXCEPTION 'process identity is immutable and version must advance once' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND OLD.status='archived' AND (NEW.status<>'active' OR
  (to_jsonb(NEW)-ARRAY['status','row_version','updated_at']) IS DISTINCT FROM
  (to_jsonb(OLD)-ARRAY['status','row_version','updated_at'])) THEN
  RAISE EXCEPTION 'archived processes must be restored before editing' USING ERRCODE='23514';
 END IF;
 PERFORM public.lock_qms_process_scope(NEW.unit_id);
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.tenant_id::text||':'||NEW.unit_id::text,0));
 IF NEW.owner_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id) AND NOT EXISTS (
  SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'process owner must be an active tenant member' USING ERRCODE='23514';
 END IF;
 IF NEW.parent_id IS NOT NULL THEN
  IF NEW.status='active' AND NOT EXISTS(SELECT 1 FROM qms_processes p
   WHERE p.id=NEW.parent_id AND p.tenant_id=NEW.tenant_id AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'active process requires an active scoped parent' USING ERRCODE='23514';
  END IF;
  IF EXISTS(WITH RECURSIVE chain AS (
   SELECT id,parent_id FROM qms_processes WHERE id=NEW.parent_id
   UNION SELECT p.id,p.parent_id FROM qms_processes p JOIN chain c ON p.id=c.parent_id)
   SELECT 1 FROM chain WHERE id=NEW.id) THEN
   RAISE EXCEPTION 'process hierarchy cannot contain a cycle' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.status='archived' AND EXISTS(SELECT 1 FROM qms_processes p WHERE p.parent_id=NEW.id AND p.status='active') THEN
  RAISE EXCEPTION 'process has active children' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_process_validate BEFORE INSERT OR UPDATE ON qms_processes
 FOR EACH ROW EXECUTE FUNCTION validate_qms_process();
CREATE TABLE qms_process_dependency_projection(id uuid PRIMARY KEY,unit_id uuid NOT NULL,status varchar(20) NOT NULL);
REVOKE ALL ON qms_process_dependency_projection FROM PUBLIC,pmcloud_app;
CREATE FUNCTION sync_qms_process_dependencies() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 INSERT INTO public.qms_process_dependency_projection(id,unit_id,status) VALUES(NEW.id,NEW.unit_id,NEW.status)
 ON CONFLICT(id) DO UPDATE SET unit_id=EXCLUDED.unit_id,status=EXCLUDED.status;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION sync_qms_process_dependencies() FROM PUBLIC;
CREATE TRIGGER qms_process_dependencies AFTER INSERT OR UPDATE ON qms_processes
 FOR EACH ROW EXECUTE FUNCTION sync_qms_process_dependencies();
CREATE FUNCTION protect_unit_with_qms_processes() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.status='archived' AND OLD.status<>'archived' THEN
  PERFORM id FROM public.organization_unit_integrity_projection WHERE id=NEW.id FOR UPDATE;
 END IF;
 IF NEW.status='archived' AND OLD.status<>'archived' AND EXISTS(
  SELECT 1 FROM public.qms_process_dependency_projection WHERE unit_id=NEW.id AND status='active') THEN
  RAISE EXCEPTION 'unit has active process dependencies' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION protect_unit_with_qms_processes() FROM PUBLIC;
CREATE TRIGGER organization_unit_qms_process_guard BEFORE UPDATE ON organization_units
 FOR EACH ROW EXECUTE FUNCTION protect_unit_with_qms_processes();

""")


def downgrade() -> None:
    op.execute(r"""
DROP TRIGGER organization_unit_qms_process_guard ON organization_units;
DROP FUNCTION protect_unit_with_qms_processes();
DROP TABLE qms_processes;
DROP FUNCTION validate_qms_process();
DROP FUNCTION lock_qms_process_scope(uuid);
DROP FUNCTION sync_qms_process_dependencies();
DROP TABLE qms_process_dependency_projection;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked'));

""")
