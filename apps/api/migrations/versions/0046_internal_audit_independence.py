# ruff: noqa: E501 -- deterministic migration SQL.
"""Append-only independence decisions bound to a planning revision, not execution."""

from alembic import op

revision = "0046_audit_independence"
down_revision = "0045_internal_audit_agenda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE qms_audit_independence_reviews (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL,
 review_version integer NOT NULL CHECK(review_version>=1),
 source_audit_version integer NOT NULL CHECK(source_audit_version>=1),
 decision varchar(20) NOT NULL CHECK(decision IN ('confirmed','override','withdrawn')),
 notes text NOT NULL CHECK(length(btrim(notes))>0 AND length(notes)<=2000),
 independence_attested boolean NOT NULL,
 reviewer_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 reviewer_name_snapshot varchar(160) NOT NULL CHECK(length(btrim(reviewer_name_snapshot)) BETWEEN 1 AND 160),
 lead_auditor_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 UNIQUE(audit_id,review_version), CHECK(independence_attested=(decision<>'withdrawn'))
);
CREATE INDEX qms_independence_lookup ON qms_audit_independence_reviews(tenant_id,unit_id,audit_id,review_version DESC);
REVOKE ALL ON qms_audit_independence_reviews FROM PUBLIC;
GRANT SELECT,INSERT ON qms_audit_independence_reviews TO pmcloud_app;
REVOKE UPDATE,DELETE,TRUNCATE ON qms_audit_independence_reviews FROM pmcloud_app;
ALTER TABLE qms_audit_independence_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_independence_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY independence_read ON qms_audit_independence_reviews FOR SELECT USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id));
CREATE POLICY independence_create ON qms_audit_independence_reviews FOR INSERT WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('audits.review',unit_id));
CREATE FUNCTION validate_qms_independence_review() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent qms_internal_audits%ROWTYPE; previous qms_audit_independence_reviews%ROWTYPE; person_name text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT qms_has_capability('audits.read',NEW.unit_id) OR NOT qms_has_capability('audits.review',NEW.unit_id) THEN RAISE EXCEPTION 'independence review authority required' USING ERRCODE='42501'; END IF;
 SELECT * INTO parent FROM qms_internal_audits WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF parent.id IS NULL OR parent.state<>'planned' OR NEW.source_audit_version<>parent.row_version THEN RAISE EXCEPTION 'review requires current scheduled plan' USING ERRCODE='23514'; END IF;
 IF actor IS NULL OR NEW.reviewer_user_id IS DISTINCT FROM actor OR actor=parent.created_by_user_id OR actor=parent.lead_auditor_user_id
 OR EXISTS(SELECT 1 FROM qms_audit_team_members WHERE audit_id=parent.id AND status='active' AND user_id=actor) THEN RAISE EXCEPTION 'reviewer must be outside audit creation and active team' USING ERRCODE='23514'; END IF;
 SELECT display_name INTO person_name FROM organization_member_directory() WHERE user_id=actor;
 IF person_name IS NULL OR NEW.reviewer_name_snapshot IS DISTINCT FROM person_name THEN RAISE EXCEPTION 'reviewer identity snapshot invalid' USING ERRCODE='23514'; END IF;
 IF NEW.lead_auditor_user_id IS DISTINCT FROM parent.lead_auditor_user_id THEN RAISE EXCEPTION 'lead snapshot invalid' USING ERRCODE='23514'; END IF;
 SELECT * INTO previous FROM qms_audit_independence_reviews WHERE audit_id=parent.id ORDER BY review_version DESC LIMIT 1;
 IF NEW.review_version<>COALESCE(previous.review_version,0)+1 THEN RAISE EXCEPTION 'independence history changed' USING ERRCODE='23514'; END IF;
 IF previous.created_at IS NOT NULL AND NEW.created_at<=previous.created_at THEN RAISE EXCEPTION 'review time must advance' USING ERRCODE='23514'; END IF;
 IF NEW.decision='withdrawn' THEN
  IF previous.id IS NULL OR previous.decision='withdrawn' THEN RAISE EXCEPTION 'no recorded decision to withdraw' USING ERRCODE='23514'; END IF;
 ELSE
  IF NOT EXISTS(SELECT 1 FROM qms_audit_team_members t JOIN organization_member_directory() d ON d.user_id=t.user_id WHERE t.audit_id=parent.id AND t.user_id=parent.lead_auditor_user_id AND t.status='active' AND t.team_role='auditor')
   OR NOT EXISTS(SELECT 1 FROM qms_audit_scopes WHERE audit_id=parent.id AND status='active')
   OR NOT EXISTS(SELECT 1 FROM qms_audit_criteria WHERE audit_id=parent.id AND status='active')
   OR NOT EXISTS(SELECT 1 FROM qms_audit_agenda_items WHERE audit_id=parent.id AND status='active') THEN RAISE EXCEPTION 'complete the structured audit plan before review' USING ERRCODE='23514'; END IF;
  IF EXISTS(SELECT 1 FROM qms_audit_team_members t WHERE t.audit_id=parent.id AND t.status='active' AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=t.user_id)) THEN RAISE EXCEPTION 'planned participants must remain active company members' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER independence_review_validate BEFORE INSERT ON qms_audit_independence_reviews FOR EACH ROW EXECUTE FUNCTION validate_qms_independence_review();
CREATE FUNCTION guard_qms_legacy_independence() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.independence_status<>'pending' OR NEW.independence_notes<>'' OR NEW.independence_reviewed_by_user_id IS NOT NULL OR NEW.independence_reviewed_at IS NOT NULL THEN RAISE EXCEPTION 'use append-only independence review commands' USING ERRCODE='23514'; END IF;
 ELSIF ROW(NEW.independence_status,NEW.independence_notes,NEW.independence_reviewed_by_user_id,NEW.independence_reviewed_at) IS DISTINCT FROM ROW(OLD.independence_status,OLD.independence_notes,OLD.independence_reviewed_by_user_id,OLD.independence_reviewed_at) THEN RAISE EXCEPTION 'use append-only independence review commands' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER internal_audit_independence_guard BEFORE INSERT OR UPDATE ON qms_internal_audits FOR EACH ROW EXECUTE FUNCTION guard_qms_legacy_independence();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_independence_reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_independence_reviews) OR EXISTS(SELECT 1 FROM audit_events WHERE action='internal_audit.updated' AND new_values->>'independence_review_id' IS NOT NULL) THEN RAISE EXCEPTION 'cannot discard internal audit operational history: independence'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TRIGGER internal_audit_independence_guard ON qms_internal_audits;
DROP FUNCTION guard_qms_legacy_independence();
DROP TABLE qms_audit_independence_reviews;
DROP FUNCTION validate_qms_independence_review();
""")
