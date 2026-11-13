# ruff: noqa: E501 -- deterministic security migration SQL.
"""Append-only auditor competence assessments with controlled documentary support."""

from alembic import op

revision = "0048_audit_competence"
down_revision = "0047_audit_execution_authority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE qms_audit_competence_reviews (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, audit_id uuid NOT NULL,
 team_member_id uuid NOT NULL REFERENCES qms_audit_team_members(id) ON DELETE RESTRICT,
 subject_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 subject_name_snapshot varchar(160) NOT NULL CHECK(length(btrim(subject_name_snapshot)) BETWEEN 1 AND 160),
 review_version integer NOT NULL CHECK(review_version>=1),
 source_audit_version integer NOT NULL CHECK(source_audit_version>=1),
 decision varchar(20) NOT NULL CHECK(decision IN ('confirmed','withdrawn')),
 notes text NOT NULL CHECK(length(btrim(notes))>0 AND length(notes)<=2000),
 competence_attested boolean NOT NULL CHECK(competence_attested=(decision='confirmed')),
 document_id uuid NOT NULL, document_revision_id uuid NOT NULL,
 document_code_snapshot varchar(40) NOT NULL, document_title_snapshot varchar(200) NOT NULL,
 document_revision_snapshot varchar(40) NOT NULL,
 file_sha256 varchar(64) NOT NULL CHECK(file_sha256 ~ '^[a-f0-9]{64}$'),
 valid_until date NOT NULL,
 reviewer_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 reviewer_name_snapshot varchar(160) NOT NULL,
 created_at timestamptz NOT NULL,
 FOREIGN KEY(audit_id,tenant_id,unit_id) REFERENCES qms_internal_audits(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_id,tenant_id,unit_id) REFERENCES qms_documents(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(document_revision_id,document_id,tenant_id) REFERENCES qms_document_revisions(id,document_id,tenant_id) ON DELETE RESTRICT,
 UNIQUE(audit_id,review_version)
);
CREATE INDEX qms_competence_history ON qms_audit_competence_reviews(tenant_id,unit_id,audit_id,review_version DESC);
CREATE INDEX qms_competence_person ON qms_audit_competence_reviews(audit_id,team_member_id,review_version DESC);
REVOKE ALL ON qms_audit_competence_reviews FROM PUBLIC;
GRANT SELECT,INSERT ON qms_audit_competence_reviews TO pmcloud_app;
REVOKE UPDATE,DELETE,TRUNCATE ON qms_audit_competence_reviews FROM pmcloud_app;
ALTER TABLE qms_audit_competence_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_audit_competence_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY competence_read ON qms_audit_competence_reviews FOR SELECT USING(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('documents.read',unit_id));
CREATE POLICY competence_create ON qms_audit_competence_reviews FOR INSERT WITH CHECK(
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('audits.read',unit_id) AND qms_has_capability('documents.read',unit_id)
 AND qms_has_capability('audits.review',unit_id));
