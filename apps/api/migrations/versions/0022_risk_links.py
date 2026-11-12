# ruff: noqa: E501
"""Preserve scoped risk links to control implementations and document revisions."""

from alembic import op

revision = "0022_risk_links"
down_revision = "0021_qms_risks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked'));
ALTER TABLE qms_risks ADD CONSTRAINT uq_qms_risks_link_scope UNIQUE(id,tenant_id,unit_id);
ALTER TABLE qms_control_instances ADD CONSTRAINT uq_qms_control_instances_link_scope UNIQUE(id,tenant_id,unit_id);
CREATE TABLE qms_risk_control_links (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id), unit_id uuid NOT NULL,
 risk_id uuid NOT NULL, control_instance_id uuid NOT NULL,
 target_process_id uuid NOT NULL, snapshot_code varchar(50) NOT NULL, snapshot_name varchar(160) NOT NULL,
 linked_target_version integer NOT NULL CHECK(linked_target_version>=1),
 status varchar(20) NOT NULL CHECK(status IN ('active','removed')),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL,
 removed_by_user_id uuid REFERENCES users(id), removed_at timestamptz,
 removal_reason text NOT NULL DEFAULT '' CHECK(length(removal_reason)<=500),
 FOREIGN KEY(risk_id,tenant_id,unit_id) REFERENCES qms_risks(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id) REFERENCES qms_control_instances(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='removed')=(removed_by_user_id IS NOT NULL AND removed_at IS NOT NULL)),
 CHECK(status<>'removed' OR length(btrim(removal_reason))>0)
);
CREATE UNIQUE INDEX qms_risk_control_links_active ON qms_risk_control_links(risk_id,control_instance_id) WHERE status='active';
CREATE INDEX qms_risk_control_links_scope ON qms_risk_control_links(tenant_id,unit_id,risk_id,created_at,id);
CREATE TABLE qms_risk_document_links (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id), unit_id uuid NOT NULL,
 risk_id uuid NOT NULL, document_id uuid NOT NULL, document_revision_id uuid NOT NULL,
 target_process_id uuid NOT NULL, snapshot_code varchar(40) NOT NULL, snapshot_name varchar(200) NOT NULL,
 snapshot_revision varchar(40) NOT NULL, linked_target_version integer NOT NULL CHECK(linked_target_version>=1),
 file_sha256 varchar(64) NOT NULL,
 status varchar(20) NOT NULL CHECK(status IN ('active','removed')),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL,
 removed_by_user_id uuid REFERENCES users(id), removed_at timestamptz,
 removal_reason text NOT NULL DEFAULT '' CHECK(length(removal_reason)<=500),
 FOREIGN KEY(risk_id,tenant_id,unit_id) REFERENCES qms_risks(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_id,tenant_id,unit_id) REFERENCES qms_documents(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_revision_id,document_id,tenant_id) REFERENCES qms_document_revisions(id,document_id,tenant_id) ON DELETE RESTRICT,
 CHECK((status='removed')=(removed_by_user_id IS NOT NULL AND removed_at IS NOT NULL)),
 CHECK(status<>'removed' OR length(btrim(removal_reason))>0)
);
CREATE UNIQUE INDEX qms_risk_document_links_active ON qms_risk_document_links(risk_id,document_revision_id) WHERE status='active';
CREATE INDEX qms_risk_document_links_scope ON qms_risk_document_links(tenant_id,unit_id,risk_id,created_at,id);
REVOKE ALL ON qms_risk_control_links,qms_risk_document_links FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_risk_control_links,qms_risk_document_links TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_risk_control_links,qms_risk_document_links FROM pmcloud_app;
ALTER TABLE qms_risk_control_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_risk_control_links FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_risk_document_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_risk_document_links FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_risk_control_link_read ON qms_risk_control_links FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('risks.read',unit_id) AND qms_has_capability('control_instances.read',unit_id));
CREATE POLICY qms_risk_control_link_insert ON qms_risk_control_links FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.read',unit_id)
 AND qms_has_capability('risks.manage',unit_id) AND qms_has_capability('control_instances.read',unit_id));
CREATE POLICY qms_risk_control_link_update ON qms_risk_control_links FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.read',unit_id)
 AND qms_has_capability('risks.manage',unit_id) AND qms_has_capability('control_instances.read',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.read',unit_id)
 AND qms_has_capability('risks.manage',unit_id) AND qms_has_capability('control_instances.read',unit_id));
