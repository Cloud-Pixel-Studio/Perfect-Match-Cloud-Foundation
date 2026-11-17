# ruff: noqa: E501 -- deterministic migration SQL.
"""Versioned audit planning team; assignment does not grant execution authority."""

from alembic import op

revision = "0044_internal_audit_team"
down_revision = "0043_internal_audit_criteria"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE qms_audit_team_members (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 display_name_snapshot varchar(160) NOT NULL CHECK(length(btrim(display_name_snapshot)) BETWEEN 1 AND 160),
 team_role varchar(20) NOT NULL CHECK(team_role IN ('auditor','auditee')),
 responsibilities text NOT NULL CHECK(length(responsibilities)<=4000),
 status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')),
 row_version integer NOT NULL CHECK(row_version>=1),
 withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, withdrawn_at timestamptz,
 withdrawal_reason varchar(500) NOT NULL CHECK(length(withdrawal_reason)<=500),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_team_active_user ON qms_audit_team_members(audit_id,user_id) WHERE status='active';
CREATE INDEX qms_audit_team_lookup ON qms_audit_team_members(tenant_id,unit_id,audit_id,status,team_role,id);
REVOKE ALL ON qms_audit_team_members FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_audit_team_members TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_audit_team_members FROM pmcloud_app;
ALTER TABLE qms_audit_team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_team_members FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_team_read ON qms_audit_team_members FOR SELECT USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id));
CREATE POLICY audit_team_create ON qms_audit_team_members FOR INSERT WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id));
CREATE POLICY audit_team_update ON qms_audit_team_members FOR UPDATE USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id)) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id));
CREATE FUNCTION validate_qms_audit_team_v2() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent_state text; current_lead uuid; member_name text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT qms_has_capability('audits.read',NEW.unit_id) OR NOT qms_has_capability('audits.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'audit team authority required' USING ERRCODE='42501'; END IF;
 SELECT state,lead_auditor_user_id INTO parent_state,current_lead FROM qms_internal_audits WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS NULL OR parent_state NOT IN ('draft','planned') THEN RAISE EXCEPTION 'audit planning is closed' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'team member must start active by current actor' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.audit_id,NEW.user_id,NEW.display_name_snapshot,NEW.created_by_user_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.audit_id,OLD.user_id,OLD.display_name_snapshot,OLD.created_by_user_id,OLD.created_at)
   OR OLD.status<>'active' OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'team identity, status or version invalid' USING ERRCODE='23514'; END IF;
  IF NEW.status='withdrawn' THEN
   IF ROW(NEW.team_role,NEW.responsibilities) IS DISTINCT FROM ROW(OLD.team_role,OLD.responsibilities)
    OR NEW.withdrawn_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NULL OR length(btrim(NEW.withdrawal_reason))=0 THEN
    RAISE EXCEPTION 'invalid team withdrawal' USING ERRCODE='23514'; END IF;
  ELSIF NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'team withdrawal fields are controlled' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.status='active' THEN
  SELECT display_name INTO member_name FROM organization_member_directory() WHERE user_id=NEW.user_id;
  IF member_name IS NULL THEN RAISE EXCEPTION 'team person must be active company member' USING ERRCODE='23514'; END IF;
  IF TG_OP='INSERT' AND NEW.display_name_snapshot IS DISTINCT FROM member_name THEN RAISE EXCEPTION 'team identity snapshot invalid' USING ERRCODE='23514'; END IF;
  IF NEW.team_role='auditee' AND NEW.user_id=current_lead THEN RAISE EXCEPTION 'lead auditor cannot be an audited participant' USING ERRCODE='23514'; END IF;
 END IF;
 UPDATE qms_internal_audits SET row_version=row_version+1,updated_at=GREATEST(NEW.updated_at,updated_at+interval '1 microsecond') WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 RETURN NEW;
END; $$;
CREATE TRIGGER audit_team_validate BEFORE INSERT OR UPDATE ON qms_audit_team_members FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_team_v2();
CREATE FUNCTION guard_qms_audit_team_lead() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.lead_auditor_user_id IS DISTINCT FROM OLD.lead_auditor_user_id AND NEW.lead_auditor_user_id IS NOT NULL
 AND EXISTS(SELECT 1 FROM qms_audit_team_members WHERE audit_id=NEW.id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id AND user_id=NEW.lead_auditor_user_id AND status='active' AND team_role='auditee') THEN
  RAISE EXCEPTION 'lead auditor cannot be an audited participant' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER audit_team_lead_guard BEFORE UPDATE ON qms_internal_audits FOR EACH ROW EXECUTE FUNCTION guard_qms_audit_team_lead();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_team_members DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_team_members) OR EXISTS(SELECT 1 FROM audit_events WHERE action='internal_audit.updated' AND new_values->>'team_member_id' IS NOT NULL) THEN
  RAISE EXCEPTION 'cannot discard internal audit operational history: audit team'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TRIGGER audit_team_lead_guard ON qms_internal_audits;
DROP FUNCTION guard_qms_audit_team_lead();
DROP TABLE qms_audit_team_members;
DROP FUNCTION validate_qms_audit_team_v2();
""")
