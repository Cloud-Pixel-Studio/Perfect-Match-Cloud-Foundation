# ruff: noqa: E501, S608 -- fixed security migration SQL and frozen catalog literals.
"""Versioned scoped QMS project planning; reported work is never verified evidence."""

from alembic import op

revision = "0050_qms_projects"
down_revision = "0049_tenant_suspension"
branch_labels = None
depends_on = None

PROJECT_ACTIONS = (
    "qms_project.created",
    "qms_project.updated",
    "qms_project.archived",
    "qms_project.restored",
    "qms_project_step.updated",
)

# Frozen independently of future runtime catalog edits.
CATALOG_ROWS = (
    ("guided-qms-v1", "initial", "process-map", 1, False),
    ("guided-qms-v1", "initial", "normative-profile", 2, True),
    ("guided-qms-v1", "initial", "document-control", 3, False),
    ("guided-qms-v1", "initial", "control-implementation", 4, False),
    ("guided-qms-v1", "initial", "risk-response", 5, False),
    ("guided-qms-v1", "initial", "people-and-performance", 6, True),
    ("guided-qms-v1", "initial", "audit-plan", 7, False),
    ("guided-qms-v1", "initial", "management-review", 8, True),
    ("guided-qms-v1", "improve", "existing-baseline", 1, False),
    ("guided-qms-v1", "improve", "change-impact", 2, True),
    ("guided-qms-v1", "improve", "document-control", 3, False),
    ("guided-qms-v1", "improve", "control-implementation", 4, False),
    ("guided-qms-v1", "improve", "risk-response", 5, False),
    ("guided-qms-v1", "improve", "corrective-follow-up", 6, False),
    ("guided-qms-v1", "improve", "accept-change", 7, True),
    ("guided-qms-v1", "transition", "source-baseline", 1, True),
    ("guided-qms-v1", "transition", "normative-profile", 2, True),
    ("guided-qms-v1", "transition", "edition-comparison", 3, True),
    ("guided-qms-v1", "transition", "control-implementation", 4, False),
    ("guided-qms-v1", "transition", "document-control", 5, False),
    ("guided-qms-v1", "transition", "risk-response", 6, False),
    ("guided-qms-v1", "transition", "audit-plan", 7, False),
    ("guided-qms-v1", "transition", "transition-decision", 8, True),
    ("guided-qms-v1", "migrate", "source-inventory", 1, True),
    ("guided-qms-v1", "migrate", "process-map", 2, False),
    ("guided-qms-v1", "migrate", "trial-import", 3, True),
    ("guided-qms-v1", "migrate", "manual-document-entry", 4, False),
    ("guided-qms-v1", "migrate", "control-implementation", 5, False),
    ("guided-qms-v1", "migrate", "reconcile-migration", 6, True),
    ("guided-qms-v1", "audit", "audit-plan", 1, False),
    ("guided-qms-v1", "audit", "audit-information", 2, False),
    ("guided-qms-v1", "audit", "control-implementation", 3, False),
    ("guided-qms-v1", "audit", "risk-response", 4, False),
    ("guided-qms-v1", "audit", "nonconformity-follow-up", 5, False),
    ("guided-qms-v1", "audit", "corrective-follow-up", 6, False),
    ("guided-qms-v1", "audit", "management-review", 7, True),
    ("guided-qms-v1", "audit", "execute-audit", 8, True),
    ("guided-qms-v1", "expand", "new-boundaries", 1, False),
    ("guided-qms-v1", "expand", "normative-profile", 2, True),
    ("guided-qms-v1", "expand", "risk-response", 3, False),
    ("guided-qms-v1", "expand", "document-control", 4, False),
    ("guided-qms-v1", "expand", "control-implementation", 5, False),
    ("guided-qms-v1", "expand", "audit-plan", 6, False),
    ("guided-qms-v1", "expand", "scope-acceptance", 7, True),
)


