# ruff: noqa: E501 -- migration SQL
"""Store the declared QMS scope as a reviewed context record."""

from alembic import op

revision = "0058_qms_scope"
down_revision = "0057_qms_party_risk_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE FUNCTION public.valid_qms_scope_definition(definition jsonb, boundaries text, approved boolean)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE STRICT
SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 fields text[] := ARRAY['products_services','basis','applicability','non_applicability'];
 blank constant text := U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF';
 decision text;
BEGIN
 IF btrim(boundaries,blank)='' OR jsonb_typeof(definition)<>'object' OR NOT (definition ?& fields)
  OR definition-fields<>'{}'::jsonb
 THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM unnest(fields) AS f(name)
  WHERE jsonb_typeof(definition->f.name)<>'string'
   OR length(definition->>f.name)>4000
   OR definition->>f.name<>btrim(definition->>f.name,blank))
 THEN RETURN false; END IF;
 decision:=definition->>'applicability';
 RETURN decision IN ('undecided','all_applicable','exceptions')
  AND (decision='exceptions' OR definition->>'non_applicability'='')
  AND (NOT approved OR (decision<>'undecided'
   AND definition->>'products_services'<>''
   AND definition->>'basis'<>''
   AND (decision<>'exceptions' OR definition->>'non_applicability'<>'')));
END; $$;
REVOKE ALL ON FUNCTION public.valid_qms_scope_definition(jsonb,text,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.valid_qms_scope_definition(jsonb,text,boolean) TO pmcloud_app;
""")
    op.execute("""
ALTER TABLE public.qms_context_records
 DROP CONSTRAINT qms_context_records_kind_check,
 DROP CONSTRAINT qms_context_records_check,
 ADD COLUMN scope_definition jsonb,
 ADD CONSTRAINT qms_context_records_kind_check CHECK(kind IN ('issues','interested-parties','qms-scope')),
 ADD CONSTRAINT qms_context_records_check CHECK(
 (kind='issues' AND classification IN ('internal','external')
  AND category IN ('legal','regulatory','technology','market','culture','economic','social','environmental','strategic','other'))
 OR (kind='interested-parties' AND category=''
  AND classification IN ('customer','employee','supplier','regulator','owner','community','other'))
 OR (kind='qms-scope' AND classification='declared_scope' AND category='' AND relevance='relevant'
  AND code='QMS-SCOPE' AND requirements='' AND evidence_summary='' AND status<>'retired')
 ),
 ADD CONSTRAINT qms_context_scope_definition CHECK(
  (kind='qms-scope' AND scope_definition IS NOT NULL
   AND public.valid_qms_scope_definition(scope_definition,description,status='active'))
  OR (kind<>'qms-scope' AND scope_definition IS NULL)
 );
CREATE UNIQUE INDEX qms_context_one_declared_scope
 ON public.qms_context_records(tenant_id,unit_id) WHERE kind='qms-scope';
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_context_records NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_context_records WHERE kind='qms-scope') THEN
  RAISE EXCEPTION 'cannot discard declared QMS scope history' USING ERRCODE='55000';
 END IF;
END $$;
ALTER TABLE public.qms_context_records FORCE ROW LEVEL SECURITY;
DROP INDEX public.qms_context_one_declared_scope;
ALTER TABLE public.qms_context_records
 DROP CONSTRAINT qms_context_scope_definition,
 DROP CONSTRAINT qms_context_records_kind_check,
 DROP CONSTRAINT qms_context_records_check,
 DROP COLUMN scope_definition,
 ADD CONSTRAINT qms_context_records_kind_check CHECK(kind IN ('issues','interested-parties')),
 ADD CONSTRAINT qms_context_records_check CHECK(
 (kind='issues' AND classification IN ('internal','external')
  AND category IN ('legal','regulatory','technology','market','culture','economic','social','environmental','strategic','other'))
 OR (kind='interested-parties' AND category=''
  AND classification IN ('customer','employee','supplier','regulator','owner','community','other'))
 );
DROP FUNCTION public.valid_qms_scope_definition(jsonb,text,boolean);
""")
