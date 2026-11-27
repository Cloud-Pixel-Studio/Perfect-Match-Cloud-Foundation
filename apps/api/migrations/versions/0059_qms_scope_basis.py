# ruff: noqa: E501 -- migration SQL
"""Snapshot reviewed context and party requirements considered in QMS scope."""

from alembic import op

revision = "0059_qms_scope_basis"
down_revision = "0058_qms_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE public.qms_context_records
 ADD COLUMN scope_basis jsonb NOT NULL DEFAULT '[]'::jsonb,
 ADD CONSTRAINT qms_scope_basis_kind CHECK(kind='qms-scope' OR scope_basis='[]'::jsonb);

CREATE FUNCTION public.snapshot_qms_scope_basis() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 item jsonb;
 source_row jsonb;
 source_id text;
 requirement_id text;
 requirement_statement text;
 source_kind text;
 source_version integer;
 reference_key text;
 keys text[] := ARRAY['record_id','source_version','requirement_id'];
 seen text[] := ARRAY[]::text[];
 assembled jsonb := '[]'::jsonb;
 uuid_pattern constant text := '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$';
BEGIN
 IF NEW.kind<>'qms-scope' THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND NEW.scope_basis IS NOT DISTINCT FROM OLD.scope_basis THEN RETURN NEW; END IF;
 IF jsonb_typeof(NEW.scope_basis) IS DISTINCT FROM 'array' THEN
  RAISE EXCEPTION 'scope basis must be an array' USING ERRCODE='23514';
 END IF;
 IF jsonb_array_length(NEW.scope_basis)>20 THEN
  RAISE EXCEPTION 'too many scope basis references' USING ERRCODE='23514';
 END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(NEW.scope_basis) LOOP
  IF jsonb_typeof(item)<>'object' OR NOT (item ?& keys) OR item-keys<>'{}'::jsonb
   OR jsonb_typeof(item->'record_id')<>'string' OR jsonb_typeof(item->'source_version')<>'number'
   OR jsonb_typeof(item->'requirement_id') NOT IN ('null','string')
  THEN RAISE EXCEPTION 'invalid scope basis reference' USING ERRCODE='23514'; END IF;
  source_id:=item->>'record_id';
  requirement_id:=item->>'requirement_id';
  IF source_id !~ uuid_pattern OR (requirement_id IS NOT NULL AND requirement_id !~ uuid_pattern)
   OR (item->>'source_version') !~ '^[1-9][0-9]{0,9}$'
  THEN RAISE EXCEPTION 'invalid scope basis identity or version' USING ERRCODE='23514'; END IF;
  IF (item->>'source_version')::bigint>=2147483647 THEN
   RAISE EXCEPTION 'invalid scope basis version' USING ERRCODE='23514';
  END IF;
  source_version:=(item->>'source_version')::integer;
  reference_key:=source_id || '/' || coalesce(requirement_id,'');
  IF reference_key=ANY(seen) THEN
   RAISE EXCEPTION 'duplicate scope basis reference' USING ERRCODE='23514';
  END IF;
  seen:=array_append(seen,reference_key);

  SELECT revision.snapshot INTO source_row FROM public.qms_context_revisions AS revision
   WHERE revision.record_id=source_id::uuid AND revision.tenant_id=NEW.tenant_id
   AND revision.unit_id=NEW.unit_id AND revision.row_version=source_version AND revision.command='reviewed';
  source_kind:=source_row->>'kind';
  requirement_statement:=NULL;
  IF source_kind='interested-parties' AND requirement_id IS NOT NULL THEN
   SELECT entry->>'statement' INTO requirement_statement
    FROM jsonb_array_elements(coalesce(source_row->'party_requirements','[]'::jsonb)) AS entry
    WHERE entry->>'id'=requirement_id AND entry->>'disposition'='addressed_by_qms';
  END IF;
  IF source_kind IS NULL OR NOT (
   (source_kind='issues' AND requirement_id IS NULL)
   OR (source_kind='interested-parties' AND requirement_statement IS NOT NULL)
  ) THEN RAISE EXCEPTION 'reviewed scope basis source unavailable in this unit' USING ERRCODE='23514'; END IF;
  assembled:=assembled||jsonb_build_array(item||jsonb_build_object(
   'kind',source_kind,'code',source_row->>'code','name',source_row->>'name',
   'requirement_statement',requirement_statement
  ));
 END LOOP;
 NEW.scope_basis:=assembled;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION public.snapshot_qms_scope_basis() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER context_validate_scope_basis BEFORE INSERT OR UPDATE ON public.qms_context_records
 FOR EACH ROW EXECUTE FUNCTION public.snapshot_qms_scope_basis();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_context_records NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_revisions NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_context_records WHERE scope_basis<>'[]'::jsonb)
 OR EXISTS(SELECT 1 FROM public.qms_context_revisions WHERE snapshot->'scope_basis'<>'[]'::jsonb)
 THEN RAISE EXCEPTION 'cannot discard QMS scope basis history' USING ERRCODE='55000';
 END IF;
END $$;
ALTER TABLE public.qms_context_records FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_revisions FORCE ROW LEVEL SECURITY;
DROP TRIGGER context_validate_scope_basis ON public.qms_context_records;
DROP FUNCTION public.snapshot_qms_scope_basis();
ALTER TABLE public.qms_context_records DROP CONSTRAINT qms_scope_basis_kind, DROP COLUMN scope_basis;
""")
