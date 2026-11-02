# ruff: noqa: E501
"""Tenant-scoped document identities and immutable revision history."""

from alembic import op

revision = "0010_qms_documents"
down_revision = "0009_qms_processes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released'));
CREATE TABLE qms_documents(
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, process_id uuid NOT NULL, code varchar(40) NOT NULL CHECK(length(btrim(code))>0),
 title varchar(200) NOT NULL CHECK(length(btrim(title))>0), document_type varchar(30) NOT NULL CHECK(document_type IN ('policy','procedure','work_instruction','form','record_template','manual','other')),
 owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, status varchar(20) NOT NULL CHECK(status IN ('draft','active','obsolete')),
 current_revision_id uuid, row_version integer NOT NULL CHECK(row_version>0), created_by_user_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id), UNIQUE(id,tenant_id), FOREIGN KEY(unit_id,tenant_id) REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT,
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT);
CREATE UNIQUE INDEX qms_document_code_unique ON qms_documents(tenant_id,lower(code));
CREATE TABLE qms_document_revisions(
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT, document_id uuid NOT NULL,
 revision varchar(40) NOT NULL CHECK(length(btrim(revision))>0), status varchar(20) NOT NULL CHECK(status IN ('draft','under_review','approved','active','superseded','rejected')),
 prepared_by_user_id uuid NOT NULL REFERENCES users(id), reviewed_by_user_id uuid REFERENCES users(id), approved_by_user_id uuid REFERENCES users(id),
 change_summary text NOT NULL DEFAULT '' CHECK(length(change_summary)<=4000), revision_date date NOT NULL, effective_date date, review_date date,
 file_state varchar(20) NOT NULL CHECK(file_state IN ('missing','quarantined','clean','rejected')), file_sha256 varchar(64), file_size bigint, file_media_type varchar(120), row_version integer NOT NULL CHECK(row_version>0), created_at timestamptz NOT NULL,
 UNIQUE(document_id,revision), UNIQUE(id,document_id,tenant_id), FOREIGN KEY(document_id,tenant_id) REFERENCES qms_documents(id,tenant_id) ON DELETE RESTRICT,
 CHECK((file_state IN ('clean','quarantined') AND file_sha256 IS NOT NULL AND file_size>0) OR file_state IN ('missing','rejected')),
 CHECK(status NOT IN ('approved','active') OR (file_state='clean' AND approved_by_user_id IS NOT NULL)),
 CHECK(status<>'active' OR (effective_date IS NOT NULL AND reviewed_by_user_id IS NOT NULL)));
CREATE UNIQUE INDEX qms_document_one_active_revision ON qms_document_revisions(document_id) WHERE status='active';
ALTER TABLE qms_documents ADD CONSTRAINT qms_document_current_revision_fk FOREIGN KEY(current_revision_id,id,tenant_id) REFERENCES qms_document_revisions(id,document_id,tenant_id) DEFERRABLE INITIALLY DEFERRED;
REVOKE ALL ON qms_documents,qms_document_revisions FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_documents,qms_document_revisions TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_documents,qms_document_revisions FROM pmcloud_app;
ALTER TABLE qms_documents ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_document_revisions ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_document_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_document_read ON qms_documents FOR SELECT USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(qms_has_capability('documents.read',unit_id) OR qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.review',unit_id) OR qms_has_capability('documents.approve',unit_id) OR qms_has_capability('documents.release',unit_id)));
CREATE POLICY qms_document_insert ON qms_documents FOR INSERT WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('documents.author',unit_id) AND status='draft' AND current_revision_id IS NULL AND row_version=1 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_document_update ON qms_documents FOR UPDATE USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.release',unit_id))) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.release',unit_id)));
CREATE POLICY qms_revision_read ON qms_document_revisions FOR SELECT USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id));
CREATE POLICY qms_revision_insert ON qms_document_revisions FOR INSERT WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND status='draft' AND row_version=1 AND prepared_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id AND qms_has_capability('documents.author',d.unit_id)));
CREATE POLICY qms_revision_update ON qms_document_revisions FOR UPDATE USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id AND(qms_has_capability('documents.author',d.unit_id) OR qms_has_capability('documents.review',d.unit_id) OR qms_has_capability('documents.approve',d.unit_id) OR qms_has_capability('documents.release',d.unit_id)))) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id));
CREATE FUNCTION guard_qms_revision() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
 IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.tenant_id<>OLD.tenant_id OR NEW.document_id<>OLD.document_id OR NEW.prepared_by_user_id<>OLD.prepared_by_user_id OR NEW.created_at<>OLD.created_at OR NEW.row_version<>OLD.row_version+1) THEN RAISE EXCEPTION 'revision identity immutable' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND OLD.status IN ('active','superseded') AND (to_jsonb(NEW)-ARRAY['status','row_version','reviewed_by_user_id','approved_by_user_id','effective_date']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','row_version','reviewed_by_user_id','approved_by_user_id','effective_date']) THEN RAISE EXCEPTION 'released revision immutable' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND NEW.status<>OLD.status AND NOT ((OLD.status IN ('draft','rejected') AND NEW.status='under_review') OR (OLD.status='under_review' AND NEW.status IN ('approved','rejected')) OR (OLD.status='approved' AND NEW.status IN ('active','superseded')) OR (OLD.status='active' AND NEW.status='superseded')) THEN RAISE EXCEPTION 'invalid revision transition' USING ERRCODE='23514'; END IF;
 IF NEW.status IN ('approved','active') AND NEW.prepared_by_user_id=NEW.approved_by_user_id THEN RAISE EXCEPTION 'preparer cannot approve own revision' USING ERRCODE='23514'; END IF;
 IF NEW.status='active' AND (NEW.file_state<>'clean' OR NEW.approved_by_user_id IS NULL OR NEW.reviewed_by_user_id IS NULL) THEN RAISE EXCEPTION 'only reviewed, approved, clean revisions can be released' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
REVOKE ALL ON FUNCTION guard_qms_revision() FROM PUBLIC;
CREATE TRIGGER qms_revision_guard BEFORE INSERT OR UPDATE ON qms_document_revisions FOR EACH ROW EXECUTE FUNCTION guard_qms_revision();
""")


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_documents DROP CONSTRAINT qms_document_current_revision_fk;
DROP TABLE qms_document_revisions; DROP TABLE qms_documents;
DROP FUNCTION guard_qms_revision();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored'));
""")
