# ruff: noqa: E501, S608 -- interpolation uses migration constants only.
"""Versioned organization context and interested parties."""

from alembic import op

revision = "0052_qms_context_register"
down_revision = "0051_qms_project_references"
branch_labels = None
depends_on = None

CAPABILITIES = ("context.read", "context.manage", "context.review")
ACTIONS = tuple(f"qms_context.{action}" for action in ("created", "updated", "reviewed", "retired"))


def extend_constraints(*, remove: bool = False) -> None:
    for table, column, values in (
        ("qms_access_grants", "capability", CAPABILITIES),
        ("audit_events", "action", ACTIONS),
    ):
        constraint = f"{table}_{column}_check"
        entries = ",".join(f"''{value}''" for value in values)
        operator, membership = ("AND", "NOT IN") if remove else ("OR", "IN")
        op.execute(f"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
 WHERE conrelid='public.{table}'::regclass AND conname='{constraint}';
 EXECUTE 'ALTER TABLE public.{table} DROP CONSTRAINT {constraint}';
 definition:=left(definition,length(definition)-1)||' {operator} {column} {membership} ({entries}))';
 EXECUTE 'ALTER TABLE public.{table} ADD CONSTRAINT {constraint} '||definition;
END $$;
""")
    base = "''audits.read'',''audits.execute'',''projects.read''"
    expanded = f"{base},''context.read''"
    before, after = (expanded, base) if remove else (base, expanded)
    for signature in ("validate_qms_access_grant()", "qms_has_capability(text,uuid)"):
        op.execute(f"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_functiondef('public.{signature}'::regprocedure) INTO definition;
 IF position('{before}' IN definition)=0 THEN
  RAISE EXCEPTION 'auditor capability definition changed unexpectedly';
 END IF;
 EXECUTE replace(definition,'{before}','{after}');
END $$;
""")