CREATE FUNCTION validate_qms_competence_review() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent public.qms_internal_audits%ROWTYPE; target public.qms_audit_team_members%ROWTYPE;
 previous public.qms_audit_competence_reviews%ROWTYPE; preceding public.qms_audit_competence_reviews%ROWTYPE; person_name text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF NOT public.qms_has_capability('audits.read',NEW.unit_id)
  OR NOT public.qms_has_capability('documents.read',NEW.unit_id)
  OR NOT public.qms_has_capability('audits.review',NEW.unit_id) THEN RAISE EXCEPTION 'competence review authority required' USING ERRCODE='42501'; END IF;
 SELECT * INTO parent FROM public.qms_internal_audits WHERE id=NEW.audit_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id FOR UPDATE;
 IF parent.id IS NULL OR parent.state<>'planned' OR NEW.source_audit_version<>parent.row_version THEN RAISE EXCEPTION 'competence review requires current scheduled plan' USING ERRCODE='23514'; END IF;
 IF actor IS NULL OR NEW.reviewer_user_id IS DISTINCT FROM actor OR actor=parent.created_by_user_id OR actor=parent.lead_auditor_user_id
  OR EXISTS(SELECT 1 FROM public.qms_audit_team_members WHERE audit_id=parent.id AND status='active' AND user_id=actor) THEN RAISE EXCEPTION 'competence reviewer must be outside audit creation and active team' USING ERRCODE='23514'; END IF;
 SELECT display_name INTO person_name FROM public.organization_member_directory() WHERE user_id=actor;
 IF person_name IS NULL OR NEW.reviewer_name_snapshot IS DISTINCT FROM person_name THEN RAISE EXCEPTION 'competence reviewer identity invalid' USING ERRCODE='23514'; END IF;
 SELECT * INTO target FROM public.qms_audit_team_members WHERE id=NEW.team_member_id AND audit_id=parent.id AND tenant_id=parent.tenant_id AND unit_id=parent.unit_id;
 IF target.id IS NULL OR NEW.subject_user_id IS DISTINCT FROM target.user_id THEN RAISE EXCEPTION 'competence subject does not match this audit assignment' USING ERRCODE='23514'; END IF;
 NEW.subject_name_snapshot:=target.display_name_snapshot;
 SELECT * INTO preceding FROM public.qms_audit_competence_reviews WHERE audit_id=parent.id ORDER BY review_version DESC LIMIT 1;
 IF NEW.review_version<>COALESCE(preceding.review_version,0)+1 THEN RAISE EXCEPTION 'competence history changed' USING ERRCODE='23514'; END IF;
 SELECT * INTO previous FROM public.qms_audit_competence_reviews WHERE audit_id=parent.id AND team_member_id=target.id ORDER BY review_version DESC LIMIT 1;
 IF NEW.decision='withdrawn' THEN
  IF previous.id IS NULL OR previous.decision<>'confirmed' THEN RAISE EXCEPTION 'no competence decision to withdraw' USING ERRCODE='23514'; END IF;
  NEW.document_id:=previous.document_id; NEW.document_revision_id:=previous.document_revision_id;
  NEW.document_code_snapshot:=previous.document_code_snapshot; NEW.document_title_snapshot:=previous.document_title_snapshot;
  NEW.document_revision_snapshot:=previous.document_revision_snapshot; NEW.file_sha256:=previous.file_sha256; NEW.valid_until:=previous.valid_until;
 ELSE
  IF target.status<>'active' OR target.team_role<>'auditor' OR NOT EXISTS(SELECT 1 FROM public.organization_member_directory() WHERE user_id=target.user_id) THEN RAISE EXCEPTION 'competence requires an active auditor and company membership' USING ERRCODE='23514'; END IF;
  IF NEW.valid_until IS NULL OR NEW.valid_until<parent.planned_end OR NEW.valid_until<(clock_timestamp() AT TIME ZONE 'UTC')::date THEN RAISE EXCEPTION 'competence validity must cover today and the audit end' USING ERRCODE='23514'; END IF;
  SELECT d.code,d.title,r.revision,r.file_sha256 INTO NEW.document_code_snapshot,NEW.document_title_snapshot,NEW.document_revision_snapshot,NEW.file_sha256
   FROM public.qms_documents d JOIN public.qms_document_revisions r ON r.document_id=d.id AND r.tenant_id=d.tenant_id
   WHERE d.id=NEW.document_id AND d.tenant_id=NEW.tenant_id AND d.unit_id=NEW.unit_id AND d.status='active'
    AND r.id=NEW.document_revision_id AND r.status='active' AND r.file_state='clean';
  IF NOT FOUND THEN RAISE EXCEPTION 'competence support requires released clean revision in same unit' USING ERRCODE='23514'; END IF;
 END IF;
 NEW.created_at:=GREATEST(clock_timestamp(),preceding.created_at+interval '1 microsecond');
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_competence_review() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER competence_review_validate BEFORE INSERT ON qms_audit_competence_reviews FOR EACH ROW EXECUTE FUNCTION validate_qms_competence_review();
""")


def downgrade() -> None:
    op.execute("""
ALTER TABLE qms_audit_competence_reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_audit_competence_reviews) OR EXISTS(SELECT 1 FROM audit_events WHERE action='internal_audit.updated' AND new_values->>'competence_review_id' IS NOT NULL) THEN RAISE EXCEPTION 'cannot discard internal audit operational history: competence'; END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TABLE qms_audit_competence_reviews;
DROP FUNCTION validate_qms_competence_review();
""")
