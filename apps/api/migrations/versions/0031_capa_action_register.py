# ruff: noqa: E501
"""Tenant-scoped CAPA action register with controlled parent versions."""

from alembic import op

revision = "0031_capa_action_register"
down_revision = "0030_capa_plan_gate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started','capa.action_created','capa.action_updated'));
CREATE TABLE qms_capa_actions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL,
 capa_id uuid NOT NULL,
 title varchar(160) NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 160),
 description text NOT NULL CHECK(length(btrim(description)) BETWEEN 1 AND 4000),
 owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 due_date date NOT NULL,
 state varchar(24) NOT NULL DEFAULT 'open' CHECK(state='open'),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(capa_id,tenant_id,unit_id) REFERENCES qms_capas(id,tenant_id,unit_id) ON DELETE RESTRICT
);
CREATE INDEX qms_capa_actions_parent ON qms_capa_actions(tenant_id,unit_id,capa_id,due_date,id);
REVOKE ALL ON qms_capa_actions FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_capa_actions TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_capa_actions FROM pmcloud_app;
ALTER TABLE qms_capa_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_actions FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_capa_action_read ON qms_capa_actions FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_actions.capa_id
  AND c.tenant_id=qms_capa_actions.tenant_id AND c.unit_id=qms_capa_actions.unit_id));
CREATE POLICY qms_capa_action_insert ON qms_capa_actions FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.manage',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_actions.capa_id
  AND c.tenant_id=qms_capa_actions.tenant_id AND c.unit_id=qms_capa_actions.unit_id));
CREATE POLICY qms_capa_action_update ON qms_capa_actions FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.manage',unit_id)
 AND EXISTS(SELECT 1 FROM qms_capas c WHERE c.id=qms_capa_actions.capa_id
  AND c.tenant_id=qms_capa_actions.tenant_id AND c.unit_id=qms_capa_actions.unit_id))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.manage',unit_id));
CREATE FUNCTION validate_qms_capa_action() RETURNS trigger
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
CREATE TRIGGER qms_capa_action_validate BEFORE INSERT OR UPDATE ON qms_capa_actions
 FOR EACH ROW EXECUTE FUNCTION validate_qms_capa_action();
CREATE FUNCTION bump_qms_capa_action_parent() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 UPDATE qms_capas SET row_version=row_version+1,
  updated_at=greatest(clock_timestamp(),updated_at+interval '1 microsecond')
 WHERE id=NEW.capa_id AND tenant_id=NEW.tenant_id AND unit_id=NEW.unit_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPA parent update denied' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_capa_action_parent_version AFTER INSERT OR UPDATE ON qms_capa_actions
 FOR EACH ROW EXECUTE FUNCTION bump_qms_capa_action_parent();
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
""")


def downgrade() -> None:
    op.execute(r"""
ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capa_actions DISABLE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capa_actions)
  OR EXISTS(SELECT 1 FROM audit_events WHERE action IN ('capa.action_created','capa.action_updated')) THEN
  RAISE EXCEPTION 'cannot discard CAPA actions or audit history';
 END IF;
END $$;
ALTER TABLE qms_capa_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
DROP TABLE qms_capa_actions;
DROP FUNCTION validate_qms_capa_action();
DROP FUNCTION bump_qms_capa_action_parent();
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated','capa.analysis_started','capa.analysis_updated','capa.plan_started'));
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
