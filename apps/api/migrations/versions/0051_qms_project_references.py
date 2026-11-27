# ruff: noqa: E501, S608 -- fixed allowlisted migration SQL.
"""Typed project-step citations; source state is an observation, never approval."""

from alembic import op

revision = "0051_qms_project_references"
down_revision = "0050_qms_projects"
branch_labels = None
depends_on = None

ACTIONS = tuple(
    f"qms_project.{kind}_{command}"
    for kind in ("document", "evidence")
    for command in ("linked", "unlinked")
)
BLANK = r"U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000\FEFF'"


def audit_constraint(*, remove: bool = False) -> None:
    entries = ",".join(f"''{a}''" for a in ACTIONS)
    op.execute(f"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
 WHERE conrelid='public.audit_events'::regclass AND conname='audit_events_action_check';
 EXECUTE 'ALTER TABLE public.audit_events DROP CONSTRAINT audit_events_action_check';
 definition:=left(definition,length(definition)-1)||' {"AND" if remove else "OR"} action {"NOT IN" if remove else "IN"} ({entries}))';
 EXECUTE 'ALTER TABLE public.audit_events ADD CONSTRAINT audit_events_action_check '||definition;
END $$;
""")


def upgrade() -> None:
    audit_constraint()
    op.execute(
        "ALTER TABLE public.qms_project_steps ADD CONSTRAINT qms_project_step_reference_scope UNIQUE(id,project_id,tenant_id,unit_id)"
    )
    for kind in ("document", "evidence"):
        table = f"qms_project_{kind}_links"
        cap = "documents.read" if kind == "document" else "control_instances.read"
        target = "document_revision_id" if kind == "document" else "evidence_id"
        columns = (
            """
 document_id uuid NOT NULL, document_revision_id uuid NOT NULL,
 snapshot_revision varchar(40) NOT NULL, file_sha256 varchar(64) NOT NULL CHECK(file_sha256 ~ '^[0-9a-f]{64}$'),
 linked_document_version integer NOT NULL CHECK(linked_document_version>0),
 FOREIGN KEY(document_id,tenant_id,unit_id) REFERENCES public.qms_documents(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_revision_id,document_id,tenant_id) REFERENCES public.qms_document_revisions(id,document_id,tenant_id) ON DELETE RESTRICT,
"""
            if kind == "document"
            else """
 evidence_id uuid NOT NULL, control_instance_id uuid NOT NULL,
 linked_instance_version integer NOT NULL CHECK(linked_instance_version>0),
 FOREIGN KEY(evidence_id,tenant_id,unit_id) REFERENCES public.qms_control_instance_evidence(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id) REFERENCES public.qms_control_instances(id,tenant_id,unit_id) ON DELETE RESTRICT,
"""
        )
        op.execute(f"""
CREATE TABLE public.{table} (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, project_id uuid NOT NULL, step_id uuid NOT NULL,
 target_process_id uuid NOT NULL, snapshot_code varchar(50) NOT NULL, snapshot_name varchar(200) NOT NULL,
 linked_target_version integer NOT NULL CHECK(linked_target_version>0),
 source_project_version integer NOT NULL CHECK(source_project_version>0),
 source_step_version integer NOT NULL CHECK(source_step_version>0),
 rationale varchar(500) NOT NULL CHECK(length(btrim(rationale,{BLANK})) BETWEEN 1 AND 500 AND rationale=btrim(rationale,{BLANK})),
 status varchar(20) NOT NULL CHECK(status IN ('active','removed')),
 row_version integer NOT NULL CHECK(row_version>0),
 created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT, created_at timestamptz NOT NULL,
 removed_by_user_id uuid REFERENCES public.users(id) ON DELETE RESTRICT, removed_at timestamptz,
 removal_reason varchar(500) NOT NULL DEFAULT '',
 {columns}
 FOREIGN KEY(step_id,project_id,tenant_id,unit_id) REFERENCES public.qms_project_steps(id,project_id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='active' AND removed_by_user_id IS NULL AND removed_at IS NULL AND removal_reason='') OR
 (status='removed' AND removed_by_user_id IS NOT NULL AND removed_at IS NOT NULL AND length(btrim(removal_reason,{BLANK})) BETWEEN 1 AND 500 AND removal_reason=btrim(removal_reason,{BLANK})))
);
CREATE UNIQUE INDEX {table}_active ON public.{table}(step_id,{target}) WHERE status='active';
CREATE INDEX {table}_scope ON public.{table}(tenant_id,unit_id,project_id,step_id,status,created_at DESC,id DESC);
REVOKE ALL ON public.{table} FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON public.{table} TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON public.{table} FROM pmcloud_app;
ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY; ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;
CREATE POLICY reference_read ON public.{table} FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('projects.read',unit_id) AND public.qms_has_capability('{cap}',unit_id));
CREATE POLICY reference_insert ON public.{table} FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('projects.read',unit_id) AND public.qms_has_capability('projects.manage',unit_id) AND public.qms_has_capability('{cap}',unit_id));
CREATE POLICY reference_update ON public.{table} FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('projects.read',unit_id) AND public.qms_has_capability('projects.manage',unit_id) AND public.qms_has_capability('{cap}',unit_id)) WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.qms_has_capability('projects.read',unit_id) AND public.qms_has_capability('projects.manage',unit_id) AND public.qms_has_capability('{cap}',unit_id));
""")
        source = (
            """
 SELECT d.process_id,d.code,d.title,r.revision,r.file_sha256
 INTO NEW.target_process_id,NEW.snapshot_code,NEW.snapshot_name,NEW.snapshot_revision,NEW.file_sha256
 FROM public.qms_documents d JOIN public.qms_document_revisions r ON r.document_id=d.id AND r.tenant_id=d.tenant_id
 WHERE d.id=NEW.document_id AND d.tenant_id=NEW.tenant_id AND d.unit_id=NEW.unit_id
 AND d.status='active' AND r.id=NEW.document_revision_id AND r.status='active' AND r.file_state='clean'
 AND r.file_sha256 ~ '^[0-9a-f]{64}$' AND d.row_version=NEW.linked_document_version AND r.row_version=NEW.linked_target_version;