def _extend_constraint(
    table: str, name: str, column: str, values: tuple[str, ...], *, remove: bool = False
) -> None:
    entries = ",".join(f"''{value}''" for value in values)
    operator = "AND" if remove else "OR"
    membership = "NOT IN" if remove else "IN"
    op.execute(f"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
  WHERE conrelid='{table}'::regclass AND conname='{name}';
 IF definition IS NULL THEN RAISE EXCEPTION 'required constraint missing: {name}'; END IF;
 EXECUTE 'ALTER TABLE {table} DROP CONSTRAINT {name}';
 definition:=left(definition,length(definition)-1)||' {operator} {column} {membership} ({entries}))';
 EXECUTE 'ALTER TABLE {table} ADD CONSTRAINT {name} '||definition;
END $$;
""")


def _auditor_read(*, remove: bool = False) -> None:
    # Preserve all existing grant/helper rules and extend only the auditor read allowlist.
    before = (
        "'audits.read','audits.execute','projects.read'"
        if remove
        else "'audits.read','audits.execute'"
    )
    after = (
        "'audits.read','audits.execute'"
        if remove
        else "'audits.read','audits.execute','projects.read'"
    )
    escaped_before, escaped_after = before.replace("'", "''"), after.replace("'", "''")
    for signature in ("validate_qms_access_grant()", "qms_has_capability(text,uuid)"):
        op.execute(f"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_functiondef('{signature}'::regprocedure) INTO definition;
 IF position('{escaped_before}' in definition)=0 THEN RAISE EXCEPTION 'auditor capability definition changed unexpectedly'; END IF;
 EXECUTE replace(definition,'{escaped_before}','{escaped_after}');
END $$;
""")


