# ruff: noqa: E501, S608 -- fixed migration constants build a deterministic constraint.
"""Tenant-scoped internal-audit programs and controlled planning."""

from alembic import op

revision = "0040_internal_audit_foundation"
down_revision = "0039_capa_trace_links"
branch_labels = None
depends_on = None


AUDIT_EVENT_ACTIONS = (
    "audit_program.created",
    "audit_program.updated",
    "audit_program.transitioned",
    "internal_audit.created",
    "internal_audit.updated",
    "internal_audit.transitioned",
)


def upgrade() -> None:
    event_actions = ",".join(f"''{action}''" for action in AUDIT_EVENT_ACTIONS)
    op.execute(
        rf"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
  WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_check';
 IF definition IS NULL THEN RAISE EXCEPTION 'audit event action constraint is missing'; END IF;
 EXECUTE 'ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check';
 definition:=left(definition,length(definition)-1)||' OR action IN ({event_actions}))';
 EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check '||definition;
END $$;

ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review','ncr.read','ncr.manage','ncr.review','capa.read','capa.manage','capa.review','audits.read','audits.manage','audits.execute','audits.review'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read','capa.read','audits.read','audits.execute')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read','capa.read','audits.read','audits.execute')));
$$;

CREATE TABLE qms_audit_programs (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, code varchar(40) NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 40),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 objective text NOT NULL CHECK(length(objective)<=4000), description text NOT NULL CHECK(length(description)<=4000),
 date_start date NOT NULL, date_end date NOT NULL, owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 state varchar(20) NOT NULL CHECK(state IN ('draft','approved','active','completed','cancelled')),
 cancellation_reason varchar(500) NOT NULL DEFAULT '', row_version integer NOT NULL CHECK(row_version>=1),
 approved_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, approved_at timestamptz,
 completed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, completed_at timestamptz,
 cancelled_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, cancelled_at timestamptz,
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id), FOREIGN KEY(unit_id,tenant_id) REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT,
 CHECK(date_end>=date_start), CHECK((approved_by_user_id IS NULL)=(approved_at IS NULL)),
 CHECK((completed_by_user_id IS NULL)=(completed_at IS NULL)), CHECK((cancelled_by_user_id IS NULL)=(cancelled_at IS NULL)),
 CHECK(state<>'completed' OR completed_at IS NOT NULL),
 CHECK((state='cancelled')=(cancelled_at IS NOT NULL AND length(btrim(cancellation_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_program_code_unique ON qms_audit_programs(tenant_id,lower(code));
CREATE INDEX qms_audit_program_scope ON qms_audit_programs(tenant_id,unit_id,state,date_start,id);

CREATE TABLE qms_internal_audits (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, program_id uuid,
 code varchar(40) NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 40),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 audit_type varchar(20) NOT NULL CHECK(audit_type IN ('system','process','department','special','follow_up')),
 planned_start date NOT NULL, planned_end date NOT NULL, actual_start date, actual_end date,
 objective text NOT NULL CHECK(length(btrim(objective)) BETWEEN 1 AND 4000),
 scope_summary text NOT NULL CHECK(length(scope_summary)<=4000), conclusion text NOT NULL CHECK(length(conclusion)<=4000),
 lead_auditor_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 independence_status varchar(24) NOT NULL CHECK(independence_status IN ('pending','confirmed','override')),
 independence_notes text NOT NULL CHECK(length(independence_notes)<=2000),
 independence_reviewed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, independence_reviewed_at timestamptz,
 state varchar(20) NOT NULL CHECK(state IN ('draft','planned','ready','in_progress','reporting','completed','cancelled')),
 cancellation_reason varchar(500) NOT NULL DEFAULT '', row_version integer NOT NULL CHECK(row_version>=1),
 completed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, completed_at timestamptz,
 cancelled_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, cancelled_at timestamptz,
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id), FOREIGN KEY(unit_id,tenant_id) REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT,
 FOREIGN KEY(program_id,tenant_id,unit_id) REFERENCES qms_audit_programs(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK(planned_end>=planned_start), CHECK(actual_end IS NULL OR actual_start IS NOT NULL),
 CHECK(actual_end IS NULL OR actual_end>=actual_start),
 CHECK((independence_reviewed_by_user_id IS NULL)=(independence_reviewed_at IS NULL)),
 CHECK(independence_status='pending' OR independence_reviewed_at IS NOT NULL),
 CHECK(independence_status<>'override' OR length(btrim(independence_notes))>0),
 CHECK(state<>'completed' OR (completed_at IS NOT NULL AND length(btrim(conclusion))>0)),
 CHECK((state='cancelled')=(cancelled_at IS NOT NULL AND length(btrim(cancellation_reason))>0))
);
CREATE UNIQUE INDEX qms_internal_audit_code_unique ON qms_internal_audits(tenant_id,lower(code));
CREATE INDEX qms_internal_audit_scope ON qms_internal_audits(tenant_id,unit_id,state,planned_start,id);

REVOKE ALL ON qms_audit_programs,qms_internal_audits FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_audit_programs,qms_internal_audits TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_audit_programs,qms_internal_audits FROM pmcloud_app;
ALTER TABLE qms_audit_programs ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_audit_programs FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_internal_audits ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_internal_audits FORCE ROW LEVEL SECURITY;

CREATE POLICY qms_audit_program_read ON qms_audit_programs FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND
 qms_has_capability('audits.read',unit_id));
CREATE POLICY qms_audit_program_insert ON qms_audit_programs FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id)
 AND qms_has_capability('audits.manage',unit_id)
 AND state='draft' AND row_version=1 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_audit_program_update ON qms_audit_programs FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND
 (qms_has_capability('audits.manage',unit_id) OR qms_has_capability('audits.review',unit_id)))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND
 (qms_has_capability('audits.manage',unit_id) OR qms_has_capability('audits.review',unit_id)));

