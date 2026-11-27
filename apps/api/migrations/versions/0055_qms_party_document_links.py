# ruff: noqa: E501 -- migration SQL
"""Released and scanned document citations for individual party requirements."""

from alembic import op

revision = "0055_qms_party_document_links"
down_revision = "0054_qms_party_process_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE TABLE public.qms_party_document_links (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 unit_id uuid NOT NULL,
 party_id uuid NOT NULL,
 requirement_id uuid NOT NULL,
 document_id uuid NOT NULL,
 document_revision_id uuid NOT NULL,
 linked_party_version integer NOT NULL CHECK(linked_party_version>1),
 document_version integer NOT NULL CHECK(document_version>0),
 revision_version integer NOT NULL CHECK(revision_version>0),
 requirement_snapshot jsonb NOT NULL,
 document_code varchar(40) NOT NULL,
 document_title varchar(200) NOT NULL,
 revision varchar(40) NOT NULL,
 file_sha256 varchar(64) NOT NULL CHECK(file_sha256 ~ '^[0-9a-f]{64}$'),
 rationale varchar(600) NOT NULL,
 created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 removed_party_version integer CHECK(removed_party_version>linked_party_version),
 removed_by_user_id uuid REFERENCES public.users(id) ON DELETE RESTRICT,
 removed_at timestamptz,
 removal_reason varchar(600) NOT NULL DEFAULT '',
 FOREIGN KEY(party_id,tenant_id,unit_id)
   REFERENCES public.qms_context_records(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_id,tenant_id,unit_id)
   REFERENCES public.qms_documents(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_revision_id,document_id,tenant_id)
   REFERENCES public.qms_document_revisions(id,document_id,tenant_id) ON DELETE RESTRICT,
 CHECK((removed_at IS NULL AND removed_party_version IS NULL AND removed_by_user_id IS NULL AND removal_reason='')
    OR (removed_at IS NOT NULL AND removed_party_version IS NOT NULL AND removed_by_user_id IS NOT NULL AND removal_reason<>''))
);
CREATE UNIQUE INDEX qms_party_document_one_active
 ON public.qms_party_document_links(party_id,requirement_id,document_revision_id) WHERE removed_at IS NULL;
CREATE INDEX qms_party_document_scope
 ON public.qms_party_document_links(tenant_id,unit_id,party_id,created_at DESC,id);

REVOKE ALL ON public.qms_party_document_links FROM PUBLIC,pmcloud_app;
GRANT SELECT,INSERT,UPDATE(removed_party_version,removal_reason) ON public.qms_party_document_links TO pmcloud_app;
ALTER TABLE public.qms_party_document_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qms_party_document_links FORCE ROW LEVEL SECURITY;
CREATE POLICY party_document_read ON public.qms_party_document_links FOR SELECT TO pmcloud_app USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('documents.read',unit_id)
);
CREATE POLICY party_document_add ON public.qms_party_document_links FOR INSERT TO pmcloud_app WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('documents.read',unit_id)
);
CREATE POLICY party_document_remove ON public.qms_party_document_links FOR UPDATE TO pmcloud_app USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('documents.read',unit_id)
) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND public.qms_has_capability('context.read',unit_id)
 AND public.qms_has_capability('context.manage',unit_id)
 AND public.qms_has_capability('documents.read',unit_id)
);

CREATE FUNCTION public.validate_qms_party_document_link() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 party public.qms_context_records%ROWTYPE;
 actor uuid := NULLIF(current_setting('app.user_id',true),'')::uuid;
 command text := current_setting('app.qms_party_document_command',true);
 blank constant text := U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF';
BEGIN
 IF actor IS NULL OR NOT public.qms_has_capability('context.read',NEW.unit_id)
  OR NOT public.qms_has_capability('context.manage',NEW.unit_id)
  OR NOT public.qms_has_capability('documents.read',NEW.unit_id)
 THEN RAISE EXCEPTION 'party and document authority required' USING ERRCODE='42501'; END IF;
 IF current_setting('app.qms_context_command',true) IS DISTINCT FROM 'updated'
 OR command IS DISTINCT FROM (CASE WHEN TG_OP='INSERT' THEN 'link' ELSE 'remove' END)
 THEN RAISE EXCEPTION 'controlled party document command required' USING ERRCODE='23514'; END IF;
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
  SELECT d.code,d.title,r.revision,r.file_sha256
  INTO NEW.document_code,NEW.document_title,NEW.revision,NEW.file_sha256
  FROM public.qms_documents AS d
  JOIN public.qms_document_revisions AS r ON r.document_id=d.id AND r.tenant_id=d.tenant_id
  WHERE d.id=NEW.document_id AND d.tenant_id=NEW.tenant_id AND d.unit_id=NEW.unit_id
   AND d.status='active' AND d.current_revision_id=r.id AND r.id=NEW.document_revision_id
   AND r.status='active' AND r.file_state='clean' AND r.file_sha256 ~ '^[0-9a-f]{64}$'
   AND d.row_version=NEW.document_version AND r.row_version=NEW.revision_version;
  IF NOT FOUND THEN RAISE EXCEPTION 'current released clean revision required' USING ERRCODE='23514'; END IF;
  NEW.created_by_user_id:=actor; NEW.created_at:=clock_timestamp();
 ELSE
  IF OLD.removed_at IS NOT NULL OR NEW.removed_party_version<>party.row_version+1
   OR NEW.removed_party_version IS NULL OR length(btrim(NEW.removal_reason,blank))=0
   OR NEW.removal_reason<>btrim(NEW.removal_reason,blank)
   OR (to_jsonb(NEW)-ARRAY['removed_party_version','removal_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['removed_party_version','removal_reason'])
  THEN RAISE EXCEPTION 'immutable party document link; only a reasoned withdrawal is allowed' USING ERRCODE='23514'; END IF;
  NEW.removed_by_user_id:=actor; NEW.removed_at:=clock_timestamp();
 END IF;
 UPDATE public.qms_context_records SET row_version=party.row_version+1 WHERE id=party.id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION public.validate_qms_party_document_link() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER party_document_validate BEFORE INSERT OR UPDATE ON public.qms_party_document_links
 FOR EACH ROW EXECUTE FUNCTION public.validate_qms_party_document_link();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_party_document_links NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_party_document_links) THEN
  RAISE EXCEPTION 'cannot discard party document link history' USING ERRCODE='55000';
 END IF;
END $$;
DROP TABLE public.qms_party_document_links;
DROP FUNCTION public.validate_qms_party_document_link();
""")