def upgrade() -> None:
    _extend_constraint("audit_events", "audit_events_action_check", "action", PROJECT_ACTIONS)
    _extend_constraint(
        "qms_access_grants",
        "qms_access_grants_capability_check",
        "capability",
        ("projects.read", "projects.manage"),
    )
    _auditor_read()
    op.execute("""
CREATE TABLE qms_project_catalog (
 catalog_version varchar(40) NOT NULL, journey_key varchar(20) NOT NULL,
 step_key varchar(50) NOT NULL, position integer NOT NULL CHECK(position>0),
 feature_pending boolean NOT NULL,
 PRIMARY KEY(catalog_version,journey_key,step_key), UNIQUE(catalog_version,journey_key,position)
);
REVOKE ALL ON qms_project_catalog FROM PUBLIC,pmcloud_app;
GRANT SELECT ON qms_project_catalog TO pmcloud_app;
CREATE TABLE qms_projects (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, code varchar(40) NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 40 AND code=btrim(code)),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160 AND name=btrim(name)),
 journey_key varchar(20) NOT NULL, catalog_version varchar(40) NOT NULL,
 scope_summary text NOT NULL CHECK(length(scope_summary)<=4000),
 coordinator_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, target_date date,
 status varchar(20) NOT NULL CHECK(status IN ('open','archived')),
 row_version integer NOT NULL CHECK(row_version>0), step_write_id uuid,
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(unit_id,tenant_id) REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX qms_project_code_unique ON qms_projects(tenant_id,lower(code));
CREATE INDEX qms_project_scope ON qms_projects(tenant_id,unit_id,code,id);
CREATE TABLE qms_project_steps (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, project_id uuid NOT NULL, step_key varchar(50) NOT NULL,
 position integer NOT NULL CHECK(position>0),
 status varchar(20) NOT NULL CHECK(status IN ('not_started','in_progress','blocked','reported','feature_pending')),
 notes text NOT NULL CHECK(length(notes)<=2000),
 assignee_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, target_date date,
 row_version integer NOT NULL CHECK(row_version>0), source_project_version integer NOT NULL CHECK(source_project_version>0),
 updated_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_at timestamptz NOT NULL,
 FOREIGN KEY(project_id,tenant_id,unit_id) REFERENCES qms_projects(id,tenant_id,unit_id) ON DELETE RESTRICT,
 UNIQUE(project_id,step_key), UNIQUE(project_id,position),
 CHECK(status NOT IN ('blocked','reported') OR length(btrim(notes,E' \\t\\n\\r'))>0)
);
CREATE UNIQUE INDEX qms_project_step_parent_version ON qms_project_steps(project_id,source_project_version) WHERE row_version>1;
CREATE INDEX qms_project_step_scope ON qms_project_steps(tenant_id,unit_id,project_id,position);
REVOKE ALL ON qms_projects,qms_project_steps FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_projects,qms_project_steps TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_projects,qms_project_steps FROM pmcloud_app;
ALTER TABLE qms_projects ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_projects FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_project_steps ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_project_steps FORCE ROW LEVEL SECURITY;
""")
    # Data-free templates are public to the runtime only for deterministic validation.
    for version, journey, key, position, pending in CATALOG_ROWS:
        op.execute(
            f"INSERT INTO qms_project_catalog VALUES ('{version}','{journey}','{key}',{position},{str(pending).lower()})"
        )
    for table in ("qms_projects", "qms_project_steps"):
        op.execute(f"""
CREATE POLICY project_read ON {table} FOR SELECT USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('projects.read',unit_id));
CREATE POLICY project_insert ON {table} FOR INSERT WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('projects.read',unit_id) AND qms_has_capability('projects.manage',unit_id));
CREATE POLICY project_update ON {table} FOR UPDATE USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('projects.read',unit_id) AND qms_has_capability('projects.manage',unit_id)) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('projects.read',unit_id) AND qms_has_capability('projects.manage',unit_id));
""")
    op.execute("""
CREATE FUNCTION validate_qms_project() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE actor uuid;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT public.qms_has_capability('projects.read',NEW.unit_id) OR NOT public.qms_has_capability('projects.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'project read and manage authority required' USING ERRCODE='42501'; END IF;
 PERFORM public.lock_qms_site_scope(NEW.unit_id,NEW.tenant_id);
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'open' OR NEW.row_version<>1 OR NEW.step_write_id IS NOT NULL OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.created_at IS DISTINCT FROM NEW.updated_at OR NOT EXISTS(
    SELECT 1 FROM public.qms_project_catalog WHERE catalog_version=NEW.catalog_version AND journey_key=NEW.journey_key) THEN
   RAISE EXCEPTION 'project must start with current actor and frozen catalog' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.code,NEW.journey_key,NEW.catalog_version,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.code,OLD.journey_key,OLD.catalog_version,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'project identity is immutable and version must advance once' USING ERRCODE='23514'; END IF;
  IF (OLD.status='archived' OR NEW.status<>OLD.status) AND (
   NEW.status=OLD.status OR
   (to_jsonb(NEW)-ARRAY['status','row_version','updated_at','step_write_id']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['status','row_version','updated_at','step_write_id']) OR NEW.step_write_id IS NOT NULL) THEN
   RAISE EXCEPTION 'archive and restore cannot edit project metadata' USING ERRCODE='23514'; END IF;
  IF NEW.step_write_id IS NOT NULL AND (
   (to_jsonb(NEW)-ARRAY['row_version','updated_at','step_write_id']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['row_version','updated_at','step_write_id']) OR NEW.status<>'open') THEN
   RAISE EXCEPTION 'step mutation cannot edit project metadata' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.coordinator_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.coordinator_user_id IS DISTINCT FROM OLD.coordinator_user_id)
  AND NOT EXISTS(SELECT 1 FROM public.organization_member_directory() WHERE user_id=NEW.coordinator_user_id) THEN
  RAISE EXCEPTION 'project coordinator must be an active company member' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_project() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER qms_project_validate BEFORE INSERT OR UPDATE ON qms_projects FOR EACH ROW EXECUTE FUNCTION validate_qms_project();

CREATE FUNCTION validate_qms_project_step() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE parent public.qms_projects%ROWTYPE; pending boolean; parent_xid xid; actor uuid;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT public.qms_has_capability('projects.read',NEW.unit_id) OR NOT public.qms_has_capability('projects.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'project read and manage authority required' USING ERRCODE='42501'; END IF;
 SELECT p.* INTO parent FROM public.qms_projects p
  WHERE p.id=NEW.project_id AND p.tenant_id=NEW.tenant_id AND p.unit_id=NEW.unit_id FOR UPDATE;
 SELECT xmin INTO parent_xid FROM public.qms_projects WHERE id=parent.id;
 IF parent.id IS NULL OR parent.status<>'open' THEN RAISE EXCEPTION 'step requires an open scoped project' USING ERRCODE='23514'; END IF;
 PERFORM public.lock_qms_site_scope(NEW.unit_id,NEW.tenant_id);
 SELECT feature_pending INTO pending FROM public.qms_project_catalog WHERE catalog_version=parent.catalog_version
  AND journey_key=parent.journey_key AND step_key=NEW.step_key AND position=NEW.position;
 IF pending IS NULL OR (NEW.status='feature_pending') IS DISTINCT FROM pending OR NEW.updated_by_user_id IS DISTINCT FROM actor THEN
  RAISE EXCEPTION 'step catalog, product gap or actor is invalid' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF parent.row_version<>1 OR parent_xid<>(pg_current_xact_id()::text)::xid OR NEW.row_version<>1 OR NEW.source_project_version<>1
   OR NEW.notes<>'' OR NEW.assignee_user_id IS NOT NULL OR NEW.target_date IS NOT NULL
   OR NEW.status<>(CASE WHEN pending THEN 'feature_pending' ELSE 'not_started' END) THEN
   RAISE EXCEPTION 'all steps must be generated once with their project' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.project_id,NEW.step_key,NEW.position)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.project_id,OLD.step_key,OLD.position)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at
   OR NEW.source_project_version<>parent.row_version OR NEW.source_project_version<=OLD.source_project_version
   OR parent.step_write_id IS DISTINCT FROM NEW.id OR parent_xid<>(pg_current_xact_id()::text)::xid THEN
   RAISE EXCEPTION 'step identity or atomic parent version is invalid' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.assignee_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.assignee_user_id IS DISTINCT FROM OLD.assignee_user_id)
  AND NOT EXISTS(SELECT 1 FROM public.organization_member_directory() WHERE user_id=NEW.assignee_user_id) THEN
  RAISE EXCEPTION 'step assignee must be an active company member' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_project_step() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER qms_project_step_validate BEFORE INSERT OR UPDATE ON qms_project_steps FOR EACH ROW EXECUTE FUNCTION validate_qms_project_step();

CREATE FUNCTION check_qms_project_catalog_complete() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE target uuid; parent public.qms_projects%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='qms_projects' THEN target:=NEW.id; ELSE target:=NEW.project_id; END IF;
 SELECT * INTO parent FROM public.qms_projects WHERE id=target;
 IF parent.id IS NULL OR
  (SELECT count(*) FROM public.qms_project_steps WHERE project_id=target) <>
  (SELECT count(*) FROM public.qms_project_catalog WHERE catalog_version=parent.catalog_version AND journey_key=parent.journey_key) THEN
  RAISE EXCEPTION 'project requires its entire frozen catalog step set' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='qms_projects' THEN
 IF NEW.step_write_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM public.qms_project_steps WHERE id=NEW.step_write_id AND project_id=target AND row_version>1 AND source_project_version=NEW.row_version) THEN
  RAISE EXCEPTION 'parent step version must match atomic child mutation' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NULL;
END; $$;
REVOKE ALL ON FUNCTION check_qms_project_catalog_complete() FROM PUBLIC,pmcloud_app;
CREATE CONSTRAINT TRIGGER qms_project_complete AFTER INSERT OR UPDATE ON qms_projects DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_qms_project_catalog_complete();
CREATE CONSTRAINT TRIGGER qms_project_step_complete AFTER INSERT OR UPDATE ON qms_project_steps DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_qms_project_catalog_complete();

CREATE TABLE qms_project_dependency_projection (
 id uuid PRIMARY KEY REFERENCES qms_projects(id) ON DELETE CASCADE,
 tenant_id uuid NOT NULL, unit_id uuid NOT NULL, status varchar(20) NOT NULL
);
CREATE INDEX qms_project_dependency_scope ON qms_project_dependency_projection(unit_id) WHERE status='open';
REVOKE ALL ON qms_project_dependency_projection FROM PUBLIC,pmcloud_app;
ALTER TABLE qms_project_dependency_projection ENABLE ROW LEVEL SECURITY;
CREATE FUNCTION sync_qms_project_dependencies() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 INSERT INTO public.qms_project_dependency_projection(id,tenant_id,unit_id,status) VALUES(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.status)
 ON CONFLICT(id) DO UPDATE SET status=EXCLUDED.status;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION sync_qms_project_dependencies() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER qms_project_dependencies AFTER INSERT OR UPDATE ON qms_projects FOR EACH ROW EXECUTE FUNCTION sync_qms_project_dependencies();
CREATE FUNCTION protect_unit_with_qms_projects() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF NEW.status='archived' AND OLD.status<>'archived' THEN
  PERFORM id FROM public.organization_unit_integrity_projection WHERE id=NEW.id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM public.qms_project_dependency_projection WHERE unit_id=NEW.id AND tenant_id=NEW.tenant_id AND status='open') THEN
   RAISE EXCEPTION 'unit has open QMS project dependencies' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION protect_unit_with_qms_projects() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER organization_unit_qms_project_guard BEFORE UPDATE ON organization_units FOR EACH ROW EXECUTE FUNCTION protect_unit_with_qms_projects();
""")


