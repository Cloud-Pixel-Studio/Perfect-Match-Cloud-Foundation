# ruff: noqa: E501
"""Gate CAPA action planning on completed, verified method evidence."""

from alembic import op

revision = "0030_capa_plan_gate"
down_revision = "0029_capa_fishbone_causes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started'));
ALTER TABLE qms_capas ADD COLUMN plan_summary text NOT NULL DEFAULT '' CHECK(length(plan_summary)<=4000);
ALTER TABLE qms_capas ADD COLUMN planned_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capas ADD COLUMN planned_at timestamptz;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_state_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_state_check CHECK(state IN ('draft','analysis','action_planned'));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_analysis_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_analysis_stamp_check CHECK(
 (state='draft' AND analysis_started_by_user_id IS NULL AND analysis_started_at IS NULL)
 OR (state IN ('analysis','action_planned') AND analysis_started_by_user_id IS NOT NULL AND analysis_started_at IS NOT NULL));
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_plan_stamp_check CHECK(
 (state IN ('draft','analysis') AND plan_summary='' AND planned_by_user_id IS NULL AND planned_at IS NULL)
 OR (state='action_planned' AND length(btrim(plan_summary))>0 AND planned_by_user_id IS NOT NULL AND planned_at IS NOT NULL));
CREATE FUNCTION qms_capa_analysis_ready(method text, data jsonb, summary text, root_cause text, other_name text) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE n integer; seen_blank boolean := false; answer text; dimension text; field text; category jsonb; cause jsonb;
BEGIN
 IF NOT qms_capa_analysis_valid(method,data) OR length(btrim(summary))<1 OR length(btrim(root_cause))<1 THEN RETURN false; END IF;
 IF method='5why' THEN
  FOR n IN 1..5 LOOP
   answer:=data->>('why'||n);
   IF length(btrim(answer))<1 THEN seen_blank:=true;
   ELSIF seen_blank THEN RETURN false;
   END IF;
  END LOOP;
  RETURN length(btrim(data->>'why1'))>0;
 ELSIF method='fishbone' THEN
  FOR category IN SELECT value FROM jsonb_each(data) LOOP
   IF jsonb_typeof(category)='array' THEN
    FOR cause IN SELECT value FROM jsonb_array_elements(category) LOOP
     IF cause->>'confirmed'='true' THEN RETURN true; END IF;
    END LOOP;
   END IF;
  END LOOP;
  RETURN false;
 ELSIF method='is_is_not' THEN
  FOREACH dimension IN ARRAY ARRAY['what','where','when','extent'] LOOP
   FOREACH field IN ARRAY ARRAY['observed','not_observed','distinction'] LOOP
    IF length(btrim(data->dimension->>field))<1 THEN RETURN false; END IF;
   END LOOP;
  END LOOP;
  RETURN true;
 ELSIF method='other' THEN
  RETURN length(btrim(other_name))>0;
 END IF;
 RETURN false;
