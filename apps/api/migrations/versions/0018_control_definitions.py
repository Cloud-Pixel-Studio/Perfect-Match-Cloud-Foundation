# ruff: noqa: E501
"""Add reusable implementation activity and evidence requirement definitions."""

from alembic import op

revision = "0018_control_definitions"
down_revision = "0017_ctrl_applicability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
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

CREATE TABLE qms_control_activities (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 unit_id uuid NOT NULL,
 process_id uuid NOT NULL,
 control_id uuid NOT NULL,
 sequence integer NOT NULL DEFAULT 10 CHECK(sequence BETWEEN 0 AND 1000000),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 description text NOT NULL DEFAULT '' CHECK(length(description)<=4000),
 objective text NOT NULL DEFAULT '' CHECK(length(objective)<=4000),
 why_it_matters text NOT NULL DEFAULT '' CHECK(length(why_it_matters)<=4000),
 implementation_steps text NOT NULL DEFAULT '' CHECK(length(implementation_steps)<=4000),
 success_criteria text NOT NULL DEFAULT '' CHECK(length(success_criteria)<=4000),
 activity_kind varchar(32) NOT NULL DEFAULT 'qms_implementation' CHECK(activity_kind IN ('qms_implementation','project_administration','readiness_assessment','certification_preparation','transition','gap_remediation','other')),
 readiness_required boolean NOT NULL DEFAULT true,
 responsible_role varchar(160) NOT NULL DEFAULT '' CHECK(length(responsible_role)<=160),
 expected_output text NOT NULL DEFAULT '' CHECK(length(expected_output)<=4000),
 evidence_expectations text NOT NULL DEFAULT '' CHECK(length(evidence_expectations)<=4000),
 definition_key varchar(80),
 active boolean NOT NULL DEFAULT true,
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 FOREIGN KEY(control_id,tenant_id,unit_id,process_id) REFERENCES qms_controls(id,tenant_id,unit_id,process_id) ON DELETE RESTRICT,
 UNIQUE(id,tenant_id,unit_id,process_id),
 CHECK(activity_kind<>'project_administration' OR readiness_required=false)
);
CREATE UNIQUE INDEX qms_control_activity_definition_key ON qms_control_activities(control_id,definition_key) WHERE definition_key IS NOT NULL;
CREATE INDEX qms_control_activities_scope ON qms_control_activities(tenant_id,unit_id,control_id,active,sequence,id);
REVOKE ALL ON qms_control_activities FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_control_activities TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_control_activities FROM pmcloud_app;
ALTER TABLE qms_control_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_control_activities FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_control_activity_read ON qms_control_activities FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('controls.read',unit_id) OR qms_has_capability('controls.manage',unit_id)));
CREATE POLICY qms_control_activity_insert ON qms_control_activities FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('controls.manage',unit_id)
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND row_version=1);
CREATE POLICY qms_control_activity_update ON qms_control_activities FOR UPDATE
 USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id));
CREATE FUNCTION validate_qms_control_activity() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' AND (ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.control_id,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.control_id,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR (OLD.definition_key IS NOT NULL AND NEW.definition_key IS DISTINCT FROM OLD.definition_key)) THEN
  RAISE EXCEPTION 'activity identity is immutable and version must advance once' USING ERRCODE='23514';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM qms_controls c WHERE c.id=NEW.control_id AND c.tenant_id=NEW.tenant_id AND c.unit_id=NEW.unit_id AND c.process_id=NEW.process_id AND c.state='draft') THEN
  RAISE EXCEPTION 'control activities can only change while the control is draft' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_control_activity() FROM PUBLIC;
CREATE TRIGGER qms_control_activity_validate BEFORE INSERT OR UPDATE ON qms_control_activities FOR EACH ROW EXECUTE FUNCTION validate_qms_control_activity();

CREATE TABLE qms_control_evidence_requirements (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 unit_id uuid NOT NULL,
 process_id uuid NOT NULL,
 control_id uuid NOT NULL,
 sequence integer NOT NULL DEFAULT 10 CHECK(sequence BETWEEN 0 AND 1000000),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 description text NOT NULL DEFAULT '' CHECK(length(description)<=4000),
 acceptance_criteria text NOT NULL DEFAULT '' CHECK(length(acceptance_criteria)<=4000),
 evidence_type varchar(24) NOT NULL DEFAULT 'record' CHECK(evidence_type IN ('document','record','report','approval','system_record','meeting','training','metric','other')),
 mandatory boolean NOT NULL DEFAULT true,
 definition_key varchar(80),
 active boolean NOT NULL DEFAULT true,
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 FOREIGN KEY(control_id,tenant_id,unit_id,process_id) REFERENCES qms_controls(id,tenant_id,unit_id,process_id) ON DELETE RESTRICT,
 UNIQUE(id,tenant_id,unit_id,process_id),
 UNIQUE(id,tenant_id,unit_id,process_id,control_id)
);
CREATE UNIQUE INDEX qms_control_evidence_requirement_definition_key ON qms_control_evidence_requirements(control_id,definition_key) WHERE definition_key IS NOT NULL;
CREATE INDEX qms_control_evidence_requirements_scope ON qms_control_evidence_requirements(tenant_id,unit_id,control_id,active,sequence,id);
REVOKE ALL ON qms_control_evidence_requirements FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_control_evidence_requirements TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_control_evidence_requirements FROM pmcloud_app;
ALTER TABLE qms_control_evidence_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_control_evidence_requirements FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_control_evidence_requirement_read ON qms_control_evidence_requirements FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('controls.read',unit_id) OR qms_has_capability('controls.manage',unit_id)));
CREATE POLICY qms_control_evidence_requirement_insert ON qms_control_evidence_requirements FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('controls.manage',unit_id)
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND row_version=1);
CREATE POLICY qms_control_evidence_requirement_update ON qms_control_evidence_requirements FOR UPDATE
 USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('controls.manage',unit_id));
CREATE FUNCTION validate_qms_control_evidence_requirement() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' AND (ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.control_id,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.control_id,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR (OLD.definition_key IS NOT NULL AND NEW.definition_key IS DISTINCT FROM OLD.definition_key)) THEN
  RAISE EXCEPTION 'evidence requirement identity is immutable and version must advance once' USING ERRCODE='23514';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM qms_controls c WHERE c.id=NEW.control_id AND c.tenant_id=NEW.tenant_id AND c.unit_id=NEW.unit_id AND c.process_id=NEW.process_id AND c.state='draft') THEN
  RAISE EXCEPTION 'evidence requirements can only change while the control is draft' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_control_evidence_requirement() FROM PUBLIC;
CREATE TRIGGER qms_control_evidence_requirement_validate BEFORE INSERT OR UPDATE ON qms_control_evidence_requirements FOR EACH ROW EXECUTE FUNCTION validate_qms_control_evidence_requirement();
""")


def downgrade() -> None:
    op.execute(r"""
DROP TABLE qms_control_evidence_requirements;
DROP FUNCTION validate_qms_control_evidence_requirement();
DROP TABLE qms_control_activities;
DROP FUNCTION validate_qms_control_activity();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN (
 'auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored',
 'organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated',
 'workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published',
 'workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated',
 'workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked',
 'process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated',
 'revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired',
 'control_instance.created','control_instance.updated','control_instance.transitioned'));
""")
