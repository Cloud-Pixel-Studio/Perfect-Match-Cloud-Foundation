# ruff: noqa: E501
"""Add reviewed evidence records to each control implementation."""

from alembic import op

revision = "0020_control_evidence_review"
down_revision = "0019_instance_activities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_documents ADD CONSTRAINT uq_qms_document_evidence_scope
 UNIQUE(id,tenant_id,unit_id,process_id);
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
 'control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned',
 'control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted',
 'control_instance_evidence.accepted','control_instance_evidence.rejected'));

CREATE TABLE qms_control_instance_evidence (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 unit_id uuid NOT NULL,
 process_id uuid NOT NULL,
 control_id uuid NOT NULL,
 control_instance_id uuid NOT NULL,
 requirement_definition_id uuid NOT NULL,
 sequence integer NOT NULL CHECK(sequence BETWEEN 0 AND 1000000),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 description text NOT NULL DEFAULT '' CHECK(length(description)<=4000),
 acceptance_criteria text NOT NULL DEFAULT '' CHECK(length(acceptance_criteria)<=4000),
 evidence_type varchar(24) NOT NULL,
 mandatory boolean NOT NULL,
 document_id uuid,
 document_revision_id uuid,
 evidence_summary text NOT NULL DEFAULT '' CHECK(length(evidence_summary)<=4000),
 status varchar(20) NOT NULL CHECK(status IN ('draft','submitted','accepted','rejected')),
 submitted_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 submitted_at timestamptz,
 reviewed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 reviewed_at timestamptz,
 review_decision text NOT NULL DEFAULT '' CHECK(length(review_decision)<=1000),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id,process_id,control_id)
  REFERENCES qms_control_instances(id,tenant_id,unit_id,process_id,control_id) ON DELETE RESTRICT,
 FOREIGN KEY(requirement_definition_id,tenant_id,unit_id,process_id,control_id)
  REFERENCES qms_control_evidence_requirements(id,tenant_id,unit_id,process_id,control_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_id,tenant_id,unit_id,process_id)
  REFERENCES qms_documents(id,tenant_id,unit_id,process_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_revision_id,document_id,tenant_id)
  REFERENCES qms_document_revisions(id,document_id,tenant_id) ON DELETE RESTRICT,
 UNIQUE(control_instance_id,requirement_definition_id),
 CHECK((document_id IS NULL)=(document_revision_id IS NULL)),
 CHECK((status IN ('submitted','accepted','rejected'))=(submitted_at IS NOT NULL AND submitted_by_user_id IS NOT NULL)),
 CHECK((status IN ('accepted','rejected'))=(reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL)),
 CHECK(status NOT IN ('accepted','rejected') OR length(btrim(review_decision))>0)
);
CREATE INDEX qms_control_instance_evidence_readiness
 ON qms_control_instance_evidence(tenant_id,unit_id,control_instance_id,mandatory,status,sequence,id);
REVOKE ALL ON qms_control_instance_evidence FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_control_instance_evidence TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_control_instance_evidence FROM pmcloud_app;
ALTER TABLE qms_control_instance_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_control_instance_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_control_instance_evidence_read ON qms_control_instance_evidence FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('control_instances.read',unit_id) OR qms_has_capability('control_instances.manage',unit_id)));
CREATE POLICY qms_control_instance_evidence_insert ON qms_control_instance_evidence FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('control_instances.manage',unit_id)
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND row_version=1);
CREATE POLICY qms_control_instance_evidence_update ON qms_control_instance_evidence FOR UPDATE
 USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id));

