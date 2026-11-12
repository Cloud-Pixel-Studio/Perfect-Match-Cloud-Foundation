# ruff: noqa: E501
"""Validate document ownership and active process scope in PostgreSQL."""

from alembic import op

revision = "0014_document_owner_scope"
down_revision = "0013_document_obsolescence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE FUNCTION validate_qms_document_scope() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='INSERT' AND NOT EXISTS (
  SELECT 1 FROM public.qms_processes p
  WHERE p.id=NEW.process_id AND p.tenant_id=NEW.tenant_id
   AND p.unit_id=NEW.unit_id AND p.status='active') THEN
  RAISE EXCEPTION 'document requires an active process in the same scope' USING ERRCODE='23514';
 END IF;
 IF NEW.owner_user_id IS NOT NULL
  AND (TG_OP='INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id)
  AND NOT EXISTS (
   SELECT 1 FROM public.organization_member_directory() d
   WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'document owner must be an active tenant member' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_document_scope() FROM PUBLIC;
CREATE TRIGGER qms_document_scope_validate BEFORE INSERT OR UPDATE ON qms_documents
 FOR EACH ROW EXECUTE FUNCTION validate_qms_document_scope();
""")


def downgrade() -> None:
    op.execute(r"""
DROP TRIGGER qms_document_scope_validate ON qms_documents;
DROP FUNCTION validate_qms_document_scope();
""")