CREATE POLICY qms_risk_document_link_read ON qms_risk_document_links FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('risks.read',unit_id) AND qms_has_capability('documents.read',unit_id));
CREATE POLICY qms_risk_document_link_insert ON qms_risk_document_links FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.read',unit_id)
 AND qms_has_capability('risks.manage',unit_id) AND qms_has_capability('documents.read',unit_id));
CREATE POLICY qms_risk_document_link_update ON qms_risk_document_links FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.read',unit_id)
 AND qms_has_capability('risks.manage',unit_id) AND qms_has_capability('documents.read',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.read',unit_id)
 AND qms_has_capability('risks.manage',unit_id) AND qms_has_capability('documents.read',unit_id));
CREATE FUNCTION validate_qms_risk_link() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE parent_state text; actor uuid; previous_command text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 SELECT r.state INTO parent_state FROM qms_risks r WHERE r.id=NEW.risk_id
  AND r.tenant_id=NEW.tenant_id AND r.unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS NULL OR parent_state='closed' THEN
  RAISE EXCEPTION 'risk links require an open scoped risk' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.removed_by_user_id IS NOT NULL OR NEW.removed_at IS NOT NULL OR NEW.removal_reason<>'' THEN
   RAISE EXCEPTION 'risk link must be created active by current actor' USING ERRCODE='23514';
  END IF;
  NEW.created_at:=clock_timestamp();
  -- Snapshot targets under the caller's read RLS. Row-locking target queries would
  -- require target write authority; risk writers deliberately need only target read.
  IF TG_TABLE_NAME='qms_risk_control_links' THEN
   SELECT i.process_id,i.code,i.name,i.row_version
    INTO NEW.target_process_id,NEW.snapshot_code,NEW.snapshot_name,NEW.linked_target_version
    FROM qms_control_instances i WHERE i.id=NEW.control_instance_id
     AND i.tenant_id=NEW.tenant_id AND i.unit_id=NEW.unit_id AND i.status='active';
   IF NOT FOUND THEN
    RAISE EXCEPTION 'risk link requires an active control implementation in same unit' USING ERRCODE='23514';
   END IF;
  ELSE
   SELECT d.process_id,d.code,d.title,r.revision,r.row_version,r.file_sha256
    INTO NEW.target_process_id,NEW.snapshot_code,NEW.snapshot_name,NEW.snapshot_revision,NEW.linked_target_version,NEW.file_sha256
    FROM qms_documents d JOIN qms_document_revisions r ON r.document_id=d.id AND r.tenant_id=d.tenant_id
    WHERE d.id=NEW.document_id AND d.tenant_id=NEW.tenant_id AND d.unit_id=NEW.unit_id
     AND d.status='active' AND r.id=NEW.document_revision_id AND r.status='active' AND r.file_state='clean';
   IF NOT FOUND THEN
    RAISE EXCEPTION 'risk link requires a released clean revision in same unit' USING ERRCODE='23514';
   END IF;
  END IF;
 ELSE
  IF OLD.status<>'active' OR NEW.status<>'removed' OR NEW.row_version<>OLD.row_version+1
   OR length(btrim(NEW.removal_reason))=0
   OR (to_jsonb(NEW)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason']) THEN
   RAISE EXCEPTION 'risk link snapshot is immutable; only reasoned soft removal is allowed' USING ERRCODE='23514';
  END IF;
  NEW.removed_by_user_id:=actor;
  NEW.removed_at:=clock_timestamp();
 END IF;
 previous_command:=current_setting('app.risk_workflow',true);
 PERFORM set_config('app.risk_workflow','',true);
 UPDATE qms_risks SET row_version=row_version+1,updated_at=clock_timestamp()
  WHERE id=NEW.risk_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 PERFORM set_config('app.risk_workflow',COALESCE(previous_command,''),true);
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_risk_link() FROM PUBLIC;
CREATE TRIGGER qms_risk_control_link_validate BEFORE INSERT OR UPDATE ON qms_risk_control_links
 FOR EACH ROW EXECUTE FUNCTION validate_qms_risk_link();
CREATE TRIGGER qms_risk_document_link_validate BEFORE INSERT OR UPDATE ON qms_risk_document_links
 FOR EACH ROW EXECUTE FUNCTION validate_qms_risk_link();
""")


def downgrade() -> None:
    # Audit records must remain valid before any relationship history can be dropped.
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed'));
DROP TABLE qms_risk_document_links,qms_risk_control_links;
DROP FUNCTION validate_qms_risk_link();
ALTER TABLE qms_control_instances DROP CONSTRAINT uq_qms_control_instances_link_scope;
ALTER TABLE qms_risks DROP CONSTRAINT uq_qms_risks_link_scope;
""")
