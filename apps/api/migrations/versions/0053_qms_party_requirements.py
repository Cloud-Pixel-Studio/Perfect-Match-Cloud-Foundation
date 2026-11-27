# ruff: noqa: E501 -- migration SQL
"""Review individual interested-party requirements with the parent revision."""

from alembic import op

revision = "0053_qms_party_requirements"
down_revision = "0052_qms_context_register"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE FUNCTION public.valid_qms_party_requirements(entries jsonb, absence_reason text)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE STRICT
SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 item jsonb;
 requirement_id text;
 seen_ids text[] := ARRAY[]::text[];
 fields text[] := ARRAY['id','statement','source','disposition','rationale'];
 blank constant text := U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF';
BEGIN
 IF jsonb_typeof(entries) <> 'array' THEN RETURN false; END IF;
 IF jsonb_array_length(entries) > 20
  OR length(absence_reason) > 600 OR absence_reason <> btrim(absence_reason,blank)
  OR (jsonb_array_length(entries) > 0 AND absence_reason <> '')
 THEN RETURN false; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(entries) LOOP
  IF jsonb_typeof(item) <> 'object' OR NOT (item ?& fields) OR item-fields <> '{}'::jsonb
  THEN RETURN false; END IF;
  IF EXISTS(SELECT 1 FROM unnest(fields) AS field(name) WHERE jsonb_typeof(item->field.name)<>'string')
  THEN RETURN false; END IF;
  requirement_id := item->>'id';
  IF requirement_id !~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
   OR requirement_id = ANY(seen_ids)
   OR length(item->>'statement') NOT BETWEEN 1 AND 360
   OR item->>'statement' <> btrim(item->>'statement',blank)
   OR length(item->>'source') NOT BETWEEN 1 AND 200
   OR item->>'source' <> btrim(item->>'source',blank)
   OR item->>'disposition' NOT IN ('pending','addressed_by_qms','outside_qms')
   OR length(item->>'rationale') > 600
   OR item->>'rationale' <> btrim(item->>'rationale',blank)
   OR (item->>'disposition' <> 'pending' AND item->>'rationale' = '')
  THEN RETURN false; END IF;
  seen_ids := array_append(seen_ids,requirement_id);
 END LOOP;
 RETURN true;
END; $$;
REVOKE ALL ON FUNCTION public.valid_qms_party_requirements(jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.valid_qms_party_requirements(jsonb,text) TO pmcloud_app;

ALTER TABLE public.qms_context_records
 ADD COLUMN party_requirements jsonb NOT NULL DEFAULT '[]'::jsonb,
 ADD COLUMN no_requirements_reason varchar(600) NOT NULL DEFAULT '',
 ADD CONSTRAINT qms_party_requirements_shape CHECK (
  (kind='interested-parties' OR (party_requirements='[]'::jsonb AND no_requirements_reason=''))
  AND public.valid_qms_party_requirements(party_requirements,no_requirements_reason)
 );

CREATE FUNCTION public.require_reviewable_qms_party_requirements() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 -- This trigger runs after context_validate. Earlier reviewed rows are preserved.
 IF NEW.kind='interested-parties' AND current_setting('app.qms_context_command',true)='reviewed' THEN
  IF (NEW.party_requirements='[]'::jsonb AND NEW.no_requirements_reason='')
   OR NEW.party_requirements @> '[{"disposition":"pending"}]'::jsonb
   OR (NEW.relevance='not_relevant' AND NEW.party_requirements @> '[{"disposition":"addressed_by_qms"}]'::jsonb)
  THEN
   RAISE EXCEPTION 'interested party requirements assessment is incomplete or inconsistent' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION public.require_reviewable_qms_party_requirements() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER context_validate_party_requirements BEFORE UPDATE ON public.qms_context_records
 FOR EACH ROW EXECUTE FUNCTION public.require_reviewable_qms_party_requirements();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_context_records NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_revisions NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM public.qms_context_records
  WHERE party_requirements<>'[]'::jsonb OR no_requirements_reason<>'')
 OR EXISTS (SELECT 1 FROM public.qms_context_revisions
  WHERE coalesce(snapshot->'party_requirements','[]'::jsonb)<>'[]'::jsonb
     OR coalesce(snapshot->>'no_requirements_reason','')<>'')
 THEN RAISE EXCEPTION 'cannot discard interested party requirement history' USING ERRCODE='55000';
 END IF;
END $$;
ALTER TABLE public.qms_context_records FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_revisions FORCE ROW LEVEL SECURITY;
DROP TRIGGER context_validate_party_requirements ON public.qms_context_records;
DROP FUNCTION public.require_reviewable_qms_party_requirements();
ALTER TABLE public.qms_context_records
 DROP CONSTRAINT qms_party_requirements_shape,
 DROP COLUMN party_requirements,
 DROP COLUMN no_requirements_reason;
DROP FUNCTION public.valid_qms_party_requirements(jsonb,text);
""")