CREATE POLICY qms_internal_audit_read ON qms_internal_audits FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND
 qms_has_capability('audits.read',unit_id));
CREATE POLICY qms_internal_audit_insert ON qms_internal_audits FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id)
 AND qms_has_capability('audits.manage',unit_id)
 AND state='draft' AND independence_status='pending' AND row_version=1
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_internal_audit_update ON qms_internal_audits FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND
 (qms_has_capability('audits.manage',unit_id) OR qms_has_capability('audits.review',unit_id)))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND
 (qms_has_capability('audits.manage',unit_id) OR qms_has_capability('audits.review',unit_id)));

CREATE FUNCTION validate_qms_audit_program() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; command boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.approved_at IS NOT NULL OR NEW.completed_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
   RAISE EXCEPTION 'audit program must start as draft by current actor' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.code,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.code,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'audit program identity or version is invalid' USING ERRCODE='23514'; END IF;
  IF OLD.state IN ('completed','cancelled') THEN RAISE EXCEPTION 'terminated audit program is immutable' USING ERRCODE='23514'; END IF;
  command:=current_setting('app.audit_program_workflow',true)='transition';
  IF command THEN
   IF NOT qms_has_capability('audits.review',NEW.unit_id) THEN RAISE EXCEPTION 'audit review authority required' USING ERRCODE='42501'; END IF;
   IF (to_jsonb(NEW)-ARRAY['state','approved_by_user_id','approved_at','completed_by_user_id','completed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','approved_by_user_id','approved_at','completed_by_user_id','completed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','row_version','updated_at']) THEN
    RAISE EXCEPTION 'audit program workflow cannot edit content' USING ERRCODE='23514'; END IF;
   IF NOT ((OLD.state='draft' AND NEW.state IN ('approved','cancelled')) OR (OLD.state='approved' AND NEW.state IN ('active','cancelled')) OR (OLD.state='active' AND NEW.state IN ('completed','cancelled'))) THEN
    RAISE EXCEPTION 'invalid audit program transition' USING ERRCODE='23514'; END IF;
  ELSE
   IF NEW.state IS DISTINCT FROM OLD.state OR ROW(NEW.approved_by_user_id,NEW.approved_at,NEW.completed_by_user_id,NEW.completed_at,NEW.cancelled_by_user_id,NEW.cancelled_at,NEW.cancellation_reason)
    IS DISTINCT FROM ROW(OLD.approved_by_user_id,OLD.approved_at,OLD.completed_by_user_id,OLD.completed_at,OLD.cancelled_by_user_id,OLD.cancelled_at,OLD.cancellation_reason) THEN
    RAISE EXCEPTION 'use audit program workflow commands' USING ERRCODE='23514'; END IF;
   IF NOT qms_has_capability('audits.manage',NEW.unit_id) THEN RAISE EXCEPTION 'audit management authority required' USING ERRCODE='42501'; END IF;
  END IF;
 END IF;
 IF NEW.owner_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'audit program owner must be active tenant member' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_audit_program_validate BEFORE INSERT OR UPDATE ON qms_audit_programs FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_program();