def downgrade() -> None:
    # Transactional owner-only visibility for the guard; no runtime policies are removed.
    op.execute("""
ALTER TABLE qms_projects NO FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_project_steps NO FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_access_grants NO FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_projects) OR EXISTS(SELECT 1 FROM qms_project_steps)
  OR EXISTS(SELECT 1 FROM qms_access_grants WHERE capability IN ('projects.read','projects.manage'))
  OR EXISTS(SELECT 1 FROM audit_events WHERE action LIKE 'qms_project.%' OR action='qms_project_step.updated'
   OR (action IN ('qms.access_granted','qms.access_revoked') AND new_values->>'capability' IN ('projects.read','projects.manage'))) THEN
  RAISE EXCEPTION 'cannot discard QMS project history' USING ERRCODE='55000'; END IF;
END $$;
ALTER TABLE qms_projects FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_project_steps FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_access_grants FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
DROP TRIGGER organization_unit_qms_project_guard ON organization_units;
DROP FUNCTION protect_unit_with_qms_projects();
DROP TABLE qms_project_dependency_projection;
DROP TABLE qms_project_steps;
DROP TABLE qms_projects;
DROP TABLE qms_project_catalog;
DROP FUNCTION validate_qms_project();
DROP FUNCTION validate_qms_project_step();
DROP FUNCTION check_qms_project_catalog_complete();
DROP FUNCTION sync_qms_project_dependencies();
""")
    _auditor_read(remove=True)
    _extend_constraint(
        "qms_access_grants",
        "qms_access_grants_capability_check",
        "capability",
        ("projects.read", "projects.manage"),
        remove=True,
    )
    _extend_constraint(
        "audit_events", "audit_events_action_check", "action", PROJECT_ACTIONS, remove=True
    )
