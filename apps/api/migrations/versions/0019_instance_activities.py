# ruff: noqa: E501
"""Generate controlled activity tasks for each applicable implementation."""

from alembic import op

revision = "0019_instance_activities"
down_revision = "0018_control_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_control_instances ADD CONSTRAINT uq_qms_control_instances_activity_parent
 UNIQUE(id,tenant_id,unit_id,process_id,control_id);
ALTER TABLE qms_control_activities ADD CONSTRAINT uq_qms_control_activities_parent
 UNIQUE(id,tenant_id,unit_id,process_id,control_id);
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN (
 'auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored',
 'organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated',
 'workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published',
 'workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated',
 'workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked',
 'process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated',
 'revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired',
 'control_instance.created','control_instance.updated','control_instance.transitioned',
 'control.activity_created','control.activity_updated','control.activity_deactivated',
 'control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated',
 'control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned'));

CREATE TABLE qms_control_instance_activities (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 unit_id uuid NOT NULL,
 process_id uuid NOT NULL,
 control_id uuid NOT NULL,
 control_instance_id uuid NOT NULL,
 activity_definition_id uuid NOT NULL,
 sequence integer NOT NULL CHECK(sequence BETWEEN 0 AND 1000000),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 description text NOT NULL DEFAULT '' CHECK(length(description)<=4000),
 objective text NOT NULL DEFAULT '' CHECK(length(objective)<=4000),
 why_it_matters text NOT NULL DEFAULT '' CHECK(length(why_it_matters)<=4000),
 implementation_steps text NOT NULL DEFAULT '' CHECK(length(implementation_steps)<=4000),
 success_criteria text NOT NULL DEFAULT '' CHECK(length(success_criteria)<=4000),
 activity_kind varchar(32) NOT NULL CHECK(activity_kind IN ('qms_implementation','project_administration','readiness_assessment','certification_preparation','transition','gap_remediation','other')),
 readiness_required boolean NOT NULL,
 responsible_role varchar(160) NOT NULL DEFAULT '' CHECK(length(responsible_role)<=160),
 expected_output text NOT NULL DEFAULT '' CHECK(length(expected_output)<=4000),
 evidence_expectations text NOT NULL DEFAULT '' CHECK(length(evidence_expectations)<=4000),
 assigned_to_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 status varchar(20) NOT NULL CHECK(status IN ('not_started','in_progress','blocked','under_review','completed')),
 target_date date,
 completion_summary text NOT NULL DEFAULT '' CHECK(length(completion_summary)<=4000),
 notes text NOT NULL DEFAULT '' CHECK(length(notes)<=4000),
 completed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 completed_at timestamptz,
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id,process_id,control_id)
  REFERENCES qms_control_instances(id,tenant_id,unit_id,process_id,control_id) ON DELETE RESTRICT,
 FOREIGN KEY(activity_definition_id,tenant_id,unit_id,process_id,control_id)
  REFERENCES qms_control_activities(id,tenant_id,unit_id,process_id,control_id) ON DELETE RESTRICT,
 UNIQUE(control_instance_id,activity_definition_id),
 CHECK((status='completed')=(completed_at IS NOT NULL AND completed_by_user_id IS NOT NULL)),
 CHECK(activity_kind<>'project_administration' OR readiness_required=false)
);
CREATE INDEX qms_control_instance_activities_readiness
 ON qms_control_instance_activities(tenant_id,unit_id,control_instance_id,readiness_required,status,sequence,id);
REVOKE ALL ON qms_control_instance_activities FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_control_instance_activities TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_control_instance_activities FROM pmcloud_app;
ALTER TABLE qms_control_instance_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_control_instance_activities FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_control_instance_activity_read ON qms_control_instance_activities FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('control_instances.read',unit_id) OR qms_has_capability('control_instances.manage',unit_id)));
CREATE POLICY qms_control_instance_activity_insert ON qms_control_instance_activities FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('control_instances.manage',unit_id)
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND row_version=1);
CREATE POLICY qms_control_instance_activity_update ON qms_control_instance_activities FOR UPDATE
 USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id));
