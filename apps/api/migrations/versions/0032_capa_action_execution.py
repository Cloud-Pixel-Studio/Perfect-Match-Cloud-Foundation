# ruff: noqa: E501
"""Controlled CAPA implementation and independently verified action transitions."""

from alembic import op

revision = "0032_capa_action_execution"
down_revision = "0031_capa_action_register"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated','capa.action_transitioned','capa.implementation_started'));
DROP POLICY qms_capa_update ON qms_capas;
CREATE POLICY qms_capa_update ON qms_capas FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('capa.read',unit_id)
 AND (qms_has_capability('capa.manage',unit_id) OR qms_has_capability('capa.review',unit_id))
 AND (source_type='other' OR (source_type='ncr' AND qms_has_capability('ncr.read',unit_id))
      OR (source_type='risk' AND qms_has_capability('risks.read',unit_id))))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND (qms_has_capability('capa.manage',unit_id) OR qms_has_capability('capa.review',unit_id)));
DROP POLICY qms_capa_action_update ON qms_capa_actions;
CREATE POLICY qms_capa_action_update ON qms_capa_actions FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('capa.manage',unit_id) OR qms_has_capability('capa.review',unit_id))
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_actions.capa_id
  AND c.tenant_id=qms_capa_actions.tenant_id AND c.unit_id=qms_capa_actions.unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('capa.manage',unit_id) OR qms_has_capability('capa.review',unit_id)));
