# ruff: noqa: E501 -- deterministic migration SQL.
"""Controlled UTC agenda with participant, scope and planning-window guards."""

from alembic import op

revision = "0045_internal_audit_agenda"
down_revision = "0044_internal_audit_team"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_team_members ADD CONSTRAINT qms_audit_team_identity UNIQUE(id,audit_id,tenant_id,unit_id);
CREATE TABLE qms_audit_agenda_items (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL,
 sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 10000),
 title varchar(160) NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 objective text NOT NULL CHECK(length(objective)<=4000),
 method varchar(30) NOT NULL CHECK(method IN ('interview','observation','document_review','sampling','meeting','other')),
 location varchar(240) NOT NULL CHECK(length(location)<=240),
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL,
 scope_id uuid, auditor_team_member_id uuid NOT NULL, auditee_team_member_id uuid,
 CHECK(starts_at<ends_at),
 CHECK(date_trunc('minute',starts_at AT TIME ZONE 'UTC')=starts_at AT TIME ZONE 'UTC' AND date_trunc('minute',ends_at AT TIME ZONE 'UTC')=ends_at AT TIME ZONE 'UTC'),
 status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')),
 row_version integer NOT NULL CHECK(row_version>=1),
 withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, withdrawn_at timestamptz,
 withdrawal_reason varchar(500) NOT NULL CHECK(length(withdrawal_reason)<=500),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(scope_id,audit_id,tenant_id,unit_id) REFERENCES qms_audit_scopes(id,audit_id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(auditor_team_member_id,audit_id,tenant_id,unit_id) REFERENCES qms_audit_team_members(id,audit_id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(auditee_team_member_id,audit_id,tenant_id,unit_id) REFERENCES qms_audit_team_members(id,audit_id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_agenda_active_sequence ON qms_audit_agenda_items(audit_id,sequence) WHERE status='active';
CREATE INDEX qms_audit_agenda_lookup ON qms_audit_agenda_items(tenant_id,unit_id,audit_id,status,starts_at,sequence,id);
CREATE INDEX qms_audit_agenda_overlap ON qms_audit_agenda_items(audit_id,starts_at,ends_at) WHERE status='active';
REVOKE ALL ON qms_audit_agenda_items FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_audit_agenda_items TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_audit_agenda_items FROM pmcloud_app;
ALTER TABLE qms_audit_agenda_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_agenda_items FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_agenda_read ON qms_audit_agenda_items FOR SELECT USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id));
CREATE POLICY audit_agenda_create ON qms_audit_agenda_items FOR INSERT WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id));
CREATE POLICY audit_agenda_update ON qms_audit_agenda_items FOR UPDATE USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id)) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id));
CREATE FUNCTION validate_qms_audit_agenda_v2() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent_state text; parent_start date; parent_end date;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT qms_has_capability('audits.read',NEW.unit_id) OR NOT qms_has_capability('audits.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'audit agenda authority required' USING ERRCODE='42501'; END IF;
 SELECT state,planned_start,planned_end INTO parent_state,parent_start,parent_end FROM qms_internal_audits WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS NULL OR parent_state NOT IN ('draft','planned') THEN RAISE EXCEPTION 'audit planning is closed' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'agenda item must start active by current actor' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.audit_id,NEW.created_by_user_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.audit_id,OLD.created_by_user_id,OLD.created_at)
   OR OLD.status<>'active' OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'agenda identity, status or version invalid' USING ERRCODE='23514'; END IF;
  IF NEW.status='withdrawn' THEN
   IF ROW(NEW.sequence,NEW.title,NEW.objective,NEW.method,NEW.location,NEW.starts_at,NEW.ends_at,NEW.scope_id,NEW.auditor_team_member_id,NEW.auditee_team_member_id) IS DISTINCT FROM ROW(OLD.sequence,OLD.title,OLD.objective,OLD.method,OLD.location,OLD.starts_at,OLD.ends_at,OLD.scope_id,OLD.auditor_team_member_id,OLD.auditee_team_member_id)
    OR NEW.withdrawn_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NULL OR length(btrim(NEW.withdrawal_reason))=0 THEN
    RAISE EXCEPTION 'invalid agenda withdrawal' USING ERRCODE='23514'; END IF;
  ELSIF NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'agenda withdrawal fields are controlled' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.status='active' THEN
  IF NEW.starts_at<(parent_start::timestamp AT TIME ZONE 'UTC') OR NEW.ends_at>((parent_end+1)::timestamp AT TIME ZONE 'UTC') THEN RAISE EXCEPTION 'agenda outside planned UTC dates' USING ERRCODE='23514'; END IF;
  PERFORM 1 FROM qms_audit_team_members WHERE id=NEW.auditor_team_member_id AND audit_id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id AND status='active' AND team_role='auditor' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'agenda auditor must be active in same audit' USING ERRCODE='23514'; END IF;
  IF NEW.auditee_team_member_id IS NOT NULL THEN
   PERFORM 1 FROM qms_audit_team_members WHERE id=NEW.auditee_team_member_id AND audit_id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id AND status='active' AND team_role='auditee' FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'agenda auditee must be active in same audit' USING ERRCODE='23514'; END IF;
  END IF;
  IF NEW.scope_id IS NOT NULL THEN
   PERFORM 1 FROM qms_audit_scopes WHERE id=NEW.scope_id AND audit_id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id AND status='active' FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'agenda agenda item must be active in same audit' USING ERRCODE='23514'; END IF;
  END IF;
  IF EXISTS(SELECT 1 FROM qms_audit_agenda_items WHERE audit_id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id AND status='active' AND id<>NEW.id AND starts_at<NEW.ends_at AND ends_at>NEW.starts_at AND (auditor_team_member_id=NEW.auditor_team_member_id OR (NEW.auditee_team_member_id IS NOT NULL AND auditee_team_member_id=NEW.auditee_team_member_id))) THEN
   RAISE EXCEPTION 'agenda participant overlap' USING ERRCODE='23514'; END IF;
 END IF;
 UPDATE qms_internal_audits SET row_version=row_version+1,updated_at=GREATEST(NEW.updated_at,updated_at+interval '1 microsecond') WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 RETURN NEW;