CREATE FUNCTION validate_qms_control_instance_activity() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE parent_status text;
BEGIN
 IF TG_OP='UPDATE' AND (ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.control_id,NEW.control_instance_id,NEW.activity_definition_id,NEW.sequence,NEW.name,NEW.description,NEW.objective,NEW.why_it_matters,NEW.implementation_steps,NEW.success_criteria,NEW.activity_kind,NEW.readiness_required,NEW.responsible_role,NEW.expected_output,NEW.evidence_expectations,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.control_id,OLD.control_instance_id,OLD.activity_definition_id,OLD.sequence,OLD.name,OLD.description,OLD.objective,OLD.why_it_matters,OLD.implementation_steps,OLD.success_criteria,OLD.activity_kind,OLD.readiness_required,OLD.responsible_role,OLD.expected_output,OLD.evidence_expectations,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1) THEN
  RAISE EXCEPTION 'implementation activity identity is immutable and version must advance once' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND OLD.status='completed' THEN
  RAISE EXCEPTION 'completed implementation activities are immutable' USING ERRCODE='23514';
 END IF;
 IF NEW.assigned_to_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.assigned_to_user_id IS DISTINCT FROM OLD.assigned_to_user_id)
   AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.assigned_to_user_id) THEN
  RAISE EXCEPTION 'activity assignee must be an active tenant member' USING ERRCODE='23514';
 END IF;
 SELECT status INTO parent_status FROM qms_control_instances i
  WHERE i.id=NEW.control_instance_id AND i.tenant_id=NEW.tenant_id AND i.unit_id=NEW.unit_id
   AND i.process_id=NEW.process_id AND i.control_id=NEW.control_id FOR UPDATE;
 IF parent_status IS NULL OR parent_status<>'active' THEN
  RAISE EXCEPTION 'implementation activity requires an active implementation' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
  IF current_setting('app.control_activity_workflow',true) IS DISTINCT FROM 'on' THEN
   RAISE EXCEPTION 'use the implementation activity workflow to change status' USING ERRCODE='23514';
  END IF;
  IF NOT (
   (OLD.status='not_started' AND NEW.status='in_progress') OR
   (OLD.status='in_progress' AND NEW.status IN ('blocked','under_review')) OR
   (OLD.status='blocked' AND NEW.status IN ('in_progress','under_review')) OR
   (OLD.status='under_review' AND NEW.status IN ('in_progress','completed')))
   THEN RAISE EXCEPTION 'invalid implementation activity transition' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.status='completed' AND (length(btrim(NEW.completion_summary))=0 OR NEW.completed_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid) THEN
  RAISE EXCEPTION 'completion requires a summary and current actor' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_control_instance_activity() FROM PUBLIC;
CREATE TRIGGER qms_control_instance_activity_validate BEFORE INSERT OR UPDATE ON qms_control_instance_activities FOR EACH ROW EXECUTE FUNCTION validate_qms_control_instance_activity();
CREATE FUNCTION enforce_control_instance_readiness() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.implementation_status IN ('under_review','implemented')
  AND NEW.implementation_status IS DISTINCT FROM OLD.implementation_status
  AND EXISTS(SELECT 1 FROM qms_control_instance_activities a
   WHERE a.tenant_id=NEW.tenant_id AND a.control_instance_id=NEW.id
    AND a.readiness_required AND a.status<>'completed') THEN
  RAISE EXCEPTION 'required implementation activities must be completed first' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION enforce_control_instance_readiness() FROM PUBLIC;
CREATE TRIGGER qms_control_instance_readiness BEFORE UPDATE ON qms_control_instances FOR EACH ROW EXECUTE FUNCTION enforce_control_instance_readiness();
""")


def downgrade() -> None:
    op.execute(r"""
DROP TABLE qms_control_instance_activities;
DROP FUNCTION validate_qms_control_instance_activity();
DROP TRIGGER qms_control_instance_readiness ON qms_control_instances;
DROP FUNCTION enforce_control_instance_readiness();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN (
 'auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored',
 'organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated',
 'workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published',
 'workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated',
 'workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked',
 'process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated',
 'revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired',
 'control_instance.created','control_instance.updated','control_instance.transitioned',
 'control.activity_created','control.activity_updated','control.activity_deactivated',
 'control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated'));
ALTER TABLE qms_control_activities DROP CONSTRAINT uq_qms_control_activities_parent;
ALTER TABLE qms_control_instances DROP CONSTRAINT uq_qms_control_instances_activity_parent;
""")
