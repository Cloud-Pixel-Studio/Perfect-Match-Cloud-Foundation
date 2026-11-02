"""Preserve optional CAPA external source references as frozen provenance."""

from alembic import op

revision = "0036_capa_source_reference"
down_revision = "0035_capa_cancellation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
ALTER TABLE qms_capas ADD COLUMN source_reference varchar(160) NOT NULL DEFAULT '';
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_source_reference_trimmed
 CHECK (source_reference=btrim(source_reference));
CREATE FUNCTION validate_qms_capa_source_reference() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.state<>'draft' AND NEW.source_reference IS DISTINCT FROM OLD.source_reference THEN
  RAISE EXCEPTION 'CAPA source reference is frozen after draft' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_capa_source_reference() FROM PUBLIC;
CREATE TRIGGER qms_capa_source_reference_validate BEFORE UPDATE ON qms_capas
 FOR EACH ROW EXECUTE FUNCTION validate_qms_capa_source_reference();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_capas DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas WHERE source_reference<>'') THEN
  RAISE EXCEPTION 'cannot discard CAPA source references';
 END IF;
END $$;
ALTER TABLE qms_capas ENABLE ROW LEVEL SECURITY;
DROP TRIGGER qms_capa_source_reference_validate ON qms_capas;
DROP FUNCTION validate_qms_capa_source_reference();
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_source_reference_trimmed;
ALTER TABLE qms_capas DROP COLUMN source_reference;
""")