END; $$;
CREATE TRIGGER audit_agenda_validate BEFORE INSERT OR UPDATE ON qms_audit_agenda_items FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_agenda_v2();
CREATE FUNCTION guard_qms_audit_team_agenda() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.status='active' AND (NEW.status='withdrawn' OR NEW.team_role IS DISTINCT FROM OLD.team_role) THEN
  PERFORM 1 FROM qms_internal_audits WHERE id=OLD.audit_id AND tenant_id=OLD.tenant_id AND unit_id=OLD.unit_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM qms_audit_agenda_items WHERE audit_id=OLD.audit_id AND status='active' AND (auditor_team_member_id=OLD.id OR auditee_team_member_id=OLD.id)) THEN RAISE EXCEPTION 'reassign or withdraw agenda before team role change or retirement' USING ERRCODE='23514'; END IF;
 END IF; RETURN NEW;
END; $$;
CREATE TRIGGER audit_team_agenda_guard BEFORE UPDATE ON qms_audit_team_members FOR EACH ROW EXECUTE FUNCTION guard_qms_audit_team_agenda();
CREATE FUNCTION guard_qms_audit_scope_agenda() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.status='active' AND NEW.status='withdrawn' THEN
  PERFORM 1 FROM qms_internal_audits WHERE id=OLD.audit_id AND tenant_id=OLD.tenant_id AND unit_id=OLD.unit_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM qms_audit_agenda_items WHERE scope_id=OLD.id AND status='active') THEN RAISE EXCEPTION 'reassign or withdraw agenda before scope retirement' USING ERRCODE='23514'; END IF;
 END IF; RETURN NEW;
END; $$;
CREATE TRIGGER audit_scope_agenda_guard BEFORE UPDATE ON qms_audit_scopes FOR EACH ROW EXECUTE FUNCTION guard_qms_audit_scope_agenda();
CREATE FUNCTION guard_qms_audit_agenda_window() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF ROW(NEW.planned_start,NEW.planned_end) IS DISTINCT FROM ROW(OLD.planned_start,OLD.planned_end) AND EXISTS(SELECT 1 FROM qms_audit_agenda_items WHERE audit_id=NEW.id AND status='active' AND (starts_at<(NEW.planned_start::timestamp AT TIME ZONE 'UTC') OR ends_at>((NEW.planned_end+1)::timestamp AT TIME ZONE 'UTC'))) THEN RAISE EXCEPTION 'replan agenda before shrinking audit dates' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER audit_agenda_window_guard BEFORE UPDATE ON qms_internal_audits FOR EACH ROW EXECUTE FUNCTION guard_qms_audit_agenda_window();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_agenda_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_agenda_items) OR EXISTS(SELECT 1 FROM audit_events WHERE action='internal_audit.updated' AND new_values->>'agenda_id' IS NOT NULL) THEN
  RAISE EXCEPTION 'cannot discard internal audit operational history: audit agenda'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TRIGGER audit_team_agenda_guard ON qms_audit_team_members;
DROP TRIGGER audit_scope_agenda_guard ON qms_audit_scopes;
DROP TRIGGER audit_agenda_window_guard ON qms_internal_audits;
DROP FUNCTION guard_qms_audit_team_agenda();
DROP FUNCTION guard_qms_audit_scope_agenda();
DROP FUNCTION guard_qms_audit_agenda_window();
DROP TABLE qms_audit_agenda_items;
ALTER TABLE qms_audit_team_members DROP CONSTRAINT qms_audit_team_identity;
DROP FUNCTION validate_qms_audit_agenda_v2();
""")