CREATE FUNCTION validate_qms_internal_audit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; command boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.independence_status<>'pending' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.completed_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
   RAISE EXCEPTION 'internal audit must start as draft by current actor' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.code,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.code,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'internal audit identity or version is invalid' USING ERRCODE='23514'; END IF;
  IF OLD.state IN ('completed','cancelled') THEN RAISE EXCEPTION 'terminated internal audit is immutable' USING ERRCODE='23514'; END IF;
  command:=current_setting('app.internal_audit_workflow',true)='transition';
  IF command THEN
   IF NOT qms_has_capability(CASE WHEN OLD.state='draft' AND NEW.state='planned' THEN 'audits.manage' ELSE 'audits.review' END,NEW.unit_id) THEN
    RAISE EXCEPTION 'internal audit workflow authority required' USING ERRCODE='42501'; END IF;
   IF (to_jsonb(NEW)-ARRAY['state','actual_start','actual_end','completed_by_user_id','completed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','actual_start','actual_end','completed_by_user_id','completed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','row_version','updated_at']) THEN
    RAISE EXCEPTION 'internal audit workflow cannot edit content' USING ERRCODE='23514'; END IF;
   IF NOT ((OLD.state='draft' AND NEW.state IN ('planned','cancelled')) OR (OLD.state='planned' AND NEW.state='cancelled')) THEN
    RAISE EXCEPTION 'workflow transition belongs to a later internal-audit slice' USING ERRCODE='23514'; END IF;
  ELSE
   IF NEW.state IS DISTINCT FROM OLD.state OR ROW(NEW.actual_start,NEW.actual_end,NEW.completed_by_user_id,NEW.completed_at,NEW.cancelled_by_user_id,NEW.cancelled_at,NEW.cancellation_reason)
    IS DISTINCT FROM ROW(OLD.actual_start,OLD.actual_end,OLD.completed_by_user_id,OLD.completed_at,OLD.cancelled_by_user_id,OLD.cancelled_at,OLD.cancellation_reason) THEN
    RAISE EXCEPTION 'use internal audit workflow commands' USING ERRCODE='23514'; END IF;
   IF NOT qms_has_capability('audits.manage',NEW.unit_id) THEN RAISE EXCEPTION 'audit management authority required' USING ERRCODE='42501'; END IF;
  END IF;
 END IF;
 IF NEW.program_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM qms_audit_programs p WHERE p.id=NEW.program_id AND p.tenant_id=NEW.tenant_id AND p.unit_id=NEW.unit_id AND p.state<>'cancelled') THEN
  RAISE EXCEPTION 'audit program scope or state is invalid' USING ERRCODE='23514'; END IF;
 IF NEW.lead_auditor_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.lead_auditor_user_id) THEN
  RAISE EXCEPTION 'lead auditor must be active tenant member' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_internal_audit_validate BEFORE INSERT OR UPDATE ON qms_internal_audits FOR EACH ROW EXECUTE FUNCTION validate_qms_internal_audit();
"""
    )


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_audit_programs DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_internal_audits DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_programs) OR EXISTS(SELECT 1 FROM qms_internal_audits)
  OR EXISTS(SELECT 1 FROM audit_events WHERE action LIKE 'audit_program.%' OR action LIKE 'internal_audit.%') THEN
  RAISE EXCEPTION 'cannot discard internal audit operational history'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TABLE qms_internal_audits,qms_audit_programs;
DROP FUNCTION validate_qms_internal_audit(); DROP FUNCTION validate_qms_audit_program();

ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review','ncr.read','ncr.manage','ncr.review','capa.read','capa.manage','capa.review'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514'; END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read','capa.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514'; END IF;
 END IF; RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND g.unit_id=requested_unit
 AND g.capability=requested_capability AND g.status='active' AND unit.status='active' AND m.status='active'
 AND u.status='active' AND t.status='active' AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read','capa.read')));
$$;
""")
    op.execute(
        r"""
DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
  WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_check';
 EXECUTE 'ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check';
 definition:=regexp_replace(definition,
  ' OR \(\(action\)::text = ANY \(\(ARRAY\[.*\]\)::text\[\]\)\)\)\)$','))');
 EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check '||definition;
END $$;
"""
    )
