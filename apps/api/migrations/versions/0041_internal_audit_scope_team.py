# ruff: noqa: E501, S608 -- fixed migration constants build deterministic constraints.
"""Internal-audit scope, criteria, agenda, team and independence review."""

from alembic import op

revision = "0041_internal_audit_scope_team"
down_revision = "0040_internal_audit_foundation"
branch_labels = None
depends_on = None


AUDIT_EVENT_ACTIONS = (
    "audit_scope.created",
    "audit_scope.updated",
    "audit_scope.withdrawn",
    "audit_criterion.created",
    "audit_criterion.updated",
    "audit_criterion.withdrawn",
    "audit_agenda.created",
    "audit_agenda.updated",
    "audit_agenda.withdrawn",
    "audit_team_member.added",
    "audit_team_member.withdrawn",
    "internal_audit.independence_reviewed",
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

CREATE TABLE qms_audit_scopes (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL, sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 10000),
 title varchar(160) NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 description text NOT NULL CHECK(length(description)<=4000), process_id uuid, control_instance_id uuid,
 status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')), row_version integer NOT NULL CHECK(row_version>=1),
 withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, withdrawn_at timestamptz,
 withdrawal_reason varchar(500) NOT NULL DEFAULT '', created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id) REFERENCES qms_control_instances(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_scope_sequence_active_unique ON qms_audit_scopes(audit_id,sequence) WHERE status='active';
CREATE INDEX qms_audit_scope_lookup ON qms_audit_scopes(tenant_id,unit_id,audit_id,status,sequence,id);

CREATE TABLE qms_audit_criteria (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL, sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 10000),
 criterion_type varchar(40) NOT NULL CHECK(criterion_type IN ('internal_control','company_procedure','customer_requirement','regulation','external_standard_reference','other')),
 title varchar(160) NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 description text NOT NULL CHECK(length(description)<=4000), control_instance_id uuid,
 reference varchar(240) NOT NULL CHECK(length(reference)<=240), standard_identifier varchar(80) NOT NULL CHECK(length(standard_identifier)<=80),
 standard_edition varchar(40) NOT NULL CHECK(length(standard_edition)<=40), clause_reference varchar(80) NOT NULL CHECK(length(clause_reference)<=80),
 status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')), row_version integer NOT NULL CHECK(row_version>=1),
 withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, withdrawn_at timestamptz,
 withdrawal_reason varchar(500) NOT NULL DEFAULT '', created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(control_instance_id,tenant_id,unit_id) REFERENCES qms_control_instances(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((criterion_type='internal_control')=(control_instance_id IS NOT NULL)),
 CHECK(criterion_type<>'external_standard_reference' OR (length(btrim(standard_identifier))>0 AND length(btrim(clause_reference))>0)),
 CHECK(criterion_type='external_standard_reference' OR (standard_identifier='' AND standard_edition='' AND clause_reference='')),
 CHECK(criterion_type IN ('internal_control','other') OR length(btrim(reference))>0),
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_criterion_sequence_active_unique ON qms_audit_criteria(audit_id,sequence) WHERE status='active';
CREATE INDEX qms_audit_criterion_lookup ON qms_audit_criteria(tenant_id,unit_id,audit_id,status,sequence,id);

CREATE TABLE qms_audit_agenda_items (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL, sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 10000),
 scheduled_start timestamptz NOT NULL, duration_minutes integer NOT NULL CHECK(duration_minutes BETWEEN 15 AND 1440),
 process_id uuid, activity varchar(240) NOT NULL CHECK(length(btrim(activity)) BETWEEN 1 AND 240),
 auditor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 auditee_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 notes text NOT NULL CHECK(length(notes)<=4000), status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')),
 row_version integer NOT NULL CHECK(row_version>=1), withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 withdrawn_at timestamptz, withdrawal_reason varchar(500) NOT NULL DEFAULT '',
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK(auditee_user_id IS NULL OR auditee_user_id<>auditor_user_id),
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_agenda_sequence_active_unique ON qms_audit_agenda_items(audit_id,sequence) WHERE status='active';
CREATE INDEX qms_audit_agenda_lookup ON qms_audit_agenda_items(tenant_id,unit_id,audit_id,status,scheduled_start,id);

CREATE TABLE qms_audit_team_members (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL, user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 team_role varchar(20) NOT NULL CHECK(team_role IN ('lead_auditor','auditor','auditee')),
 responsibility varchar(500) NOT NULL CHECK(length(responsibility)<=500),
 status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')), row_version integer NOT NULL CHECK(row_version>=1),
 withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, withdrawn_at timestamptz,
 withdrawal_reason varchar(500) NOT NULL DEFAULT '', created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_team_user_active_unique ON qms_audit_team_members(audit_id,user_id) WHERE status='active';
CREATE UNIQUE INDEX qms_audit_team_lead_active_unique ON qms_audit_team_members(audit_id) WHERE status='active' AND team_role='lead_auditor';
CREATE INDEX qms_audit_team_lookup ON qms_audit_team_members(tenant_id,unit_id,audit_id,status,team_role,id);

REVOKE ALL ON qms_audit_scopes,qms_audit_criteria,qms_audit_agenda_items,qms_audit_team_members FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_audit_scopes,qms_audit_criteria,qms_audit_agenda_items,qms_audit_team_members TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_audit_scopes,qms_audit_criteria,qms_audit_agenda_items,qms_audit_team_members FROM pmcloud_app;
ALTER TABLE qms_audit_scopes ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_audit_scopes FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_criteria ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_audit_criteria FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_agenda_items ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_audit_agenda_items FORCE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_team_members ENABLE ROW LEVEL SECURITY; ALTER TABLE qms_audit_team_members FORCE ROW LEVEL SECURITY;

CREATE FUNCTION qms_audit_planning_row_allowed(requested_tenant uuid,requested_unit uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT requested_tenant=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('audits.read',requested_unit);
$$;
CREATE FUNCTION qms_audit_planning_write_allowed(requested_tenant uuid,requested_unit uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT qms_audit_planning_row_allowed(requested_tenant,requested_unit)
 AND qms_has_capability('audits.manage',requested_unit);
$$;

CREATE POLICY qms_audit_scope_read ON qms_audit_scopes FOR SELECT USING(qms_audit_planning_row_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_scope_insert ON qms_audit_scopes FOR INSERT WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_scope_update ON qms_audit_scopes FOR UPDATE USING(qms_audit_planning_write_allowed(tenant_id,unit_id)) WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_criterion_read ON qms_audit_criteria FOR SELECT USING(qms_audit_planning_row_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_criterion_insert ON qms_audit_criteria FOR INSERT WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_criterion_update ON qms_audit_criteria FOR UPDATE USING(qms_audit_planning_write_allowed(tenant_id,unit_id)) WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_agenda_read ON qms_audit_agenda_items FOR SELECT USING(qms_audit_planning_row_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_agenda_insert ON qms_audit_agenda_items FOR INSERT WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_agenda_update ON qms_audit_agenda_items FOR UPDATE USING(qms_audit_planning_write_allowed(tenant_id,unit_id)) WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_team_read ON qms_audit_team_members FOR SELECT USING(qms_audit_planning_row_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_team_insert ON qms_audit_team_members FOR INSERT WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));
CREATE POLICY qms_audit_team_update ON qms_audit_team_members FOR UPDATE USING(qms_audit_planning_write_allowed(tenant_id,unit_id)) WITH CHECK(qms_audit_planning_write_allowed(tenant_id,unit_id));

CREATE FUNCTION validate_qms_audit_planning_item() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; audit_state text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 SELECT state INTO audit_state FROM qms_internal_audits
  WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF audit_state IS NULL OR audit_state NOT IN ('draft','planned') THEN
  RAISE EXCEPTION 'audit planning is closed' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'audit planning item must start active by current actor' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.audit_id,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.audit_id,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at OR OLD.status<>'active' THEN
   RAISE EXCEPTION 'audit planning item identity, version or state is invalid' USING ERRCODE='23514'; END IF;
  IF NEW.status='withdrawn' THEN
   IF (to_jsonb(NEW)-ARRAY['status','withdrawn_by_user_id','withdrawn_at','withdrawal_reason','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','withdrawn_by_user_id','withdrawn_at','withdrawal_reason','row_version','updated_at'])
    OR NEW.withdrawn_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NULL OR length(btrim(NEW.withdrawal_reason))=0 THEN
    RAISE EXCEPTION 'invalid audit planning withdrawal' USING ERRCODE='23514'; END IF;
  ELSIF NEW.status<>'active' OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'use controlled audit planning withdrawal' USING ERRCODE='23514'; END IF;
 END IF;
 IF NOT qms_has_capability('audits.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'audit management authority required' USING ERRCODE='42501'; END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION validate_qms_audit_scope() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE item qms_audit_scopes; control_process uuid;
BEGIN
 item:=validate_qms_audit_planning_item();
 IF item.control_instance_id IS NOT NULL THEN
  SELECT process_id INTO control_process FROM qms_control_instances WHERE id=item.control_instance_id
   AND tenant_id=item.tenant_id AND unit_id=item.unit_id AND status='active';
  IF control_process IS NULL OR (item.process_id IS NOT NULL AND item.process_id<>control_process) THEN
   RAISE EXCEPTION 'audit scope control must be active and match process' USING ERRCODE='23514'; END IF;
 END IF;
 IF item.process_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=item.process_id AND p.tenant_id=item.tenant_id AND p.unit_id=item.unit_id AND p.status='active') THEN
  RAISE EXCEPTION 'audit scope process must be active' USING ERRCODE='23514'; END IF;
 RETURN item;
END; $$;
CREATE TRIGGER qms_audit_scope_validate BEFORE INSERT OR UPDATE ON qms_audit_scopes FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_scope();

CREATE FUNCTION validate_qms_audit_criterion() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE item qms_audit_criteria;
BEGIN
 item:=validate_qms_audit_planning_item();
 IF item.control_instance_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM qms_control_instances c WHERE c.id=item.control_instance_id AND c.tenant_id=item.tenant_id AND c.unit_id=item.unit_id AND c.status='active') THEN
  RAISE EXCEPTION 'audit criterion control must be active' USING ERRCODE='23514'; END IF;
 RETURN item;
END; $$;
CREATE TRIGGER qms_audit_criterion_validate BEFORE INSERT OR UPDATE ON qms_audit_criteria FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_criterion();

CREATE FUNCTION validate_qms_audit_agenda() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE item qms_audit_agenda_items;
BEGIN
 item:=validate_qms_audit_planning_item();
 IF item.process_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=item.process_id AND p.tenant_id=item.tenant_id AND p.unit_id=item.unit_id AND p.status='active') THEN
  RAISE EXCEPTION 'audit agenda process must be active' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=item.auditor_user_id)
  OR NOT EXISTS(SELECT 1 FROM qms_access_grants g WHERE g.tenant_id=item.tenant_id AND g.unit_id=item.unit_id AND g.user_id=item.auditor_user_id AND g.capability='audits.execute' AND g.status='active') THEN
  RAISE EXCEPTION 'agenda auditor must be active and explicitly authorized' USING ERRCODE='23514'; END IF;
 IF item.auditee_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=item.auditee_user_id) THEN
  RAISE EXCEPTION 'agenda auditee must be active tenant member' USING ERRCODE='23514'; END IF;
 RETURN item;
END; $$;
CREATE TRIGGER qms_audit_agenda_validate BEFORE INSERT OR UPDATE ON qms_audit_agenda_items FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_agenda();

CREATE FUNCTION validate_qms_audit_team_member() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE item qms_audit_team_members; expected_lead uuid;
BEGIN
 item:=validate_qms_audit_planning_item();
 IF NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=item.user_id) THEN
  RAISE EXCEPTION 'audit team member must be active tenant member' USING ERRCODE='23514'; END IF;
 IF item.team_role IN ('lead_auditor','auditor') AND NOT EXISTS(
  SELECT 1 FROM qms_access_grants g WHERE g.tenant_id=item.tenant_id AND g.unit_id=item.unit_id
   AND g.user_id=item.user_id AND g.capability='audits.execute' AND g.status='active') THEN
  RAISE EXCEPTION 'audit team auditor requires explicit execution authority' USING ERRCODE='23514'; END IF;
 IF item.team_role='lead_auditor' THEN
  SELECT lead_auditor_user_id INTO expected_lead FROM qms_internal_audits WHERE id=item.audit_id;
  IF expected_lead IS NULL OR expected_lead<>item.user_id THEN
   RAISE EXCEPTION 'lead team member must match audit lead auditor' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN item;
END; $$;
CREATE TRIGGER qms_audit_team_validate BEFORE INSERT OR UPDATE ON qms_audit_team_members FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_team_member();

CREATE OR REPLACE FUNCTION validate_qms_internal_audit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; workflow boolean; independence boolean;
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
  workflow:=current_setting('app.internal_audit_workflow',true)='transition';
  independence:=current_setting('app.internal_audit_independence',true)='review';
  IF workflow THEN
   IF NOT qms_has_capability(CASE WHEN OLD.state='draft' AND NEW.state='planned' THEN 'audits.manage' ELSE 'audits.review' END,NEW.unit_id) THEN
    RAISE EXCEPTION 'internal audit workflow authority required' USING ERRCODE='42501'; END IF;
   IF (to_jsonb(NEW)-ARRAY['state','actual_start','actual_end','completed_by_user_id','completed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','actual_start','actual_end','completed_by_user_id','completed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','row_version','updated_at']) THEN
    RAISE EXCEPTION 'internal audit workflow cannot edit content' USING ERRCODE='23514'; END IF;
   IF NOT ((OLD.state='draft' AND NEW.state IN ('planned','cancelled')) OR (OLD.state='planned' AND NEW.state IN ('ready','cancelled'))) THEN
    RAISE EXCEPTION 'workflow transition belongs to a later internal-audit slice' USING ERRCODE='23514'; END IF;
   IF OLD.state='planned' AND NEW.state='ready' AND (
    NOT EXISTS(SELECT 1 FROM qms_audit_scopes s WHERE s.audit_id=NEW.id AND s.status='active')
    OR NOT EXISTS(SELECT 1 FROM qms_audit_criteria c WHERE c.audit_id=NEW.id AND c.status='active')
    OR NEW.lead_auditor_user_id IS NULL
    OR NOT EXISTS(SELECT 1 FROM qms_audit_team_members tm WHERE tm.audit_id=NEW.id AND tm.user_id=NEW.lead_auditor_user_id AND tm.team_role='lead_auditor' AND tm.status='active')
    OR NEW.independence_status NOT IN ('confirmed','override')
   ) THEN RAISE EXCEPTION 'internal audit readiness prerequisites are incomplete' USING ERRCODE='23514'; END IF;
  ELSIF independence THEN
   IF NOT qms_has_capability('audits.review',NEW.unit_id) OR OLD.state NOT IN ('draft','planned') THEN
    RAISE EXCEPTION 'independence review authority or state invalid' USING ERRCODE='42501'; END IF;
   IF (to_jsonb(NEW)-ARRAY['independence_status','independence_notes','independence_reviewed_by_user_id','independence_reviewed_at','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['independence_status','independence_notes','independence_reviewed_by_user_id','independence_reviewed_at','row_version','updated_at'])
    OR NEW.independence_status NOT IN ('confirmed','override')
    OR NEW.independence_reviewed_by_user_id IS DISTINCT FROM actor OR NEW.independence_reviewed_at IS NULL
    OR actor IS NOT DISTINCT FROM NEW.lead_auditor_user_id
    OR (NEW.independence_status='override' AND length(btrim(NEW.independence_notes))=0) THEN
    RAISE EXCEPTION 'invalid independence review command' USING ERRCODE='23514'; END IF;
  ELSE
   IF NEW.state IS DISTINCT FROM OLD.state OR ROW(NEW.actual_start,NEW.actual_end,NEW.completed_by_user_id,NEW.completed_at,NEW.cancelled_by_user_id,NEW.cancelled_at,NEW.cancellation_reason,
     NEW.independence_status,NEW.independence_notes,NEW.independence_reviewed_by_user_id,NEW.independence_reviewed_at)
    IS DISTINCT FROM ROW(OLD.actual_start,OLD.actual_end,OLD.completed_by_user_id,OLD.completed_at,OLD.cancelled_by_user_id,OLD.cancelled_at,OLD.cancellation_reason,
     OLD.independence_status,OLD.independence_notes,OLD.independence_reviewed_by_user_id,OLD.independence_reviewed_at) THEN
    RAISE EXCEPTION 'use internal audit workflow commands' USING ERRCODE='23514'; END IF;
   IF NOT qms_has_capability('audits.manage',NEW.unit_id) THEN RAISE EXCEPTION 'audit management authority required' USING ERRCODE='42501'; END IF;
   IF EXISTS(SELECT 1 FROM qms_audit_team_members tm WHERE tm.audit_id=NEW.id AND tm.team_role='lead_auditor' AND tm.status='active' AND tm.user_id IS DISTINCT FROM NEW.lead_auditor_user_id) THEN
    RAISE EXCEPTION 'withdraw the active lead team member before changing lead auditor' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 IF NEW.program_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM qms_audit_programs p WHERE p.id=NEW.program_id AND p.tenant_id=NEW.tenant_id AND p.unit_id=NEW.unit_id AND p.state<>'cancelled') THEN
  RAISE EXCEPTION 'audit program scope or state is invalid' USING ERRCODE='23514'; END IF;
 IF NEW.lead_auditor_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.lead_auditor_user_id) THEN
  RAISE EXCEPTION 'lead auditor must be active tenant member' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
"""
    )


def downgrade() -> None:
    op.execute(
        r"""
ALTER TABLE qms_audit_scopes DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_criteria DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_agenda_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_team_members DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_scopes) OR EXISTS(SELECT 1 FROM qms_audit_criteria)
  OR EXISTS(SELECT 1 FROM qms_audit_agenda_items) OR EXISTS(SELECT 1 FROM qms_audit_team_members)
  OR EXISTS(SELECT 1 FROM qms_internal_audits WHERE independence_status<>'pending' OR state='ready')
  OR EXISTS(SELECT 1 FROM audit_events WHERE action IN ('audit_scope.created','audit_scope.updated','audit_scope.withdrawn','audit_criterion.created','audit_criterion.updated','audit_criterion.withdrawn','audit_agenda.created','audit_agenda.updated','audit_agenda.withdrawn','audit_team_member.added','audit_team_member.withdrawn','internal_audit.independence_reviewed')) THEN
  RAISE EXCEPTION 'cannot discard internal audit scope and independence history'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

DROP TABLE qms_audit_team_members,qms_audit_agenda_items,qms_audit_criteria,qms_audit_scopes;
DROP FUNCTION validate_qms_audit_team_member(); DROP FUNCTION validate_qms_audit_agenda();
DROP FUNCTION validate_qms_audit_criterion(); DROP FUNCTION validate_qms_audit_scope();
DROP FUNCTION validate_qms_audit_planning_item(); DROP FUNCTION qms_audit_planning_write_allowed(uuid,uuid);
DROP FUNCTION qms_audit_planning_row_allowed(uuid,uuid);

CREATE OR REPLACE FUNCTION validate_qms_internal_audit() RETURNS trigger
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

DO $$ DECLARE definition text; BEGIN
 SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
  WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_check';
 EXECUTE 'ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check';
 definition:=regexp_replace(definition,
  ' OR \\(\\(action\\)::text = ANY \\(\\(ARRAY\\[.*\\]\\)::text\\[\\]\\)\\)\\)\\)$','))');
 EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check '||definition;
END $$;
"""
    )