"""
            if kind == "document"
            else """
 SELECT i.id,i.process_id,i.code,e.name INTO NEW.control_instance_id,NEW.target_process_id,NEW.snapshot_code,NEW.snapshot_name
 FROM public.qms_control_instance_evidence e JOIN public.qms_control_instances i
 ON i.id=e.control_instance_id AND i.tenant_id=e.tenant_id AND i.unit_id=e.unit_id
 WHERE e.id=NEW.evidence_id AND e.tenant_id=NEW.tenant_id AND e.unit_id=NEW.unit_id
 AND e.status='accepted' AND i.status='active' AND i.row_version=NEW.linked_instance_version AND e.row_version=NEW.linked_target_version;
"""
        )
        op.execute(f"""
CREATE FUNCTION public.validate_{table}() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE parent public.qms_projects%ROWTYPE; child public.qms_project_steps%ROWTYPE; actor uuid; stamp timestamptz;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT public.qms_has_capability('projects.read',NEW.unit_id) OR NOT public.qms_has_capability('projects.manage',NEW.unit_id)
 OR NOT public.qms_has_capability('{cap}',NEW.unit_id) THEN
 RAISE EXCEPTION 'explicit project and source authority required' USING ERRCODE='42501'; END IF;
 IF current_setting('app.qms_project_reference_command',true) IS DISTINCT FROM (CASE WHEN TG_OP='INSERT' THEN 'link' ELSE 'unlink' END) THEN
 RAISE EXCEPTION 'controlled reference command required' USING ERRCODE='23514'; END IF;
 SELECT * INTO parent FROM public.qms_projects WHERE id=NEW.project_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 SELECT * INTO child FROM public.qms_project_steps WHERE id=NEW.step_id AND project_id=NEW.project_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF parent.id IS NULL OR child.id IS NULL OR parent.status<>'open' OR parent.catalog_version<>'guided-qms-v1'
 OR NEW.source_project_version<>parent.row_version+1 OR NEW.source_step_version<>child.row_version+1 THEN
 RAISE EXCEPTION 'reference scope, catalog or versions conflict' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
 IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
 OR NEW.removed_by_user_id IS NOT NULL OR NEW.removed_at IS NOT NULL OR NEW.removal_reason<>'' THEN
 RAISE EXCEPTION 'reference must start active by current actor' USING ERRCODE='23514'; END IF;
 {source}
 IF NOT FOUND THEN RAISE EXCEPTION 'selected eligible source and versions required' USING ERRCODE='23514'; END IF;
 NEW.created_at:=clock_timestamp();
 ELSE
 IF OLD.status<>'active' OR NEW.status<>'removed' OR NEW.row_version<>OLD.row_version+1
 OR length(btrim(NEW.removal_reason,{BLANK}))=0 OR NEW.removal_reason<>btrim(NEW.removal_reason,{BLANK})
 OR NEW.removed_by_user_id IS NOT NULL OR NEW.removed_at IS NOT NULL
 OR (to_jsonb(NEW)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason','source_project_version','source_step_version'])
 IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','row_version','removed_by_user_id','removed_at','removal_reason','source_project_version','source_step_version']) THEN
 RAISE EXCEPTION 'immutable snapshot; only reasoned removal allowed' USING ERRCODE='23514'; END IF;
 NEW.removed_by_user_id:=actor; NEW.removed_at:=clock_timestamp();
 END IF;
 stamp:=greatest(clock_timestamp(),parent.updated_at+interval '1 microsecond',child.updated_at+interval '1 microsecond');
 UPDATE public.qms_projects SET row_version=NEW.source_project_version,step_write_id=child.id,updated_at=stamp WHERE id=parent.id;
 UPDATE public.qms_project_steps SET row_version=NEW.source_step_version,source_project_version=NEW.source_project_version,
 updated_by_user_id=actor,updated_at=stamp WHERE id=child.id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION public.validate_{table}() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER reference_validate BEFORE INSERT OR UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.validate_{table}();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_project_document_links NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qms_project_evidence_links NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.qms_project_document_links) OR EXISTS(SELECT 1 FROM public.qms_project_evidence_links)
 OR EXISTS(SELECT 1 FROM public.audit_events WHERE action IN ('qms_project.document_linked','qms_project.document_unlinked','qms_project.evidence_linked','qms_project.evidence_unlinked')) THEN
 RAISE EXCEPTION 'cannot discard QMS project reference history' USING ERRCODE='55000'; END IF;
END $$;
ALTER TABLE public.audit_events FORCE ROW LEVEL SECURITY;
DROP TABLE public.qms_project_document_links;
DROP TABLE public.qms_project_evidence_links;
DROP FUNCTION public.validate_qms_project_document_links();
DROP FUNCTION public.validate_qms_project_evidence_links();
ALTER TABLE public.qms_project_steps DROP CONSTRAINT qms_project_step_reference_scope;
""")
    audit_constraint(remove=True)
