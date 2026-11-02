# ruff: noqa: E501
"""Append-only CAPA effectiveness decisions, rework cycles and controlled closure."""

from alembic import op

revision = "0034_capa_effectiveness"
down_revision = "0033_capa_review_start"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated','capa.action_transitioned','capa.implementation_started','capa.effectiveness_review_started','capa.effectiveness_decided','capa.effectiveness_recorded','capa.closed'));
ALTER TABLE qms_capas ADD COLUMN effective_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capas ADD COLUMN effective_at timestamptz;
ALTER TABLE qms_capas ADD COLUMN closed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capas ADD COLUMN closed_at timestamptz;
ALTER TABLE qms_capas ADD COLUMN closure_notes text NOT NULL DEFAULT '' CHECK(length(closure_notes)<=4000);
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_state_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_state_check CHECK(state IN ('draft','analysis','action_planned','implementation','effectiveness_review','effective','closed'));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_analysis_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_analysis_stamp_check CHECK(
 (state='draft' AND analysis_started_by_user_id IS NULL AND analysis_started_at IS NULL)
 OR (state IN ('analysis','action_planned','implementation','effectiveness_review','effective','closed') AND analysis_started_by_user_id IS NOT NULL AND analysis_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_plan_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_plan_stamp_check CHECK(
 (state IN ('draft','analysis') AND plan_summary='' AND planned_by_user_id IS NULL AND planned_at IS NULL)
 OR (state IN ('action_planned','implementation','effectiveness_review','effective','closed') AND length(btrim(plan_summary))>0 AND planned_by_user_id IS NOT NULL AND planned_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_implementation_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_implementation_stamp_check CHECK(
 (state IN ('draft','analysis','action_planned') AND implementation_started_by_user_id IS NULL AND implementation_started_at IS NULL)
 OR (state IN ('implementation','effectiveness_review','effective','closed') AND implementation_started_by_user_id IS NOT NULL AND implementation_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_review_start_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_review_start_stamp_check CHECK(
 (state IN ('draft','analysis','action_planned','implementation') AND review_started_by_user_id IS NULL AND review_started_at IS NULL)
 OR (state IN ('effectiveness_review','effective','closed') AND review_started_by_user_id IS NOT NULL AND review_started_at IS NOT NULL));
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_effective_stamp_check CHECK(
 (state NOT IN ('effective','closed') AND effective_by_user_id IS NULL AND effective_at IS NULL)
 OR (state IN ('effective','closed') AND effective_by_user_id IS NOT NULL AND effective_at IS NOT NULL));
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_close_stamp_check CHECK(
 (state<>'closed' AND closed_by_user_id IS NULL AND closed_at IS NULL AND closure_notes='')
 OR (state='closed' AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL AND length(btrim(closure_notes))>0));
CREATE TABLE qms_capa_effectiveness_reviews (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL,
 capa_id uuid NOT NULL,
 cycle_number integer NOT NULL CHECK(cycle_number>=1),
 decision varchar(16) NOT NULL CHECK(decision IN ('effective','ineffective')),
 notes text NOT NULL CHECK(length(btrim(notes)) BETWEEN 1 AND 4000),
 reviewer_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 reviewed_at timestamptz NOT NULL,
 implementation_started_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 implementation_started_at timestamptz NOT NULL,
 review_started_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 review_started_at timestamptz NOT NULL,
 active_action_count integer NOT NULL CHECK(active_action_count>=1),
 verified_action_count integer NOT NULL CHECK(verified_action_count>=0),
 cancelled_action_count integer NOT NULL CHECK(cancelled_action_count>=0),
 UNIQUE(capa_id,cycle_number),
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(capa_id,tenant_id,unit_id) REFERENCES qms_capas(id,tenant_id,unit_id) ON DELETE RESTRICT
);
CREATE INDEX qms_capa_effectiveness_reviews_parent ON qms_capa_effectiveness_reviews(tenant_id,unit_id,capa_id,cycle_number);
REVOKE ALL ON qms_capa_effectiveness_reviews FROM PUBLIC;
GRANT SELECT,INSERT ON qms_capa_effectiveness_reviews TO pmcloud_app;
REVOKE UPDATE,DELETE,TRUNCATE ON qms_capa_effectiveness_reviews FROM pmcloud_app;
ALTER TABLE qms_capa_effectiveness_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_effectiveness_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_capa_effectiveness_read ON qms_capa_effectiveness_reviews FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_effectiveness_reviews.capa_id
  AND c.tenant_id=qms_capa_effectiveness_reviews.tenant_id AND c.unit_id=qms_capa_effectiveness_reviews.unit_id));
CREATE POLICY qms_capa_effectiveness_insert ON qms_capa_effectiveness_reviews FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.review',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_effectiveness_reviews.capa_id
  AND c.tenant_id=qms_capa_effectiveness_reviews.tenant_id AND c.unit_id=qms_capa_effectiveness_reviews.unit_id));
CREATE FUNCTION validate_qms_capa_effectiveness_review() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent qms_capas%ROWTYPE; next_cycle integer; active_count integer; verified_count integer; cancelled_count integer;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 SELECT * INTO parent FROM qms_capas c WHERE c.id=NEW.capa_id AND c.tenant_id=NEW.tenant_id
  AND c.unit_id=NEW.unit_id FOR UPDATE;
 IF parent.id IS NULL OR parent.state<>'effectiveness_review'
  OR current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'assess'
  OR NOT qms_has_capability('capa.review',NEW.unit_id)
  OR NEW.reviewer_user_id IS DISTINCT FROM actor
  OR NEW.reviewed_at<parent.review_started_at
  OR NEW.implementation_started_by_user_id IS DISTINCT FROM parent.implementation_started_by_user_id
  OR NEW.implementation_started_at IS DISTINCT FROM parent.implementation_started_at
  OR NEW.review_started_by_user_id IS DISTINCT FROM parent.review_started_by_user_id
  OR NEW.review_started_at IS DISTINCT FROM parent.review_started_at THEN
  RAISE EXCEPTION 'CAPA effectiveness review is invalid' USING ERRCODE='23514';
 END IF;
 IF EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=parent.id
  AND a.tenant_id=parent.tenant_id AND a.unit_id=parent.unit_id AND a.completed_by_user_id=actor)
  OR EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=parent.id
  AND a.tenant_id=parent.tenant_id AND a.unit_id=parent.unit_id AND a.state IN ('open','in_progress')) THEN
  RAISE EXCEPTION 'CAPA effectiveness reviewer must be independent of completed actions' USING ERRCODE='23514';
 END IF;
 SELECT count(*) FILTER (WHERE state IN ('completed','verified')),
  count(*) FILTER (WHERE state='verified'),count(*) FILTER (WHERE state='cancelled')
 INTO active_count,verified_count,cancelled_count FROM qms_capa_actions a WHERE a.capa_id=parent.id
  AND a.tenant_id=parent.tenant_id AND a.unit_id=parent.unit_id;
 SELECT COALESCE(max(cycle_number),0)+1 INTO next_cycle FROM qms_capa_effectiveness_reviews r
  WHERE r.capa_id=parent.id AND r.tenant_id=parent.tenant_id AND r.unit_id=parent.unit_id;
 IF active_count<1 OR NEW.active_action_count<>active_count
  OR NEW.verified_action_count<>verified_count OR NEW.cancelled_action_count<>cancelled_count
  OR NEW.cycle_number<>next_cycle THEN
  RAISE EXCEPTION 'CAPA effectiveness action snapshot is invalid' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_capa_effectiveness_validate BEFORE INSERT ON qms_capa_effectiveness_reviews
 FOR EACH ROW EXECUTE FUNCTION validate_qms_capa_effectiveness_review();
