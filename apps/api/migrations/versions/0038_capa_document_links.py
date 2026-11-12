"""Scoped CAPA references to released, clean document revisions."""

# ruff: noqa: E501 -- SQL statements and audit action constraints are migration snapshots.

from alembic import op

revision = "0038_capa_document_links"
down_revision = "0037_capa_draft_edit_command"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated','capa.action_transitioned','capa.implementation_started','capa.effectiveness_review_started','capa.effectiveness_decided','capa.effectiveness_recorded','capa.closed','capa.cancelled','capa.document_linked','capa.document_unlinked'));
CREATE TABLE qms_capa_document_links (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, capa_id uuid NOT NULL, document_id uuid NOT NULL,
 document_revision_id uuid NOT NULL, snapshot_revision varchar(40) NOT NULL,
 file_sha256 varchar(64) NOT NULL, target_process_id uuid NOT NULL,
 snapshot_code varchar(50) NOT NULL, snapshot_name varchar(200) NOT NULL,
 linked_target_version integer NOT NULL CHECK(linked_target_version>=1),
 status varchar(20) NOT NULL CHECK(status IN ('active','removed')),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 removed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 removed_at timestamptz, removal_reason text NOT NULL DEFAULT ''
  CHECK(length(removal_reason)<=500),
 FOREIGN KEY(capa_id,tenant_id,unit_id) REFERENCES qms_capas(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_id,tenant_id,unit_id) REFERENCES qms_documents(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_revision_id,document_id,tenant_id)
  REFERENCES qms_document_revisions(id,document_id,tenant_id) ON DELETE RESTRICT,
 CHECK((status='removed')=(removed_by_user_id IS NOT NULL AND removed_at IS NOT NULL)),
 CHECK(status<>'removed' OR length(btrim(removal_reason))>0)
);
CREATE UNIQUE INDEX qms_capa_document_links_active ON qms_capa_document_links(capa_id,document_revision_id) WHERE status='active';
CREATE INDEX qms_capa_document_links_scope ON qms_capa_document_links(tenant_id,unit_id,capa_id,created_at,id);
REVOKE ALL ON qms_capa_document_links FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_capa_document_links TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_capa_document_links FROM pmcloud_app;
ALTER TABLE qms_capa_document_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_document_links FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_capa_document_link_read ON qms_capa_document_links FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('documents.read',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_document_links.capa_id
  AND c.tenant_id=qms_capa_document_links.tenant_id AND c.unit_id=qms_capa_document_links.unit_id));
CREATE POLICY qms_capa_document_link_insert ON qms_capa_document_links FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('capa.manage',unit_id)
 AND qms_has_capability('documents.read',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_document_links.capa_id
  AND c.tenant_id=qms_capa_document_links.tenant_id AND c.unit_id=qms_capa_document_links.unit_id));
CREATE POLICY qms_capa_document_link_update ON qms_capa_document_links FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('capa.manage',unit_id)
 AND qms_has_capability('documents.read',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_document_links.capa_id
  AND c.tenant_id=qms_capa_document_links.tenant_id AND c.unit_id=qms_capa_document_links.unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('capa.manage',unit_id)
 AND qms_has_capability('documents.read',unit_id));
CREATE FUNCTION validate_qms_capa_document_link() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE parent_state text; actor uuid; previous_command text; command text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 SELECT c.state INTO parent_state FROM qms_capas c WHERE c.id=NEW.capa_id
  AND c.tenant_id=NEW.tenant_id AND c.unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state NOT IN ('draft','analysis','action_planned','implementation') OR parent_state IS NULL THEN
  RAISE EXCEPTION 'CAPA document links are locked during effectiveness review or after termination' USING ERRCODE='23514';
 END IF;
 IF ((TG_OP='INSERT' AND current_setting('app.capa_link_command',true) IS DISTINCT FROM 'link')
  OR (TG_OP='UPDATE' AND current_setting('app.capa_link_command',true) IS DISTINCT FROM 'unlink'))
  OR NOT qms_has_capability('capa.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'CAPA document link requires a controlled manager command' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.removed_by_user_id IS NOT NULL OR NEW.removed_at IS NOT NULL OR NEW.removal_reason<>'' THEN
   RAISE EXCEPTION 'CAPA document link must start active by current actor' USING ERRCODE='23514';
  END IF;
  NEW.created_at:=clock_timestamp();
  SELECT d.process_id,d.code,d.title,r.revision,r.row_version,r.file_sha256
   INTO NEW.target_process_id,NEW.snapshot_code,NEW.snapshot_name,
    NEW.snapshot_revision,NEW.linked_target_version,NEW.file_sha256
   FROM qms_documents d JOIN qms_document_revisions r
    ON r.document_id=d.id AND r.tenant_id=d.tenant_id
   WHERE d.id=NEW.document_id AND d.tenant_id=NEW.tenant_id AND d.unit_id=NEW.unit_id
    AND d.status='active' AND r.id=NEW.document_revision_id
    AND r.status='active' AND r.file_state='clean';
  IF NOT FOUND THEN
   RAISE EXCEPTION 'CAPA link requires a released clean document revision in the same unit' USING ERRCODE='23514';
  END IF;
 ELSE
  IF OLD.status<>'active' OR NEW.status<>'removed' OR NEW.row_version<>OLD.row_version+1
   OR length(btrim(NEW.removal_reason))=0
   OR (to_jsonb(NEW)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason']) THEN
   RAISE EXCEPTION 'CAPA document snapshot is immutable; removal requires a reason' USING ERRCODE='23514';
  END IF;
  NEW.removed_by_user_id:=actor;
  NEW.removed_at:=clock_timestamp();
 END IF;
 command:=CASE parent_state WHEN 'draft' THEN 'edit' WHEN 'analysis' THEN 'edit'
  WHEN 'action_planned' THEN 'action' ELSE 'progress' END;
 previous_command:=current_setting('app.capa_analysis_command',true);
 PERFORM set_config('app.capa_analysis_command',command,true);
 UPDATE qms_capas SET row_version=row_version+1,updated_at=clock_timestamp()
  WHERE id=NEW.capa_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 PERFORM set_config('app.capa_analysis_command',COALESCE(previous_command,''),true);
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_capa_document_link() FROM PUBLIC;
CREATE TRIGGER qms_capa_document_link_validate BEFORE INSERT OR UPDATE ON qms_capa_document_links
 FOR EACH ROW EXECUTE FUNCTION validate_qms_capa_document_link();
""")


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_capa_document_links DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capa_document_links)
  OR EXISTS(SELECT 1 FROM audit_events WHERE action IN ('capa.document_linked','capa.document_unlinked')) THEN
  RAISE EXCEPTION 'cannot discard CAPA document link history';
 END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_document_links ENABLE ROW LEVEL SECURITY;
DROP TABLE qms_capa_document_links;
DROP FUNCTION validate_qms_capa_document_link();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated','capa.action_transitioned','capa.implementation_started','capa.effectiveness_review_started','capa.effectiveness_decided','capa.effectiveness_recorded','capa.closed','capa.cancelled'));
""")