ALTER TABLE qms_capas ADD COLUMN implementation_started_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capas ADD COLUMN implementation_started_at timestamptz;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_state_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_state_check CHECK(state IN ('draft','analysis','action_planned','implementation'));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_analysis_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_analysis_stamp_check CHECK(
 (state='draft' AND analysis_started_by_user_id IS NULL AND analysis_started_at IS NULL)
 OR (state IN ('analysis','action_planned','implementation') AND analysis_started_by_user_id IS NOT NULL AND analysis_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_plan_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_plan_stamp_check CHECK(
 (state IN ('draft','analysis') AND plan_summary='' AND planned_by_user_id IS NULL AND planned_at IS NULL)
 OR (state IN ('action_planned','implementation') AND length(btrim(plan_summary))>0 AND planned_by_user_id IS NOT NULL AND planned_at IS NOT NULL));
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_implementation_stamp_check CHECK(
 (state IN ('draft','analysis','action_planned') AND implementation_started_by_user_id IS NULL AND implementation_started_at IS NULL)
 OR (state='implementation' AND implementation_started_by_user_id IS NOT NULL AND implementation_started_at IS NOT NULL));
ALTER TABLE qms_capa_actions DROP CONSTRAINT qms_capa_actions_state_check;
ALTER TABLE qms_capa_actions ADD CONSTRAINT qms_capa_actions_state_check CHECK(state IN ('open','in_progress','completed','verified','cancelled'));
ALTER TABLE qms_capa_actions ADD COLUMN completed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capa_actions ADD COLUMN completed_at timestamptz;
ALTER TABLE qms_capa_actions ADD COLUMN verified_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capa_actions ADD COLUMN verified_at timestamptz;
ALTER TABLE qms_capa_actions ADD COLUMN verification_notes text NOT NULL DEFAULT '' CHECK(length(verification_notes)<=4000);
ALTER TABLE qms_capa_actions ADD COLUMN cancelled_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE qms_capa_actions ADD COLUMN cancelled_at timestamptz;
ALTER TABLE qms_capa_actions ADD COLUMN cancellation_reason text NOT NULL DEFAULT '' CHECK(length(cancellation_reason)<=500);
ALTER TABLE qms_capa_actions ADD CONSTRAINT qms_capa_actions_stamps_check CHECK(
 (state IN ('open','in_progress') AND completed_by_user_id IS NULL AND completed_at IS NULL
  AND verified_by_user_id IS NULL AND verified_at IS NULL AND verification_notes=''
  AND cancelled_by_user_id IS NULL AND cancelled_at IS NULL AND cancellation_reason='')
 OR (state='completed' AND completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL
  AND verified_by_user_id IS NULL AND verified_at IS NULL AND verification_notes=''
  AND cancelled_by_user_id IS NULL AND cancelled_at IS NULL AND cancellation_reason='')
 OR (state='verified' AND completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL
  AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND length(btrim(verification_notes))>0
  AND cancelled_by_user_id IS NULL AND cancelled_at IS NULL AND cancellation_reason='')
 OR (state='cancelled' AND ((completed_by_user_id IS NULL AND completed_at IS NULL)
    OR (completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL))
  AND verified_by_user_id IS NULL AND verified_at IS NULL AND verification_notes=''
  AND cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL AND length(btrim(cancellation_reason))>0));
CREATE OR REPLACE FUNCTION validate_qms_capa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; origin_code text; origin_state text; starting boolean; planning boolean; implementing boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
    OR NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL THEN
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
  IF NEW.state IS DISTINCT FROM OLD.state AND NOT (starting OR planning OR implementing) THEN
   RAISE EXCEPTION 'invalid CAPA analysis transition' USING ERRCODE='23514';
  END IF;
  IF OLD.state='draft' AND NOT starting THEN
   IF NEW.analysis_data<>'{}'::jsonb OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>''
    OR NEW.other_method_name<>'' OR NEW.analysis_started_by_user_id IS NOT NULL OR NEW.analysis_started_at IS NOT NULL
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL THEN
    RAISE EXCEPTION 'analysis requires a transition' USING ERRCODE='23514';
   END IF;
  ELSIF starting THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'start' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NEW.root_cause_method IS NULL OR NEW.analysis_data IS DISTINCT FROM qms_capa_analysis_scaffold(NEW.root_cause_method)
    OR NEW.analysis_summary<>'' OR NEW.verified_root_cause<>'' OR NEW.other_method_name<>''
    OR NEW.plan_summary<>'' OR NEW.planned_by_user_id IS NOT NULL OR NEW.planned_at IS NOT NULL
    OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL
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
    OR NEW.implementation_started_by_user_id IS DISTINCT FROM actor
    OR NEW.implementation_started_at IS NULL OR NEW.implementation_started_at<OLD.planned_at
    OR (to_jsonb(NEW)-ARRAY['state','implementation_started_by_user_id','implementation_started_at','row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','implementation_started_by_user_id','implementation_started_at','row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA implementation start is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF OLD.state='action_planned' AND NEW.state='action_planned' THEN
   IF (current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'action'
      OR NEW.implementation_started_by_user_id IS NOT NULL OR NEW.implementation_started_at IS NOT NULL)
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
 IF NEW.state IN ('analysis','action_planned','implementation') THEN
  IF NOT qms_capa_analysis_valid(NEW.root_cause_method,NEW.analysis_data)
   OR (NEW.root_cause_method<>'other' AND NEW.other_method_name<>'') THEN
   RAISE EXCEPTION 'invalid CAPA analysis structure' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.state IN ('action_planned','implementation') AND (NOT qms_capa_analysis_ready(NEW.root_cause_method,NEW.analysis_data,
  NEW.analysis_summary,NEW.verified_root_cause,NEW.other_method_name) OR length(btrim(NEW.plan_summary))<1
  OR NEW.planned_by_user_id IS NULL OR NEW.planned_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA planned state is incomplete' USING ERRCODE='23514';
 END IF;
 IF NEW.state='implementation' AND (NEW.implementation_started_by_user_id IS NULL
  OR NEW.implementation_started_at IS NULL) THEN
  RAISE EXCEPTION 'CAPA implementation stamp missing' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION validate_qms_capa_action() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent_state text; command text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 command:=current_setting('app.capa_analysis_command',true);
 SELECT state INTO parent_state FROM qms_capas c WHERE c.id=NEW.capa_id
  AND c.tenant_id=NEW.tenant_id AND c.unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS NULL THEN
  RAISE EXCEPTION 'CAPA action parent is unavailable' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  IF parent_state<>'action_planned' OR command IS DISTINCT FROM 'action'
   OR NOT qms_has_capability('capa.manage',NEW.unit_id)
   OR NEW.state<>'open' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.created_at IS DISTINCT FROM NEW.updated_at
   OR NEW.completed_by_user_id IS NOT NULL OR NEW.completed_at IS NOT NULL
   OR NEW.verified_by_user_id IS NOT NULL OR NEW.verified_at IS NOT NULL OR NEW.verification_notes<>''
   OR NEW.cancelled_by_user_id IS NOT NULL OR NEW.cancelled_at IS NOT NULL OR NEW.cancellation_reason<>'' THEN
   RAISE EXCEPTION 'CAPA action insert is invalid' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM organization_member_directory() d
   WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA action owner must be active member' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.capa_id,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.capa_id,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'CAPA action identity or version invalid' USING ERRCODE='23514';
  END IF;
  IF parent_state='action_planned' AND OLD.state='open' AND NEW.state='open' THEN
   IF command IS DISTINCT FROM 'action' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR NOT EXISTS(SELECT 1 FROM organization_member_directory() d
      WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
    RAISE EXCEPTION 'CAPA action plan edit is invalid' USING ERRCODE='23514';
   END IF;
  ELSIF parent_state='implementation' THEN
   IF (to_jsonb(NEW)-ARRAY['state','row_version','updated_at','completed_by_user_id','completed_at',
     'verified_by_user_id','verified_at','verification_notes','cancelled_by_user_id','cancelled_at','cancellation_reason'])
      IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','row_version','updated_at','completed_by_user_id','completed_at',
     'verified_by_user_id','verified_at','verification_notes','cancelled_by_user_id','cancelled_at','cancellation_reason']) THEN
    RAISE EXCEPTION 'CAPA action plan details are locked' USING ERRCODE='23514';
   END IF;
   IF OLD.state='open' AND NEW.state='in_progress' THEN
    IF command IS DISTINCT FROM 'progress' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
     OR (to_jsonb(NEW)-ARRAY['state','row_version','updated_at'])
        IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','row_version','updated_at']) THEN
     RAISE EXCEPTION 'CAPA action start is invalid' USING ERRCODE='23514';
    END IF;
   ELSIF OLD.state IN ('open','in_progress') AND NEW.state='completed' THEN
    IF command IS DISTINCT FROM 'progress' OR NOT qms_has_capability('capa.manage',NEW.unit_id)
     OR NEW.completed_by_user_id IS DISTINCT FROM actor OR NEW.completed_at IS NULL
     OR NEW.completed_at<OLD.created_at
     OR (to_jsonb(NEW)-ARRAY['state','row_version','updated_at','completed_by_user_id','completed_at'])
        IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','row_version','updated_at','completed_by_user_id','completed_at']) THEN
     RAISE EXCEPTION 'CAPA action completion is invalid' USING ERRCODE='23514';
    END IF;
   ELSIF OLD.state='completed' AND NEW.state='verified' THEN
    IF command IS DISTINCT FROM 'verify' OR NOT qms_has_capability('capa.review',NEW.unit_id)
     OR actor=OLD.completed_by_user_id OR NEW.verified_by_user_id IS DISTINCT FROM actor
     OR NEW.verified_at IS NULL OR NEW.verified_at<OLD.completed_at
     OR length(btrim(NEW.verification_notes))<1
     OR (to_jsonb(NEW)-ARRAY['state','row_version','updated_at','verified_by_user_id','verified_at','verification_notes'])
        IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','row_version','updated_at','verified_by_user_id','verified_at','verification_notes']) THEN
     RAISE EXCEPTION 'CAPA action verification is invalid' USING ERRCODE='23514';
    END IF;
   ELSIF OLD.state IN ('open','in_progress','completed') AND NEW.state='cancelled' THEN
    IF command IS DISTINCT FROM 'verify' OR NOT qms_has_capability('capa.review',NEW.unit_id)
     OR NEW.cancelled_by_user_id IS DISTINCT FROM actor OR NEW.cancelled_at IS NULL
     OR NEW.cancelled_at<OLD.created_at OR length(btrim(NEW.cancellation_reason))<1
     OR (to_jsonb(NEW)-ARRAY['state','row_version','updated_at','cancelled_by_user_id','cancelled_at','cancellation_reason'])
        IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','row_version','updated_at','cancelled_by_user_id','cancelled_at','cancellation_reason']) THEN
     RAISE EXCEPTION 'CAPA action cancellation is invalid' USING ERRCODE='23514';
    END IF;
   ELSE
    RAISE EXCEPTION 'CAPA action transition is invalid' USING ERRCODE='23514';
   END IF;
  ELSE
   RAISE EXCEPTION 'CAPA action stage is locked' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
""")


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_capas DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_actions DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas WHERE state='implementation')
  OR EXISTS(SELECT 1 FROM qms_capa_actions WHERE state<>'open')
  OR EXISTS(SELECT 1 FROM audit_events WHERE action IN ('capa.action_transitioned','capa.implementation_started')) THEN
  RAISE EXCEPTION 'cannot discard CAPA execution or audit history';
 END IF;
END $$;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capas ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated'));
DROP POLICY qms_capa_update ON qms_capas;
CREATE POLICY qms_capa_update ON qms_capas FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('capa.read',unit_id)
 AND qms_has_capability('capa.manage',unit_id)
 AND (source_type='other' OR (source_type='ncr' AND qms_has_capability('ncr.read',unit_id))
      OR (source_type='risk' AND qms_has_capability('risks.read',unit_id))))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('capa.manage',unit_id));
DROP POLICY qms_capa_action_update ON qms_capa_actions;
CREATE POLICY qms_capa_action_update ON qms_capa_actions FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.manage',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_actions.capa_id
  AND c.tenant_id=qms_capa_actions.tenant_id AND c.unit_id=qms_capa_actions.unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.manage',unit_id));
ALTER TABLE qms_capa_actions DROP CONSTRAINT qms_capa_actions_stamps_check;
ALTER TABLE qms_capa_actions DROP CONSTRAINT qms_capa_actions_state_check;
ALTER TABLE qms_capa_actions ADD CONSTRAINT qms_capa_actions_state_check CHECK(state='open');
CREATE OR REPLACE FUNCTION validate_qms_capa_action() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; parent_state text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'action'
  OR NOT qms_has_capability('capa.manage',NEW.unit_id) THEN
  RAISE EXCEPTION 'CAPA action requires controlled manage command' USING ERRCODE='23514';
 END IF;
 SELECT state INTO parent_state FROM qms_capas c WHERE c.id=NEW.capa_id
  AND c.tenant_id=NEW.tenant_id AND c.unit_id=NEW.unit_id FOR UPDATE;
 IF parent_state IS DISTINCT FROM 'action_planned' THEN
  RAISE EXCEPTION 'CAPA action requires planned parent' USING ERRCODE='23514';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM organization_member_directory() d
  WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
  RAISE EXCEPTION 'CAPA action owner must be active member' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'open' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.created_at IS DISTINCT FROM NEW.updated_at THEN
   RAISE EXCEPTION 'CAPA action must start open by current actor' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.capa_id,NEW.state,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.capa_id,OLD.state,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'CAPA action identity or version invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
ALTER TABLE qms_capa_actions DROP COLUMN cancellation_reason;
ALTER TABLE qms_capa_actions DROP COLUMN cancelled_at;
ALTER TABLE qms_capa_actions DROP COLUMN cancelled_by_user_id;
ALTER TABLE qms_capa_actions DROP COLUMN verification_notes;
ALTER TABLE qms_capa_actions DROP COLUMN verified_at;
ALTER TABLE qms_capa_actions DROP COLUMN verified_by_user_id;
ALTER TABLE qms_capa_actions DROP COLUMN completed_at;
ALTER TABLE qms_capa_actions DROP COLUMN completed_by_user_id;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_implementation_stamp_check;
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_plan_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_plan_stamp_check CHECK(
 (state IN ('draft','analysis') AND plan_summary='' AND planned_by_user_id IS NULL AND planned_at IS NULL)
 OR (state='action_planned' AND length(btrim(plan_summary))>0 AND planned_by_user_id IS NOT NULL AND planned_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_analysis_stamp_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_analysis_stamp_check CHECK(
 (state='draft' AND analysis_started_by_user_id IS NULL AND analysis_started_at IS NULL)
 OR (state IN ('analysis','action_planned') AND analysis_started_by_user_id IS NOT NULL AND analysis_started_at IS NOT NULL));
ALTER TABLE qms_capas DROP CONSTRAINT qms_capas_state_check;
ALTER TABLE qms_capas ADD CONSTRAINT qms_capas_state_check CHECK(state IN ('draft','analysis','action_planned'));
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
  ELSIF OLD.state='action_planned' AND NEW.state='action_planned' THEN
   IF current_setting('app.capa_analysis_command',true) IS DISTINCT FROM 'action'
    OR NOT qms_has_capability('capa.manage',NEW.unit_id)
    OR (to_jsonb(NEW)-ARRAY['row_version','updated_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['row_version','updated_at']) THEN
    RAISE EXCEPTION 'CAPA action mutation is invalid' USING ERRCODE='23514';
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
ALTER TABLE qms_capas DROP COLUMN implementation_started_at;
ALTER TABLE qms_capas DROP COLUMN implementation_started_by_user_id;

""")