def upgrade() -> None:
    extend_constraints()
    op.execute("""
CREATE TABLE public.qms_context_records (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 unit_id uuid NOT NULL,
 kind varchar(20) NOT NULL CHECK(kind IN ('issues','interested-parties')),
 code varchar(40) NOT NULL CHECK(length(btrim(code))>0),
 name varchar(160) NOT NULL CHECK(length(btrim(name))>0),
 classification varchar(40) NOT NULL,
 category varchar(20) NOT NULL,
 relevance varchar(20) NOT NULL CHECK(relevance IN ('relevant','not_relevant','under_review')),
 description varchar(4000) NOT NULL CHECK(length(btrim(description))>0),
 requirements varchar(4000) NOT NULL,
 evidence_summary varchar(4000) NOT NULL,
 owner_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 review_due_on date NOT NULL,
 status varchar(20) NOT NULL CHECK(status IN ('draft','active','retired')),
 row_version integer NOT NULL CHECK(row_version>0),
 created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 content_editor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 updated_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 reviewed_at timestamptz,
 decision_note varchar(1000) NOT NULL,
 FOREIGN KEY(unit_id,tenant_id) REFERENCES public.organization_units(id,tenant_id) ON DELETE RESTRICT,
 UNIQUE(id,tenant_id,unit_id),
 CHECK((kind='issues' AND classification IN ('internal','external')
  AND category IN ('legal','regulatory','technology','market','culture','social','economic','environmental','strategic','other'))
  OR (kind='interested-parties' AND category=''
  AND classification IN ('customer','employee','supplier','regulator','owner','community','other'))),
 CHECK(status<>'active' OR (reviewed_at IS NOT NULL AND relevance<>'under_review')),
 CHECK(status<>'draft' OR reviewed_at IS NULL)
);
CREATE UNIQUE INDEX qms_context_code ON public.qms_context_records(tenant_id,unit_id,kind,lower(code));
CREATE INDEX qms_context_scope ON public.qms_context_records(tenant_id,unit_id,kind,code,id);

CREATE TABLE public.qms_context_revisions (
 record_id uuid NOT NULL,
 tenant_id uuid NOT NULL,
 unit_id uuid NOT NULL,
 row_version integer NOT NULL,
 command varchar(20) NOT NULL CHECK(command IN ('created','updated','reviewed','retired')),
 snapshot jsonb NOT NULL,
 PRIMARY KEY(record_id,row_version),
 FOREIGN KEY(record_id,tenant_id,unit_id)
  REFERENCES public.qms_context_records(id,tenant_id,unit_id) ON DELETE RESTRICT
);

REVOKE ALL ON public.qms_context_records,public.qms_context_revisions FROM PUBLIC,pmcloud_app;
GRANT SELECT,INSERT,UPDATE ON public.qms_context_records TO pmcloud_app;
GRANT SELECT ON public.qms_context_revisions TO pmcloud_app;
ALTER TABLE public.qms_context_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_records FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qms_context_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY context_read ON public.qms_context_records FOR SELECT TO pmcloud_app USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('context.read',unit_id));
CREATE POLICY context_insert ON public.qms_context_records FOR INSERT TO pmcloud_app WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND
 public.qms_has_capability('context.read',unit_id) AND public.qms_has_capability('context.manage',unit_id));
CREATE POLICY context_update ON public.qms_context_records FOR UPDATE TO pmcloud_app USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('context.read',unit_id)
 AND (public.qms_has_capability('context.manage',unit_id) OR public.qms_has_capability('context.review',unit_id))
) WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('context.read',unit_id)
 AND (public.qms_has_capability('context.manage',unit_id) OR public.qms_has_capability('context.review',unit_id))
);
CREATE POLICY context_history_read ON public.qms_context_revisions FOR SELECT TO pmcloud_app USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('context.read',unit_id));
CREATE POLICY context_history_append ON public.qms_context_revisions FOR INSERT TO pmcloud_migrator WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);

CREATE FUNCTION public.validate_qms_context_record() RETURNS trigger LANGUAGE plpgsql
SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid := NULLIF(current_setting('app.user_id',true),'')::uuid;
 command text := current_setting('app.qms_context_command',true);
 stamp timestamptz := clock_timestamp();
BEGIN
 IF actor IS NULL OR NOT public.qms_has_capability('context.read',NEW.unit_id)
 OR NOT public.qms_has_capability(CASE WHEN command='reviewed' THEN 'context.review' ELSE 'context.manage' END,NEW.unit_id)
 THEN RAISE EXCEPTION 'explicit context authority required' USING ERRCODE='42501'; END IF;
 IF TG_OP='INSERT' THEN
  IF command IS DISTINCT FROM 'created' THEN
   RAISE EXCEPTION 'context creation command required' USING ERRCODE='23514';
  END IF;
  NEW.row_version:=1; NEW.status:='draft'; NEW.created_by_user_id:=actor;
  NEW.content_editor_user_id:=actor; NEW.created_at:=stamp;
  NEW.reviewed_at:=NULL; NEW.decision_note:='';
 ELSE
  IF OLD.status='retired' OR NEW.row_version<>OLD.row_version+1
   OR ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.kind,NEW.created_by_user_id,NEW.created_at)
     IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.kind,OLD.created_by_user_id,OLD.created_at)
  THEN RAISE EXCEPTION 'context scope, lifecycle or version conflict' USING ERRCODE='23514'; END IF;
  IF command='updated' THEN
   NEW.status:='draft'; NEW.content_editor_user_id:=actor;
   NEW.reviewed_at:=NULL; NEW.decision_note:='';
  ELSIF command IN ('reviewed','retired') THEN
   IF (to_jsonb(NEW)-ARRAY['row_version','decision_note','review_due_on'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','decision_note','review_due_on'])
    OR length(btrim(NEW.decision_note))=0 THEN
    RAISE EXCEPTION 'context decision cannot alter record content' USING ERRCODE='23514';
   END IF;
   IF command='reviewed' THEN
    IF actor IN (OLD.created_by_user_id,OLD.content_editor_user_id) THEN
     RAISE EXCEPTION 'independent context review required' USING ERRCODE='42501';
    END IF;
    IF OLD.relevance='under_review' OR NEW.review_due_on<=(stamp AT TIME ZONE 'UTC')::date THEN
     RAISE EXCEPTION 'context review needs decided relevance and a future review date' USING ERRCODE='23514';
    END IF;
    NEW.status:='active'; NEW.reviewed_at:=stamp;
   ELSE
    NEW.status:='retired'; NEW.review_due_on:=OLD.review_due_on;
   END IF;
  ELSE
   RAISE EXCEPTION 'context update command required' USING ERRCODE='23514';
  END IF;
 END IF;
 IF command IN ('created','updated')
   AND NOT EXISTS(SELECT 1 FROM public.organization_member_directory() WHERE user_id=NEW.owner_user_id)
 THEN RAISE EXCEPTION 'responsible person must be an active company member' USING ERRCODE='23514'; END IF;
 NEW.updated_by_user_id:=actor; NEW.updated_at:=stamp;
 RETURN NEW;
END; $$;
CREATE FUNCTION public.append_qms_context_revision() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 INSERT INTO public.qms_context_revisions(record_id,tenant_id,unit_id,row_version,command,snapshot)
 VALUES(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.row_version,current_setting('app.qms_context_command'),to_jsonb(NEW));
 RETURN NULL;
END; $$;
REVOKE ALL ON FUNCTION public.validate_qms_context_record(),public.append_qms_context_revision() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER context_validate BEFORE INSERT OR UPDATE ON public.qms_context_records
 FOR EACH ROW EXECUTE FUNCTION public.validate_qms_context_record();
CREATE TRIGGER context_history AFTER INSERT OR UPDATE ON public.qms_context_records
 FOR EACH ROW EXECUTE FUNCTION public.append_qms_context_revision();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_context_records NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_access_grants NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_context_records)
 OR EXISTS(SELECT 1 FROM public.qms_access_grants WHERE capability LIKE 'context.%')
 OR EXISTS(SELECT 1 FROM public.audit_events WHERE action LIKE 'qms_context.%'
  OR (action IN ('qms.access_granted','qms.access_revoked') AND new_values->>'capability' LIKE 'context.%'))
 THEN RAISE EXCEPTION 'cannot discard QMS context history' USING ERRCODE='55000'; END IF;
END $$;
ALTER TABLE public.qms_access_grants FORCE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events FORCE ROW LEVEL SECURITY;
DROP TABLE public.qms_context_revisions;
DROP TABLE public.qms_context_records;
DROP FUNCTION public.validate_qms_context_record();
DROP FUNCTION public.append_qms_context_revision();
""")
    extend_constraints(remove=True)