CREATE FUNCTION apply_qms_capa_effectiveness_decision() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.decision='effective' THEN
  UPDATE qms_capas SET state='effective',effective_by_user_id=NEW.reviewer_user_id,
   effective_at=NEW.reviewed_at,row_version=row_version+1,
   updated_at=greatest(clock_timestamp(),updated_at+interval '1 microsecond')
  WHERE id=NEW.capa_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 ELSE
  UPDATE qms_capas SET state='action_planned',
   implementation_started_by_user_id=NULL,implementation_started_at=NULL,
   review_started_by_user_id=NULL,review_started_at=NULL,
   row_version=row_version+1,
   updated_at=greatest(clock_timestamp(),updated_at+interval '1 microsecond')
  WHERE id=NEW.capa_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 END IF;
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPA effectiveness parent update denied' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_capa_effectiveness_apply AFTER INSERT ON qms_capa_effectiveness_reviews
 FOR EACH ROW EXECUTE FUNCTION apply_qms_capa_effectiveness_decision();
CREATE OR REPLACE FUNCTION validate_qms_capa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; origin_code text; origin_state text; starting boolean; planning boolean; implementing boolean; reviewing boolean; effective_decision boolean; replan_decision boolean; closing boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
    OR NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NEW.effective_by_user_id IS NOT NULL OR NEW.effective_at IS NOT NULL
    OR NEW.closed_by_user_id IS NOT NULL OR NEW.closed_at IS NOT NULL OR NEW.closure_notes<>'' THEN
   RAISE EXCEPTION 'CAPA must start as blank draft by current actor' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=NEW.process_id AND p.tenant_id=NEW.tenant_id
    AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'CAPA requires active scoped process' USING ERRCODE='23514';
  END IF;
  IF NEW.owner_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d
    WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA owner must be active member' USING ERRCODE='23514';
  END IF;
  IF NEW.source_type='ncr' THEN
   SELECT n.code,n.state INTO origin_code,origin_state FROM qms_nonconformities n
    WHERE n.id=NEW.source_ncr_id AND n.tenant_id=NEW.tenant_id AND n.unit_id=NEW.unit_id AND n.state<>'cancelled';
  ELSIF NEW.source_type='risk' THEN
   SELECT r.code,r.state INTO origin_code,origin_state FROM qms_risks r
    WHERE r.id=NEW.source_risk_id AND r.tenant_id=NEW.tenant_id AND r.unit_id=NEW.unit_id AND r.state<>'cancelled';
  END IF;
  IF NEW.source_type<>'other' AND (origin_code IS NULL OR NEW.source_code IS DISTINCT FROM origin_code
    OR NEW.source_state IS DISTINCT FROM origin_state) THEN
   RAISE EXCEPTION 'CAPA origin is invalid or snapshot differs' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.code,NEW.source_type,
    NEW.source_ncr_id,NEW.source_risk_id,NEW.source_code,NEW.source_state,
    NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.code,OLD.source_type,
    OLD.source_ncr_id,OLD.source_risk_id,OLD.source_code,OLD.source_state,
    OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'CAPA identity, provenance or version invalid' USING ERRCODE='23514';
  END IF;
  IF NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id AND NEW.owner_user_id IS NOT NULL
   AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d
    WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA owner must be active member' USING ERRCODE='23514';
  END IF;
  starting:=OLD.state='draft' AND NEW.state='analysis';
  planning:=OLD.state='analysis' AND NEW.state='action_planned';
  implementing:=OLD.state='action_planned' AND NEW.state='implementation';
  reviewing:=OLD.state='implementation' AND NEW.state='effectiveness_review';
  effective_decision:=OLD.state='effectiveness_review' AND NEW.state='effective';
  replan_decision:=OLD.state='effectiveness_review' AND NEW.state='action_planned';
  closing:=OLD.state='effective' AND NEW.state='closed';
  IF NEW.state IS DISTINCT FROM OLD.state AND NOT (starting OR planning OR implementing OR reviewing OR effective_decision OR replan_decision OR closing) THEN
   RAISE EXCEPTION 'invalid CAPA analysis transition' USING ERRCODE='23514';
  END IF;
  IF OLD.state='draft' AND NOT starting THEN
   IF NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NEW.effective_by_user_id IS NOT NULL OR NEW.effective_at IS NOT NULL
    OR NEW.closed_by_user_id IS NOT NULL OR NEW.closed_at IS NOT NULL OR NEW.closure_notes<>'' THEN
    RAISE EXCEPTION 'analysis requires a transition' USING ERRCODE='23514';
   END IF;
  ELSIF starting THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'start' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NEW.root_cause_method IS NULL OR NEW.analysis_data IS DISTINCT FROM qms_capa_analysis_scaffold(NEW.root_cause_method)
    OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>'' OR NEW.other_method_name<>''
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NEW.effective_by_user_id IS NOT NULL OR NEW.effective_at IS NOT NULL
    OR NEW.closed_by_user_id IS NOT NULL OR NEW.closed_at IS NOT NULL OR NEW.closure_notes<>''
    OR NEW.analysis_started_by_user_id IS DISTINCT FROM actor OR NEW.analysis_started_at IS NULL
    OR NEW.analysis_started_at<OLD.created_at OR NEW.root_cause_method IS DISTINCT FROM OLD.root_cause_method
    OR (to_jsonb(NEW)-ARRAY['state','analysis_data','analysis_started_by_user_id','analysis_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','analysis_data','analysis_started_by_user_id','analysis_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA analysis start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF planning THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'plan'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT qms_capa_analysis_ready(OLD.root_cause_method,OLD.analysis_data,OLD.analysis_summary,
      OLD.verified_root_cause,OLD.other_method_name)
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR length(btrim(NEW.plan_summary))<1 OR NEW.planned_by_user_id IS DISTINCT FROM actor
    OR NEW.planned_at IS NULL OR NEW.planned_at<OLD.analysis_started_at
    OR (to_jsonb(NEW)-ARRAY['state','plan_summary','planned_by_user_id','planned_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','plan_summary','planned_by_user_id','planned_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA planning transition is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF implementing THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'implement'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=OLD.id
      AND a.tenant_id=OLD.tenant_id AND a.unit_id=OLD.unit_id AND a.state='open')
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS DISTINCT FROM actor
    OR NEW.implementation_started_at IS NULL OR NEW.implementation_started_at<OLD.planned_at
    OR (to_jsonb(NEW)-ARRAY['state','implementation_started_by_user_id','implementation_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','implementation_started_by_user_id','implementation_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA implementation start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF reviewing THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'review'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=OLD.id
      AND a.tenant_id=OLD.tenant_id AND a.unit_id=OLD.unit_id AND a.state IN ('completed','verified'))
    OR EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=OLD.id
      AND a.tenant_id=OLD.tenant_id AND a.unit_id=OLD.unit_id AND a.state IN ('open','in_progress'))
    OR NEW.review_started_by_user_id IS DISTINCT FROM actor
    OR NEW.review_started_at IS NULL OR NEW.review_started_at<OLD.implementation_started_at
    OR (to_jsonb(NEW)-ARRAY['state','review_started_by_user_id','review_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','review_started_by_user_id','review_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA effectiveness review start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF effective_decision THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'assess'
    OR NOT qms_has_capability('capa.review',NEW.unit_id)
    OR NEW.effective_by_user_id IS DISTINCT FROM actor OR NEW.effective_at IS NULL
    OR NEW.effective_at<OLD.review_started_at
    OR NOT EXISTS(SELECT 1 FROM qms_capa_effectiveness_reviews r WHERE r.capa_id=OLD.id
      AND r.tenant_id=OLD.tenant_id AND r.unit_id=OLD.unit_id AND r.decision='effective'
      AND r.reviewer_user_id=actor AND r.reviewed_at=NEW.effective_at)
    OR (to_jsonb(NEW)-ARRAY['state','effective_by_user_id','effective_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','effective_by_user_id','effective_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA effective decision is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF replan_decision THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'assess'
    OR NOT qms_has_capability('capa.review',NEW.unit_id)
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NOT EXISTS(SELECT 1 FROM qms_capa_effectiveness_reviews r WHERE r.capa_id=OLD.id
      AND r.tenant_id=OLD.tenant_id AND r.unit_id=OLD.unit_id AND r.decision='ineffective'
      AND r.reviewer_user_id=actor AND r.reviewed_at>=OLD.review_started_at)
    OR (to_jsonb(NEW)-ARRAY['state','implementation_started_by_user_id','implementation_started_at',
      'review_started_by_user_id','review_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','implementation_started_by_user_id','implementation_started_at',
      'review_started_by_user_id','review_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA replan decision is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF closing THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'close'
    OR NOT qms_has_capability('capa.review',NEW.unit_id)
    OR NEW.closed_by_user_id IS DISTINCT FROM actor OR NEW.closed_at IS NULL
    OR NEW.closed_at<OLD.effective_at OR length(btrim(NEW.closure_notes))<1
    OR (to_jsonb(NEW)-ARRAY['state','closed_by_user_id','closed_at','closure_notes','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','closed_by_user_id','closed_at','closure_notes','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA closure is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF OLD.state='action_planned' AND NEW.state='action_planned' THEN
   IF (current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'action'
      OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
      OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL)
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR (to_jsonb(NEW)-ARRAY['row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA action mutation is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF OLD.state='implementation' AND NEW.state='implementation' THEN
   IF current_setting('app.capa_analysis_command',true) NOT IN ('progress','verify')
    OR NOT (qms_has_capability('capa.manage',NEW.unit_id) OR qms_has_capability('capa.review',NEW.unit_id))
    OR (to_jsonb(NEW)-ARRAY['row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA action progress is invalid' USING ERRCODE='23514';
   END IF;
  ELSE
   IF OLD.state<>'analysis' OR NEW.root_cause_method IS DISTINCT FROM OLD.root_cause_method
    OR NEW.analysis_started_by_user_id IS DISTINCT FROM OLD.analysis_started_by_user_id
    OR NEW.analysis_started_at IS DISTINCT FROM OLD.analysis_started_at
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL THEN
    RAISE EXCEPTION 'CAPA analysis identity is immutable' USING ERRCODE='23514';
   END IF;
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'edit' THEN
    RAISE EXCEPTION 'CAPA analysis edits require a controlled command' USING ERRCODE='23514';
   END IF;
  END IF;
 END IF;
 IF NEW.state IN ('analysis','action_planned','implementation','effectiveness_review','effective','closed') THEN
  IF NOT qms_capa_analysis_valid(NEW.root_cause_method,NEW.analysis_data)
   OR (NEW.root_cause_method<>'other' AND NEW.other_method_name<>'') THEN
   RAISE EXCEPTION 'invalid CAPA analysis structure' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.state IN ('action_planned','implementation','effectiveness_review','effective','closed') AND (NOT qms_capa_analysis_ready(NEW.root_cause_method,NEW.analysis_data,
  NEW.analysis_summary,NEW.verified_root_cause,NEW.other_method_name) OR length(btrim(NEW.plan_summary))<1
  OR NEW.planned_by_user_id IS NULL OR NEW.planned_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA planned state is incomplete' USING ERRCODE='23514';
 END IF;
 IF NEW.state IN ('implementation','effectiveness_review','effective','closed') AND (NEW.implementation_started_by_user_id IS NULL
  OR NEW.implementation_started_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA implementation stamp missing' USING ERRCODE='23514';
 END IF;
 IF NEW.state IN ('effectiveness_review','effective','closed') AND (NEW.review_started_by_user_id IS NULL OR NEW.review_started_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA review stamp missing' USING ERRCODE='23514';
 END IF;
 IF NEW.state IN ('effective','closed') AND (NEW.effective_by_user_id IS NULL OR NEW.effective_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA effective stamp missing' USING ERRCODE='23514';
 END IF;
 IF NEW.state='closed' AND (NEW.closed_by_user_id IS NULL OR NEW.closed_at IS NULL OR length(btrim(NEW.closure_notes))<1) THEN
  RAISE EXCEPTION 'CAPA closure stamp missing' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
""")


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_capas DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_effectiveness_reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capa_effectiveness_reviews)
  OR EXISTS(SELECT 1 FROM qms_capas WHERE state IN ('effective','closed'))
  OR EXISTS(SELECT 1 FROM audit_events WHERE action IN ('capa.effectiveness_decided','capa.effectiveness_recorded','capa.closed')) THEN
  RAISE EXCEPTION 'cannot discard CAPA effectiveness or closure history';
 END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_effectiveness_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capas ENABLE ROW LEVEL SECURITY;
DROP TABLE qms_capa_effectiveness_reviews;
DROP FUNCTION validate_qms_capa_effectiveness_review();
DROP FUNCTION apply_qms_capa_effectiveness_decision();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated','capa.action_transitioned','capa.implementation_started','capa.effectiveness_review_started'));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_close_stamp_check;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_effective_stamp_check;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_review_start_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_review_start_stamp_check CHECK(
 (state IN ('draft','analysis','action_planned','implementation') AND review_started_by_user_id IS NULL AND review_started_at IS NULL)
 OR (state='effectiveness_review' AND review_started_by_user_id IS NOT NULL AND review_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_implementation_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_implementation_stamp_check CHECK(
 (state IN ('draft','analysis','action_planned') AND implementation_started_by_user_id IS NULL AND implementation_started_at IS NULL)
 OR (state IN ('implementation','effectiveness_review') AND implementation_started_by_user_id IS NOT NULL AND implementation_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_plan_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_plan_stamp_check CHECK(
 (state IN ('draft','analysis') AND plan_summary='' AND planned_by_user_id IS NULL AND planned_at IS NULL)
 OR (state IN ('action_planned','implementation','effectiveness_review') AND length(btrim(plan_summary))>0 AND planned_by_user_id IS NOT NULL AND planned_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_analysis_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_analysis_stamp_check CHECK(
 (state='draft' AND analysis_started_by_user_id IS NULL AND analysis_started_at IS NULL)
 OR (state IN ('analysis','action_planned','implementation','effectiveness_review') AND analysis_started_by_user_id IS NOT NULL AND analysis_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_state_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_state_check CHECK(state IN ('draft','analysis','action_planned','implementation','effectiveness_review'));
CREATE OR REPLACE FUNCTION validate_qms_capa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; origin_code text; origin_state text; starting boolean; planning boolean; implementing boolean; reviewing boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
    OR NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL THEN
   RAISE EXCEPTION 'CAPA must start as blank draft by current actor' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=NEW.process_id AND p.tenant_id=NEW.tenant_id
    AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'CAPA requires active scoped process' USING ERRCODE='23514';
  END IF;
  IF NEW.owner_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d
    WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA owner must be active member' USING ERRCODE='23514';
  END IF;
  IF NEW.source_type='ncr' THEN
   SELECT n.code,n.state INTO origin_code,origin_state FROM qms_nonconformities n
    WHERE n.id=NEW.source_ncr_id AND n.tenant_id=NEW.tenant_id AND n.unit_id=NEW.unit_id AND n.state<>'cancelled';
  ELSIF NEW.source_type='risk' THEN
   SELECT r.code,r.state INTO origin_code,origin_state FROM qms_risks r
    WHERE r.id=NEW.source_risk_id AND r.tenant_id=NEW.tenant_id AND r.unit_id=NEW.unit_id AND r.state<>'cancelled';
  END IF;
  IF NEW.source_type<>'other' AND (origin_code IS NULL OR NEW.source_code IS DISTINCT FROM origin_code
    OR NEW.source_state IS DISTINCT FROM origin_state) THEN
   RAISE EXCEPTION 'CAPA origin is invalid or snapshot differs' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.code,NEW.source_type,
    NEW.source_ncr_id,NEW.source_risk_id,NEW.source_code,NEW.source_state,
    NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.code,OLD.source_type,
    OLD.source_ncr_id,OLD.source_risk_id,OLD.source_code,OLD.source_state,
    OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'CAPA identity, provenance or version invalid' USING ERRCODE='23514';
  END IF;
  IF NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id AND NEW.owner_user_id IS NOT NULL
   AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d
    WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA owner must be active member' USING ERRCODE='23514';
  END IF;
  starting:=OLD.state='draft' AND NEW.state='analysis';
  planning:=OLD.state='analysis' AND NEW.state='action_planned';
  implementing:=OLD.state='action_planned' AND NEW.state='implementation';
  reviewing:=OLD.state='implementation' AND NEW.state='effectiveness_review';
  IF NEW.state IS DISTINCT FROM OLD.state AND NOT (starting OR planning OR implementing OR reviewing) THEN
   RAISE EXCEPTION 'invalid CAPA analysis transition' USING ERRCODE='23514';
  END IF;
  IF OLD.state='draft' AND NOT starting THEN
   IF NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL THEN
    RAISE EXCEPTION 'analysis requires a transition' USING ERRCODE='23514';
   END IF;
  ELSIF starting THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'start' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NEW.root_cause_method IS NULL OR NEW.analysis_data IS DISTINCT FROM qms_capa_analysis_scaffold(NEW.root_cause_method)
    OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>'' OR NEW.other_method_name<>''
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NEW.analysis_started_by_user_id IS DISTINCT FROM actor OR NEW.analysis_started_at IS NULL
    OR NEW.analysis_started_at<OLD.created_at OR NEW.root_cause_method IS DISTINCT FROM OLD.root_cause_method
    OR (to_jsonb(NEW)-ARRAY['state','analysis_data','analysis_started_by_user_id','analysis_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','analysis_data','analysis_started_by_user_id','analysis_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA analysis start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF planning THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'plan'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT qms_capa_analysis_ready(OLD.root_cause_method,OLD.analysis_data,OLD.analysis_summary,
      OLD.verified_root_cause,OLD.other_method_name)
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR length(btrim(NEW.plan_summary))<1 OR NEW.planned_by_user_id IS DISTINCT FROM actor
    OR NEW.planned_at IS NULL OR NEW.planned_at<OLD.analysis_started_at
    OR (to_jsonb(NEW)-ARRAY['state','plan_summary','planned_by_user_id','planned_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','plan_summary','planned_by_user_id','planned_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA planning transition is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF implementing THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'implement'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=OLD.id
      AND a.tenant_id=OLD.tenant_id AND a.unit_id=OLD.unit_id AND a.state='open')
    OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS DISTINCT FROM actor
    OR NEW.implementation_started_at IS NULL OR NEW.implementation_started_at<OLD.planned_at
    OR (to_jsonb(NEW)-ARRAY['state','implementation_started_by_user_id','implementation_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','implementation_started_by_user_id','implementation_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA implementation start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF reviewing THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'review'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=OLD.id
      AND a.tenant_id=OLD.tenant_id AND a.unit_id=OLD.unit_id AND a.state IN ('completed','verified'))
    OR EXISTS(SELECT 1 FROM qms_capa_actions a WHERE a.capa_id=OLD.id
      AND a.tenant_id=OLD.tenant_id AND a.unit_id=OLD.unit_id AND a.state IN ('open','in_progress'))
    OR NEW.review_started_by_user_id IS DISTINCT FROM actor
    OR NEW.review_started_at IS NULL OR NEW.review_started_at<OLD.implementation_started_at
    OR (to_jsonb(NEW)-ARRAY['state','review_started_by_user_id','review_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','review_started_by_user_id','review_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA effectiveness review start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF OLD.state='action_planned' AND NEW.state='action_planned' THEN
   IF (current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'action'
      OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
      OR NEW.review_started_by_user_id IS NOT NULL OR NEW.review_started_at IS NOT NULL)
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR (to_jsonb(NEW)-ARRAY['row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA action mutation is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF OLD.state='implementation' AND NEW.state='implementation' THEN
   IF current_setting('app.capa_analysis_command',true) NOT IN ('progress','verify')
    OR NOT (qms_has_capability('capa.manage',NEW.unit_id) OR qms_has_capability('capa.review',NEW.unit_id))
    OR (to_jsonb(NEW)-ARRAY['row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA action progress is invalid' USING ERRCODE='23514';
   END IF;
  ELSE
   IF OLD.state<>'analysis' OR NEW.root_cause_method IS DISTINCT FROM OLD.root_cause_method
    OR NEW.analysis_started_by_user_id IS DISTINCT FROM OLD.analysis_started_by_user_id
    OR NEW.analysis_started_at IS DISTINCT FROM OLD.analysis_started_at
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL THEN
    RAISE EXCEPTION 'CAPA analysis identity is immutable' USING ERRCODE='23514';
   END IF;
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'edit' THEN
    RAISE EXCEPTION 'CAPA analysis edits require a controlled command' USING ERRCODE='23514';
   END IF;
  END IF;
 END IF;
 IF NEW.state IN ('analysis','action_planned','implementation','effectiveness_review') THEN
  IF NOT qms_capa_analysis_valid(NEW.root_cause_method,NEW.analysis_data)
   OR (NEW.root_cause_method<>'other' AND NEW.other_method_name<>'') THEN
   RAISE EXCEPTION 'invalid CAPA analysis structure' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.state IN ('action_planned','implementation','effectiveness_review') AND (NOT qms_capa_analysis_ready(NEW.root_cause_method,NEW.analysis_data,
  NEW.analysis_summary,NEW.verified_root_cause,NEW.other_method_name) OR length(btrim(NEW.plan_summary))<1
  OR NEW.planned_by_user_id IS NULL OR NEW.planned_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA planned state is incomplete' USING ERRCODE='23514';
 END IF;
 IF NEW.state IN ('implementation','effectiveness_review') AND (NEW.implementation_started_by_user_id IS NULL
  OR NEW.implementation_started_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA implementation stamp missing' USING ERRCODE='23514';
 END IF;
 IF NEW.state='effectiveness_review' AND (NEW.review_started_by_user_id IS NULL OR NEW.review_started_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA review stamp missing' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
ALTER TABLE qms_capas DROP COLUMN closure_notes;
ALTER TABLE qms_capas DROP COLUMN closed_at;
ALTER TABLE qms_capas DROP COLUMN closed_by_user_id;
ALTER TABLE qms_capas DROP COLUMN effective_at;
ALTER TABLE qms_capas DROP COLUMN effective_by_user_id;

""")