END; $$;
CREATE OR REPLACE FUNCTION validate_qms_capa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; origin_code text; origin_state text; starting boolean; planning boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
    OR NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL THEN
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
  IF NEW.state IS DISTINCT FROM OLD.state AND NOT (starting OR planning) THEN
   RAISE EXCEPTION 'invalid CAPA analysis transition' USING ERRCODE='23514';
  END IF;
  IF OLD.state='draft' AND NOT starting THEN
   IF NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL THEN
    RAISE EXCEPTION 'analysis requires a transition' USING ERRCODE='23514';
   END IF;
  ELSIF starting THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'start' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NEW.root_cause_method IS NULL OR NEW.analysis_data IS DISTINCT FROM qms_capa_analysis_scaffold(NEW.root_cause_method)
    OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>'' OR NEW.other_method_name<>''
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
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
    OR length(btrim(NEW.plan_summary))<1 OR NEW.planned_by_user_id IS DISTINCT FROM actor
    OR NEW.planned_at IS NULL OR NEW.planned_at<OLD.analysis_started_at
    OR (to_jsonb(NEW)-ARRAY['state','plan_summary','planned_by_user_id','planned_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','plan_summary','planned_by_user_id','planned_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA planning transition is invalid' USING ERRCODE='23514';
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
 IF NEW.state IN ('analysis','action_planned') THEN
  IF NOT qms_capa_analysis_valid(NEW.root_cause_method,NEW.analysis_data)
   OR (NEW.root_cause_method<>'other' AND NEW.other_method_name<>'') THEN
   RAISE EXCEPTION 'invalid CAPA analysis structure' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.state='action_planned' AND (NOT qms_capa_analysis_ready(NEW.root_cause_method,NEW.analysis_data,
  NEW.analysis_summary,NEW.verified_root_cause,NEW.other_method_name) OR length(btrim(NEW.plan_summary))<1
  OR NEW.planned_by_user_id IS NULL OR NEW.planned_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA planned state is incomplete' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
""")


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_capas DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas WHERE state='action_planned')
 OR EXISTS(SELECT 1 FROM audit_events WHERE action='capa.plan_started' OR (resource_type='qms_capa' AND new_values->>'state'='action_planned')) THEN
  RAISE EXCEPTION 'cannot discard CAPA planning or audit history';
 END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capas ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated'));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_plan_stamp_check;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_analysis_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_analysis_stamp_check CHECK(
 (state='draft' AND analysis_started_by_user_id IS NULL AND analysis_started_at IS NULL)
 OR (state='analysis' AND analysis_started_by_user_id IS NOT NULL AND analysis_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_state_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_state_check CHECK(state IN ('draft','analysis'));
DROP FUNCTION qms_capa_analysis_ready(text,jsonb,text,text,text);
CREATE OR REPLACE FUNCTION validate_qms_capa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; origin_code text; origin_state text; starting boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
    OR NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL THEN
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
  IF NEW.state IS DISTINCT FROM OLD.state AND NOT starting THEN
   RAISE EXCEPTION 'invalid CAPA analysis transition' USING ERRCODE='23514';
  END IF;
  IF OLD.state='draft' AND NOT starting THEN
   IF NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL THEN
    RAISE EXCEPTION 'analysis requires a transition' USING ERRCODE='23514';
   END IF;
  ELSIF starting THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'start' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NEW.root_cause_method IS NULL OR NEW.analysis_data IS DISTINCT FROM qms_capa_analysis_scaffold(NEW.root_cause_method)
    OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>'' OR NEW.other_method_name<>''
    OR NEW.analysis_started_by_user_id IS DISTINCT FROM actor OR NEW.analysis_started_at IS NULL
    OR NEW.analysis_started_at<OLD.created_at OR NEW.root_cause_method IS DISTINCT FROM OLD.root_cause_method
    OR (to_jsonb(NEW)-ARRAY['state','analysis_data','analysis_started_by_user_id','analysis_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','analysis_data','analysis_started_by_user_id','analysis_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA analysis start is invalid' USING ERRCODE='23514';
   END IF;
  ELSE
   IF OLD.state<>'analysis' OR NEW.root_cause_method IS DISTINCT FROM OLD.root_cause_method
    OR NEW.analysis_started_by_user_id IS DISTINCT FROM OLD.analysis_started_by_user_id
    OR NEW.analysis_started_at IS DISTINCT FROM OLD.analysis_started_at THEN
    RAISE EXCEPTION 'CAPA analysis identity is immutable' USING ERRCODE='23514';
   END IF;
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'edit' THEN
    RAISE EXCEPTION 'CAPA analysis edits require a controlled command' USING ERRCODE='23514';
   END IF;
  END IF;
 END IF;
 IF NEW.state='analysis' THEN
  IF NOT qms_capa_analysis_valid(NEW.root_cause_method,NEW.analysis_data)
   OR (NEW.root_cause_method<>'other' AND NEW.other_method_name<>'') THEN
   RAISE EXCEPTION 'invalid CAPA analysis structure' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
ALTER TABLE qms_capas DROP COLUMN planned_at;
ALTER TABLE qms_capas DROP COLUMN planned_by_user_id;
ALTER TABLE qms_capas DROP COLUMN plan_summary;
""")
