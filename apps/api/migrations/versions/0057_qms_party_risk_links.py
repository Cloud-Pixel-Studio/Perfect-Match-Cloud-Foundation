# ruff: noqa: E501 -- migration SQL
"""Assessed risk and opportunity citations for party requirements."""

from alembic import op

revision = "0057_qms_party_risk_links"
down_revision = "0056_qms_party_evidence_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE TABLE public.qms_party_risk_links (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 unit_id uuid NOT NULL,
 party_id uuid NOT NULL,
 requirement_id uuid NOT NULL,
 risk_id uuid NOT NULL,
 linked_party_version integer NOT NULL CHECK(linked_party_version>1),
 risk_version integer NOT NULL CHECK(risk_version>0),
 requirement_snapshot jsonb NOT NULL,
 risk_code varchar(40) NOT NULL,
 risk_name varchar(160) NOT NULL,
 risk_type varchar(20) NOT NULL CHECK(risk_type IN ('risk','opportunity')),
 linked_risk_state varchar(20) NOT NULL CHECK(linked_risk_state IN ('assessed','action_required','monitoring')),
 rationale varchar(600) NOT NULL,
 created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 removed_party_version integer CHECK(removed_party_version>linked_party_version),
 removed_by_user_id uuid REFERENCES public.users(id) ON DELETE RESTRICT,
 removed_at timestamptz,
 removal_reason varchar(600) NOT NULL DEFAULT '',
 FOREIGN KEY(party_id,tenant_id,unit_id)
   REFERENCES public.qms_context_records(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(risk_id,tenant_id,unit_id)
   REFERENCES public.qms_risks(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((removed_at IS NULL AND removed_party_version IS NULL AND removed_by_user_id IS NULL AND removal_reason='')
    OR (removed_at IS NOT NULL AND removed_party_version IS NOT NULL AND removed_by_user_id IS NOT NULL AND removal_reason<>''))
);
CREATE UNIQUE INDEX qms_party_risk_one_active
 ON public.qms_party_risk_links(party_id,requirement_id,risk_id) WHERE removed_at IS NULL;
CREATE INDEX qms_party_risk_scope
 ON public.qms_party_risk_links(tenant_id,unit_id,party_id,created_at DESC,id);

REVOKE ALL ON public.qms_party_risk_links FROM PUBLIC,pmcloud_app;
GRANT SELECT,INSERT,UPDATE(removed_party_version,removal_reason) ON public.qms_party_risk_links TO pmcloud_app;
ALTER TABLE public.qms_party_risk_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qms_party_risk_links FORCE ROW LEVEL SECURITY;
CREATE POLICY party_risk_read ON public.qms_party_risk_links FOR SELECT TO pmcloud_app USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('risks.read',unit_id)
);
CREATE POLICY party_risk_add ON public.qms_party_risk_links FOR INSERT TO pmcloud_app WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('risks.read',unit_id)
);
CREATE POLICY party_risk_remove ON public.qms_party_risk_links FOR UPDATE TO pmcloud_app USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('risks.read',unit_id)
) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('risks.read',unit_id)
);

CREATE FUNCTION public.validate_qms_party_risk_link() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 party public.qms_context_records%ROWTYPE;
 actor uuid := NULLIF(current_setting('app.user_id',true),'')::uuid;
 command text := current_setting('app.qms_party_risk_command',true);
 blank constant text := U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF';
BEGIN
 IF actor IS NULL OR NOT public.qms_has_capability('context.read',NEW.unit_id)
  OR NOT public.qms_has_capability('context.manage',NEW.unit_id)
  OR NOT public.qms_has_capability('risks.read',NEW.unit_id)
 THEN RAISE EXCEPTION 'party and risk authority required' USING ERRCODE='42501'; END IF;
 IF current_setting('app.qms_context_command',true) IS DISTINCT FROM 'updated'
 OR command IS DISTINCT FROM (CASE WHEN TG_OP='INSERT' THEN 'link' ELSE 'remove' END)
 THEN RAISE EXCEPTION 'controlled party risk command required' USING ERRCODE='23514'; END IF;
 SELECT * INTO party FROM public.qms_context_records
  WHERE id=NEW.party_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id
  AND kind='interested-parties' FOR UPDATE;
 IF party.id IS NULL OR party.status='retired' OR party.row_version>=2147483647
 THEN RAISE EXCEPTION 'party scope or state conflict' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.linked_party_version<>party.row_version+1 OR NEW.removed_party_version IS NOT NULL
   OR NEW.removed_by_user_id IS NOT NULL OR NEW.removed_at IS NOT NULL OR NEW.removal_reason<>''
   OR length(btrim(NEW.rationale,blank))=0 OR NEW.rationale<>btrim(NEW.rationale,blank)
  THEN RAISE EXCEPTION 'party version, rationale or link state conflict' USING ERRCODE='23514'; END IF;
  SELECT item INTO NEW.requirement_snapshot FROM jsonb_array_elements(party.party_requirements) AS item
   WHERE item->>'id'=NEW.requirement_id::text AND item->>'disposition'='addressed_by_qms';
  IF NOT FOUND THEN RAISE EXCEPTION 'current requirement addressed by the QMS required' USING ERRCODE='23514'; END IF;
  SELECT risk.code,risk.name,risk.risk_type,risk.state
  INTO NEW.risk_code,NEW.risk_name,NEW.risk_type,NEW.linked_risk_state
  FROM public.qms_risks AS risk
  WHERE risk.id=NEW.risk_id AND risk.tenant_id=NEW.tenant_id AND risk.unit_id=NEW.unit_id
   AND risk.state IN ('assessed','action_required','monitoring') AND risk.row_version=NEW.risk_version;
  IF NOT FOUND THEN RAISE EXCEPTION 'current eligible risk version required' USING ERRCODE='23514'; END IF;
  NEW.created_by_user_id:=actor; NEW.created_at:=clock_timestamp();
 ELSE
  IF OLD.removed_at IS NOT NULL OR NEW.removed_party_version<>party.row_version+1
   OR NEW.removed_party_version IS NULL OR length(btrim(NEW.removal_reason,blank))=0
   OR NEW.removal_reason<>btrim(NEW.removal_reason,blank)
   OR (to_jsonb(NEW)-ARRAY['removed_party_version','removal_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['removed_party_version','removal_reason'])
  THEN RAISE EXCEPTION 'immutable party risk link; only a reasoned withdrawal is allowed' USING ERRCODE='23514'; END IF;
  NEW.removed_by_user_id:=actor; NEW.removed_at:=clock_timestamp();
 END IF;
 UPDATE public.qms_context_records SET row_version=party.row_version+1 WHERE id=party.id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION public.validate_qms_party_risk_link() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER party_risk_validate BEFORE INSERT OR UPDATE ON public.qms_party_risk_links
 FOR EACH ROW EXECUTE FUNCTION public.validate_qms_party_risk_link();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_party_risk_links NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_party_risk_links) THEN
  RAISE EXCEPTION 'cannot discard party risk link history' USING ERRCODE='55000';
 END IF;
END $$;
DROP TABLE public.qms_party_risk_links;
DROP FUNCTION public.validate_qms_party_risk_link();
""")
