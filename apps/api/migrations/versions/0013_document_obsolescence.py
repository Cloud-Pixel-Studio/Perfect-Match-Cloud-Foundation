# ruff: noqa: E501
"""Add explicit authority for controlled document obsolescence."""

from alembic import op

revision = "0013_document_obsolescence"
down_revision = "0012_document_quarantine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK (capability IN (
 'documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete',
 'evidence.read','evidence.create','evidence.review','processes.read','processes.manage'));
DROP POLICY qms_document_read ON qms_documents;
CREATE POLICY qms_document_read ON qms_documents FOR SELECT
 USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(
  qms_has_capability('documents.read',unit_id) OR qms_has_capability('documents.author',unit_id)
  OR qms_has_capability('documents.review',unit_id) OR qms_has_capability('documents.approve',unit_id)
  OR qms_has_capability('documents.release',unit_id) OR qms_has_capability('documents.obsolete',unit_id)));
DROP POLICY qms_document_update ON qms_documents;
CREATE POLICY qms_document_update ON qms_documents FOR UPDATE
 USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(
  qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.release',unit_id)
  OR qms_has_capability('documents.obsolete',unit_id)))
 WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(
  qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.release',unit_id)
  OR qms_has_capability('documents.obsolete',unit_id)));
""")


def downgrade() -> None:
    op.execute(r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_access_grants WHERE capability='documents.obsolete') THEN
  RAISE EXCEPTION 'revoke documents.obsolete grants before downgrading';
 END IF;
END $$;
DROP POLICY qms_document_read ON qms_documents;
CREATE POLICY qms_document_read ON qms_documents FOR SELECT
 USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(
  qms_has_capability('documents.read',unit_id) OR qms_has_capability('documents.author',unit_id)
  OR qms_has_capability('documents.review',unit_id) OR qms_has_capability('documents.approve',unit_id)
  OR qms_has_capability('documents.release',unit_id)));
DROP POLICY qms_document_update ON qms_documents;
CREATE POLICY qms_document_update ON qms_documents FOR UPDATE
 USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(
  qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.release',unit_id)))
 WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND(
  qms_has_capability('documents.author',unit_id) OR qms_has_capability('documents.release',unit_id)));
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK (capability IN (
 'documents.read','documents.author','documents.review','documents.approve','documents.release',
 'evidence.read','evidence.create','evidence.review','processes.read','processes.manage'));
""")
