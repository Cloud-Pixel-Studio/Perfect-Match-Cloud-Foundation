# ruff: noqa: E501 -- deterministic migration SQL.
"""Versioned audit criteria with optional scope traceability."""

from alembic import op

revision = "0043_internal_audit_criteria"
down_revision = "0042_internal_audit_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_scopes ADD CONSTRAINT qms_audit_scope_identity UNIQUE(id,audit_id,tenant_id,unit_id);
CREATE TABLE qms_audit_criteria (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL,
 sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 10000),
 title varchar(160) NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 requirement text NOT NULL CHECK(length(btrim(requirement)) BETWEEN 1 AND 4000),
 source_type varchar(20) NOT NULL CHECK(source_type IN ('internal','standard','regulation','customer')),
 reference varchar(240) NOT NULL CHECK(length(btrim(reference)) BETWEEN 1 AND 240), scope_id uuid,
 status varchar(20) NOT NULL CHECK(status IN ('active','withdrawn')),
 row_version integer NOT NULL CHECK(row_version>=1),
 withdrawn_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, withdrawn_at timestamptz,
 withdrawal_reason varchar(500) NOT NULL CHECK(length(withdrawal_reason)<=500),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(scope_id,audit_id,tenant_id,unit_id) REFERENCES qms_audit_scopes(id,audit_id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((status='withdrawn')=(withdrawn_at IS NOT NULL AND withdrawn_by_user_id IS NOT NULL AND length(btrim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX qms_audit_criterion_active_sequence ON qms_audit_criteria(audit_id,sequence) WHERE status='active';
CREATE INDEX qms_audit_criterion_scope ON qms_audit_criteria(scope_id) WHERE status='active';
CREATE INDEX qms_audit_criterion_lookup ON qms_audit_criteria(tenant_id,unit_id,audit_id,status,sequence,id);
REVOKE ALL ON qms_audit_criteria FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_audit_criteria TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_audit_criteria FROM pmcloud_app;
ALTER TABLE qms_audit_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_criteria FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_criterion_read ON qms_audit_criteria FOR SELECT USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id));
CREATE POLICY audit_criterion_create ON qms_audit_criteria FOR INSERT WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id));
CREATE POLICY audit_criterion_update ON qms_audit_criteria FOR UPDATE USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id)) WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.manage',unit_id));
CREATE FUNCTION validate_qms_audit_criterion_v2() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent_state text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT qms_has_capability('audits.read',NEW.unit_id) OR NOT qms_has_capability('audits.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'audit criterion authority required' USING ERRCODE='42501'; END IF;
 SELECT state INTO parent_state FROM qms_internal_audits WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS NULL OR parent_state NOT IN ('draft','planned') THEN RAISE EXCEPTION 'audit planning is closed' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'active' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'criterion must start active by current actor' USING ERRCODE='23514'; END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.audit_id,NEW.created_by_user_id,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.audit_id,OLD.created_by_user_id,OLD.created_at)
   OR OLD.status<>'active' OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'criterion identity, status or version invalid' USING ERRCODE='23514'; END IF;
  IF NEW.status='withdrawn' THEN
   IF ROW(NEW.sequence,NEW.title,NEW.requirement,NEW.source_type,NEW.reference,NEW.scope_id) IS DISTINCT FROM ROW(OLD.sequence,OLD.title,OLD.requirement,OLD.source_type,OLD.reference,OLD.scope_id)
    OR NEW.withdrawn_by_user_id IS DISTINCT FROM actor OR NEW.withdrawn_at IS NULL OR length(btrim(NEW.withdrawal_reason))=0 THEN
    RAISE EXCEPTION 'invalid criterion withdrawal' USING ERRCODE='23514'; END IF;
  ELSIF NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by_user_id IS NOT NULL OR NEW.withdrawal_reason<>'' THEN
   RAISE EXCEPTION 'criterion withdrawal fields are controlled' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.status='active' AND NEW.scope_id IS NOT NULL THEN
  PERFORM 1 FROM qms_audit_scopes WHERE id=NEW.scope_id AND audit_id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id AND status='active' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'criterion scope must be active in same audit' USING ERRCODE='23514'; END IF;
 END IF;
 UPDATE qms_internal_audits SET row_version=row_version+1,updated_at=GREATEST(NEW.updated_at,updated_at+interval '1 microsecond') WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 RETURN NEW;
END; $$;
CREATE TRIGGER audit_criterion_validate BEFORE INSERT OR UPDATE ON qms_audit_criteria FOR EACH ROW EXECUTE FUNCTION validate_qms_audit_criterion_v2();
CREATE FUNCTION guard_qms_audit_scope_criteria() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.status='active' AND NEW.status='withdrawn' THEN
  PERFORM 1 FROM qms_internal_audits WHERE id=OLD.audit_id AND tenant_id=OLD.tenant_id AND unit_id=OLD.unit_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM qms_audit_criteria WHERE scope_id=OLD.id AND status='active') THEN
   RAISE EXCEPTION 'withdraw or relink active criteria before withdrawing scope' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER audit_scope_criteria_guard BEFORE UPDATE ON qms_audit_scopes FOR EACH ROW EXECUTE FUNCTION guard_qms_audit_scope_criteria();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_criteria DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_criteria) OR EXISTS(SELECT 1 FROM audit_events WHERE action='internal_audit.updated' AND new_values->>'criterion_id' IS NOT NULL) THEN
  RAISE EXCEPTION 'cannot discard internal audit operational history: structured criterion'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TRIGGER audit_scope_criteria_guard ON qms_audit_scopes;
DROP FUNCTION guard_qms_audit_scope_criteria();
DROP TABLE qms_audit_criteria;
ALTER TABLE qms_audit_scopes DROP CONSTRAINT qms_audit_scope_identity;
DROP FUNCTION validate_qms_audit_criterion_v2();
""")
