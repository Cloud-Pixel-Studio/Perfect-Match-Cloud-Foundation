# ruff: noqa: E501 -- migration SQL
"""Accepted control evidence citations for individual party requirements."""

from alembic import op

revision = "0056_qms_party_evidence_links"
down_revision = "0055_qms_party_document_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE TABLE public.qms_party_evidence_links (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 unit_id uuid NOT NULL,
 party_id uuid NOT NULL,
 requirement_id uuid NOT NULL,
 evidence_id uuid NOT NULL,
 control_instance_id uuid NOT NULL,
 linked_party_version integer NOT NULL CHECK(linked_party_version>1),
 instance_version integer NOT NULL CHECK(instance_version>0),
 evidence_version integer NOT NULL CHECK(evidence_version>0),
 requirement_snapshot jsonb NOT NULL,
 control_code varchar(50) NOT NULL,
 evidence_name varchar(160) NOT NULL,
 evidence_type varchar(30) NOT NULL,
 accepted_at timestamptz NOT NULL,
 rationale varchar(600) NOT NULL,
 created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 removed_party_version integer CHECK(removed_party_version>linked_party_version),
 removed_by_user_id uuid REFERENCES public.users(id) ON DELETE RESTRICT,
 removed_at timestamptz,
 removal_reason varchar(600) NOT NULL DEFAULT '',
 FOREIGN KEY(party_id,tenant_id,unit_id)
   REFERENCES public.qms_context_records(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(evidence_id,tenant_id,unit_id)
   REFERENCES public.qms_control_instance_evidence(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id)
   REFERENCES public.qms_control_instances(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((removed_at IS NULL AND removed_party_version IS NULL AND removed_by_user_id IS NULL AND removal_reason='')
    OR (removed_at IS NOT NULL AND removed_party_version IS NOT NULL AND removed_by_user_id IS NOT NULL AND removal_reason<>''))
);
CREATE UNIQUE INDEX qms_party_evidence_one_active
 ON public.qms_party_evidence_links(party_id,requirement_id,evidence_id) WHERE removed_at IS NULL;
CREATE INDEX qms_party_evidence_scope
 ON public.qms_party_evidence_links(tenant_id,unit_id,party_id,created_at DESC,id);

REVOKE ALL ON public.qms_party_evidence_links FROM PUBLIC,pmcloud_app;
GRANT SELECT,INSERT,UPDATE(removed_party_version,removal_reason) ON public.qms_party_evidence_links TO pmcloud_app;
ALTER TABLE public.qms_party_evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qms_party_evidence_links FORCE ROW LEVEL SECURITY;
CREATE POLICY party_evidence_read ON public.qms_party_evidence_links FOR SELECT TO pmcloud_app USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('control_instances.read',unit_id)
);
CREATE POLICY party_evidence_add ON public.qms_party_evidence_links FOR INSERT TO pmcloud_app WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('control_instances.read',unit_id)
);
CREATE POLICY party_evidence_remove ON public.qms_party_evidence_links FOR UPDATE TO pmcloud_app USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('control_instances.read',unit_id)
) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('control_instances.read',unit_id)
);

CREATE FUNCTION public.validate_qms_party_evidence_link() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 party public.qms_context_records%ROWTYPE;
 actor uuid := NULLIF(current_setting('app.user_id',true),'')::uuid;
 command text := current_setting('app.qms_party_evidence_command',true);
 blank constant text := U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF';
BEGIN
 IF actor IS NULL OR NOT public.qms_has_capability('context.read',NEW.unit_id)
  OR NOT public.qms_has_capability('context.manage',NEW.unit_id)
  OR NOT public.qms_has_capability('control_instances.read',NEW.unit_id)
 THEN RAISE EXCEPTION 'party and evidence authority required' USING ERRCODE='42501'; END IF;
 IF current_setting('app.qms_context_command',true) IS DISTINCT FROM 'updated'
 OR command IS DISTINCT FROM (CASE WHEN TG_OP='INSERT' THEN 'link' ELSE 'remove' END)
 THEN RAISE EXCEPTION 'controlled party evidence command required' USING ERRCODE='23514'; END IF;
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
  SELECT i.code,e.name,e.evidence_type,e.reviewed_at
  INTO NEW.control_code,NEW.evidence_name,NEW.evidence_type,NEW.accepted_at
  FROM public.qms_control_instance_evidence AS e
  JOIN public.qms_control_instances AS i ON i.id=e.control_instance_id
   AND i.tenant_id=e.tenant_id AND i.unit_id=e.unit_id
  WHERE e.id=NEW.evidence_id AND e.tenant_id=NEW.tenant_id AND e.unit_id=NEW.unit_id
   AND i.id=NEW.control_instance_id AND i.status='active' AND e.status='accepted'
   AND i.row_version=NEW.instance_version AND e.row_version=NEW.evidence_version;
  IF NOT FOUND THEN RAISE EXCEPTION 'current accepted evidence required' USING ERRCODE='23514'; END IF;
  NEW.created_by_user_id:=actor; NEW.created_at:=clock_timestamp();
 ELSE
  IF OLD.removed_at IS NOT NULL OR NEW.removed_party_version<>party.row_version+1
   OR NEW.removed_party_version IS NULL OR length(btrim(NEW.removal_reason,blank))=0
   OR NEW.removal_reason<>btrim(NEW.removal_reason,blank)
   OR (to_jsonb(NEW)-ARRAY['removed_party_version','removal_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['removed_party_version','removal_reason'])
  THEN RAISE EXCEPTION 'immutable party evidence link; only a reasoned withdrawal is allowed' USING ERRCODE='23514'; END IF;
  NEW.removed_by_user_id:=actor; NEW.removed_at:=clock_timestamp();
 END IF;
 UPDATE public.qms_context_records SET row_version=party.row_version+1 WHERE id=party.id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION public.validate_qms_party_evidence_link() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER party_evidence_validate BEFORE INSERT OR UPDATE ON public.qms_party_evidence_links
 FOR EACH ROW EXECUTE FUNCTION public.validate_qms_party_evidence_link();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_party_evidence_links NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_party_evidence_links) THEN
  RAISE EXCEPTION 'cannot discard party evidence link history' USING ERRCODE='55000';
 END IF;
END $$;
DROP TABLE public.qms_party_evidence_links;
DROP FUNCTION public.validate_qms_party_evidence_link();
""")