CREATE FUNCTION validate_qms_control_instance_evidence() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE parent_status text; linked_status text; linked_file_state text;
BEGIN
 IF TG_OP='UPDATE' AND (
   ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.control_id,NEW.control_instance_id,NEW.requirement_definition_id,NEW.sequence,NEW.name,NEW.description,NEW.acceptance_criteria,NEW.evidence_type,NEW.mandatory,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.control_id,OLD.control_instance_id,OLD.requirement_definition_id,OLD.sequence,OLD.name,OLD.description,OLD.acceptance_criteria,OLD.evidence_type,OLD.mandatory,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1) THEN
  RAISE EXCEPTION 'evidence identity is immutable and version must advance once' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND OLD.status='accepted' THEN
  RAISE EXCEPTION 'accepted evidence is immutable' USING ERRCODE='23514';
 END IF;
 SELECT status INTO parent_status FROM qms_control_instances i
  WHERE i.id=NEW.control_instance_id AND i.tenant_id=NEW.tenant_id AND i.unit_id=NEW.unit_id
   AND i.process_id=NEW.process_id AND i.control_id=NEW.control_id FOR UPDATE;
 IF parent_status IS NULL OR parent_status<>'active' THEN
  RAISE EXCEPTION 'evidence requires an active implementation' USING ERRCODE='23514';
 END IF;
 IF NEW.document_revision_id IS NOT NULL AND
  (TG_OP='INSERT' OR NEW.document_revision_id IS DISTINCT FROM OLD.document_revision_id OR NEW.status='submitted') THEN
  SELECT r.status,r.file_state INTO linked_status,linked_file_state
   FROM qms_document_revisions r JOIN qms_documents d ON d.id=r.document_id AND d.tenant_id=r.tenant_id
   WHERE r.id=NEW.document_revision_id AND r.document_id=NEW.document_id
    AND r.tenant_id=NEW.tenant_id AND d.unit_id=NEW.unit_id AND d.process_id=NEW.process_id;
  IF linked_status IS DISTINCT FROM 'active' OR linked_file_state IS DISTINCT FROM 'clean' THEN
   RAISE EXCEPTION 'evidence must link to a released clean document revision in the same scope' USING ERRCODE='23514';
  END IF;
 END IF;
 IF TG_OP='UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
  IF current_setting('app.control_evidence_workflow',true) IS DISTINCT FROM 'on' THEN
   RAISE EXCEPTION 'use the evidence submission and review workflow' USING ERRCODE='23514';
  END IF;
  IF NOT ((OLD.status IN ('draft','rejected') AND NEW.status='submitted') OR
          (OLD.status='submitted' AND NEW.status IN ('accepted','rejected'))) THEN
   RAISE EXCEPTION 'invalid evidence review transition' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.status='submitted' AND (length(btrim(NEW.evidence_summary))=0 AND NEW.document_revision_id IS NULL) THEN
  RAISE EXCEPTION 'submission requires a summary or controlled document revision' USING ERRCODE='23514';
 END IF;
 IF NEW.status IN ('accepted','rejected') AND NEW.reviewed_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
  RAISE EXCEPTION 'review actor must match current user' USING ERRCODE='23514';
 END IF;
 IF NEW.status IN ('accepted','rejected') AND NEW.reviewed_by_user_id=NEW.submitted_by_user_id THEN
  RAISE EXCEPTION 'evidence reviewer must differ from submitter' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_control_instance_evidence() FROM PUBLIC;
CREATE TRIGGER qms_control_instance_evidence_validate BEFORE INSERT OR UPDATE ON qms_control_instance_evidence FOR EACH ROW EXECUTE FUNCTION validate_qms_control_instance_evidence();

CREATE OR REPLACE FUNCTION enforce_control_instance_readiness() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.implementation_status IN ('under_review','implemented')
  AND NEW.implementation_status IS DISTINCT FROM OLD.implementation_status
  AND (EXISTS(SELECT 1 FROM qms_control_instance_activities a
    WHERE a.tenant_id=NEW.tenant_id AND a.control_instance_id=NEW.id
     AND a.readiness_required AND a.status<>'completed')
   OR EXISTS(SELECT 1 FROM qms_control_instance_evidence e
    WHERE e.tenant_id=NEW.tenant_id AND e.control_instance_id=NEW.id
     AND e.mandatory AND e.status<>'accepted')) THEN
  RAISE EXCEPTION 'required implementation activities and evidence must be complete first' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
""")


def downgrade() -> None:
    op.execute(r"""
DROP TABLE qms_control_instance_evidence;
DROP FUNCTION validate_qms_control_instance_evidence();
CREATE OR REPLACE FUNCTION enforce_control_instance_readiness() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
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
ALTER TABLE qms_documents DROP CONSTRAINT uq_qms_document_evidence_scope;
""")
