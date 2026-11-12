# ruff: noqa: E501
"""Prevent document scope changes and preserve capability on revision writes."""

from alembic import op

revision = "0011_qms_document_scope_guard"
down_revision = "0010_qms_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE OR REPLACE FUNCTION guard_qms_document() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
 IF NEW.id<>OLD.id OR NEW.tenant_id<>OLD.tenant_id OR NEW.unit_id<>OLD.unit_id OR NEW.process_id<>OLD.process_id OR NEW.created_by_user_id<>OLD.created_by_user_id OR NEW.created_at<>OLD.created_at OR NEW.row_version<>OLD.row_version+1 THEN RAISE EXCEPTION 'document scope is immutable and version must advance' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
REVOKE ALL ON FUNCTION guard_qms_document() FROM PUBLIC;
DROP TRIGGER IF EXISTS qms_document_guard ON qms_documents;
CREATE TRIGGER qms_document_guard BEFORE UPDATE ON qms_documents FOR EACH ROW EXECUTE FUNCTION guard_qms_document();
DROP POLICY qms_revision_update ON qms_document_revisions;
CREATE POLICY qms_revision_update ON qms_document_revisions FOR UPDATE USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id AND(qms_has_capability('documents.author',d.unit_id) OR qms_has_capability('documents.review',d.unit_id) OR qms_has_capability('documents.approve',d.unit_id) OR qms_has_capability('documents.release',d.unit_id)))) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id AND(qms_has_capability('documents.author',d.unit_id) OR qms_has_capability('documents.review',d.unit_id) OR qms_has_capability('documents.approve',d.unit_id) OR qms_has_capability('documents.release',d.unit_id))));
""")


def downgrade() -> None:
    op.execute(
        "DROP POLICY qms_revision_update ON qms_document_revisions; CREATE POLICY qms_revision_update ON qms_document_revisions FOR UPDATE USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id AND(qms_has_capability('documents.author',d.unit_id) OR qms_has_capability('documents.review',d.unit_id) OR qms_has_capability('documents.approve',d.unit_id) OR qms_has_capability('documents.release',d.unit_id)))) WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND EXISTS(SELECT 1 FROM qms_documents d WHERE d.id=document_id)); DROP TRIGGER qms_document_guard ON qms_documents; DROP FUNCTION guard_qms_document();"
    )
