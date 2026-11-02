# ruff: noqa: E501
"""Connect NCRs to independently accepted implementation evidence."""

from alembic import op

revision = "0025_ncr_evidence_links"
down_revision = "0024_ncr_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked'));
ALTER TABLE qms_control_instance_evidence ADD CONSTRAINT uq_qms_evidence_ncr_scope UNIQUE(id,tenant_id,unit_id);
CREATE TABLE qms_ncr_evidence_links (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT, unit_id uuid NOT NULL,
 nonconformity_id uuid NOT NULL, evidence_id uuid NOT NULL, control_instance_id uuid NOT NULL,
 target_process_id uuid NOT NULL, snapshot_code varchar(50) NOT NULL, snapshot_name varchar(200) NOT NULL,
 linked_target_version integer NOT NULL CHECK(linked_target_version>=1),
 status varchar(20) NOT NULL CHECK(status IN ('active','removed')),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT, created_at timestamptz NOT NULL,
 removed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, removed_at timestamptz,
 removal_reason text NOT NULL DEFAULT '' CHECK(length(removal_reason)<=500),
 FOREIGN KEY(nonconformity_id,tenant_id,unit_id) REFERENCES qms_nonconformities(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(evidence_id,tenant_id,unit_id) REFERENCES qms_control_instance_evidence(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id) REFERENCES qms_control_instances(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='removed')=(removed_by_user_id IS NOT NULL AND removed_at IS NOT NULL)),
 CHECK(status<>'removed' OR length(btrim(removal_reason))>0)
);
CREATE UNIQUE INDEX qms_ncr_evidence_links_active ON qms_ncr_evidence_links(nonconformity_id,evidence_id) WHERE status='active';
CREATE INDEX qms_ncr_evidence_links_scope ON qms_ncr_evidence_links(tenant_id,unit_id,nonconformity_id,created_at,id);
REVOKE ALL ON qms_ncr_evidence_links FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_ncr_evidence_links TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_ncr_evidence_links FROM pmcloud_app;
ALTER TABLE qms_ncr_evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_ncr_evidence_links FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_ncr_evidence_link_read ON qms_ncr_evidence_links FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('ncr.read',unit_id) AND qms_has_capability('control_instances.read',unit_id));
CREATE POLICY qms_ncr_evidence_link_insert ON qms_ncr_evidence_links FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('ncr.read',unit_id)
 AND qms_has_capability('ncr.manage',unit_id) AND qms_has_capability('control_instances.read',unit_id));
CREATE POLICY qms_ncr_evidence_link_update ON qms_ncr_evidence_links FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('ncr.read',unit_id)
 AND qms_has_capability('ncr.manage',unit_id) AND qms_has_capability('control_instances.read',unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('ncr.read',unit_id)
 AND qms_has_capability('ncr.manage',unit_id) AND qms_has_capability('control_instances.read',unit_id));
CREATE FUNCTION validate_qms_ncr_evidence_link() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE parent_state text; actor uuid; previous_command text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 SELECT n.state INTO parent_state FROM qms_nonconformities n WHERE n.id=NEW.nonconformity_id
  AND n.tenant_id=NEW.tenant_id AND n.unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS NULL OR parent_state IN ('closed','cancelled') THEN
  RAISE EXCEPTION 'NCR evidence links require a nonterminal scoped nonconformity' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.removed_by_user_id IS NOT NULL OR NEW.removed_at IS NOT NULL OR NEW.removal_reason<>'' THEN
   RAISE EXCEPTION 'NCR evidence link must be created active by current actor' USING ERRCODE='23514';
  END IF;
  NEW.created_at:=clock_timestamp();
  SELECT e.process_id,i.code,e.name,e.row_version,e.control_instance_id
   INTO NEW.target_process_id,NEW.snapshot_code,NEW.snapshot_name,NEW.linked_target_version,NEW.control_instance_id
   FROM qms_control_instance_evidence e JOIN qms_control_instances i
    ON i.id=e.control_instance_id AND i.tenant_id=e.tenant_id AND i.unit_id=e.unit_id
   WHERE e.id=NEW.evidence_id AND e.tenant_id=NEW.tenant_id AND e.unit_id=NEW.unit_id
    AND e.status='accepted' AND i.status='active';
  IF NOT FOUND THEN
   RAISE EXCEPTION 'NCR evidence link requires accepted evidence on an active implementation in same unit' USING ERRCODE='23514';
  END IF;
 ELSE
  IF OLD.status<>'active' OR NEW.status<>'removed' OR NEW.row_version<>OLD.row_version+1
   OR length(btrim(NEW.removal_reason))=0
   OR (to_jsonb(NEW)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason']) THEN
   RAISE EXCEPTION 'NCR evidence link snapshot is immutable; only reasoned soft removal is allowed' USING ERRCODE='23514';
  END IF;
  NEW.removed_by_user_id:=actor;
  NEW.removed_at:=clock_timestamp();
 END IF;
 previous_command:=current_setting('app.ncr_workflow',true);
 PERFORM set_config('app.ncr_workflow','',true);
 UPDATE qms_nonconformities SET row_version=row_version+1,updated_at=clock_timestamp()
  WHERE id=NEW.nonconformity_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 PERFORM set_config('app.ncr_workflow',COALESCE(previous_command,''),true);
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_ncr_evidence_link() FROM PUBLIC;
CREATE TRIGGER qms_ncr_evidence_link_validate BEFORE INSERT OR UPDATE ON qms_ncr_evidence_links
 FOR EACH ROW EXECUTE FUNCTION validate_qms_ncr_evidence_link();
""")


def downgrade() -> None:
    # A recorded link audit event prevents the downgrade and preserves history.
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked'));
DROP TABLE qms_ncr_evidence_links;
DROP FUNCTION validate_qms_ncr_evidence_link();
ALTER TABLE qms_control_instance_evidence DROP CONSTRAINT uq_qms_evidence_ncr_scope;
""")
