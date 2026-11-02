"""Require a controlled command for CAPA draft edits."""

from alembic import op

revision = "0037_capa_draft_edit_command"
down_revision = "0036_capa_source_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE FUNCTION guard_qms_capa_draft_edit_command() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.state='draft' AND NEW.state='draft'
  AND (current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'edit'
   OR NOT qms_has_capability('capa.manage',NEW.unit_id)) THEN
  RAISE EXCEPTION 'CAPA draft edits require a controlled manager command' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION guard_qms_capa_draft_edit_command() FROM PUBLIC;
CREATE TRIGGER qms_capa_draft_edit_command BEFORE UPDATE ON qms_capas
 FOR EACH ROW EXECUTE FUNCTION guard_qms_capa_draft_edit_command();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_capas DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas)
  OR EXISTS(SELECT 1 FROM audit_events WHERE action LIKE 'capa.%') THEN
  RAISE EXCEPTION 'cannot remove controlled CAPA draft edits with business history';
 END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capas ENABLE ROW LEVEL SECURITY;
DROP TRIGGER qms_capa_draft_edit_command ON qms_capas;
DROP FUNCTION guard_qms_capa_draft_edit_command();
""")
