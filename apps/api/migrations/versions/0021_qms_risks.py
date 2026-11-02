# ruff: noqa: E501
"""Tenant-scoped risks and opportunities with explicit review authority."""

from alembic import op

revision = "0021_qms_risks"
down_revision = "0020_control_evidence_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read')));
$$;

ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed'));
""")
    op.execute(r"""
CREATE TABLE qms_risks (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, process_id uuid NOT NULL,
 code varchar(40) NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 40),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 risk_type varchar(20) NOT NULL CHECK(risk_type IN ('risk','opportunity')),
 category varchar(20) NOT NULL CHECK(category IN ('strategic','operational','process','supplier','document','customer','security','other')),
 source varchar(200) NOT NULL DEFAULT '',
 description text NOT NULL CHECK(length(btrim(description)) BETWEEN 1 AND 4000),
 cause text NOT NULL DEFAULT '' CHECK(length(cause)<=4000),
 potential_effect text NOT NULL DEFAULT '' CHECK(length(potential_effect)<=4000),
 benefit text NOT NULL DEFAULT '' CHECK(length(benefit)<=4000),
 opportunity_action text NOT NULL DEFAULT '' CHECK(length(opportunity_action)<=4000),
 mitigation_plan text NOT NULL DEFAULT '' CHECK(length(mitigation_plan)<=4000),
 closure_notes text NOT NULL DEFAULT '' CHECK(length(closure_notes)<=4000),
 owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 likelihood integer NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
 impact integer NOT NULL CHECK(impact BETWEEN 1 AND 5),
 residual_likelihood integer NOT NULL CHECK(residual_likelihood BETWEEN 1 AND 5),
 residual_impact integer NOT NULL CHECK(residual_impact BETWEEN 1 AND 5),
 response_strategy varchar(20) NOT NULL CHECK(response_strategy IN ('accept','mitigate','transfer','avoid','exploit','enhance','share')),
 target_date date, review_date date,
 state varchar(20) NOT NULL CHECK(state IN ('draft','assessed','action_required','monitoring','closed')),
 scoring_model varchar(40) NOT NULL CHECK(scoring_model='PMC-RISK-5X5-v1'),
 threshold_moderate integer NOT NULL CHECK(threshold_moderate=5),
 threshold_high integer NOT NULL CHECK(threshold_high=10),
 threshold_critical integer NOT NULL CHECK(threshold_critical=16),
 assessed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, assessed_at timestamptz,
 reviewed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, reviewed_at timestamptz,
 closed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, closed_at timestamptz,
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id,process_id),
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((assessed_by_user_id IS NULL)=(assessed_at IS NULL)),
 CHECK((reviewed_by_user_id IS NULL)=(reviewed_at IS NULL)),
 CHECK((closed_by_user_id IS NULL)=(closed_at IS NULL)),
 CHECK((state='draft')=(assessed_at IS NULL)),
 CHECK((state='closed')=(closed_at IS NOT NULL)),
 CHECK(state<>'closed' OR length(btrim(closure_notes))>0)
);
CREATE UNIQUE INDEX qms_risks_code_unique ON qms_risks(tenant_id,lower(code));
CREATE INDEX qms_risks_scope_state ON qms_risks(tenant_id,unit_id,state,code,id);
REVOKE ALL ON qms_risks FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_risks TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_risks FROM pmcloud_app;
ALTER TABLE qms_risks ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_risks FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_risk_read ON qms_risks FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('risks.read',unit_id) OR qms_has_capability('risks.manage',unit_id) OR qms_has_capability('risks.review',unit_id)));
CREATE POLICY qms_risk_insert ON qms_risks FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('risks.manage',unit_id)
 AND state='draft' AND row_version=1 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_risk_update ON qms_risks FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('risks.manage',unit_id) OR qms_has_capability('risks.review',unit_id)))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('risks.manage',unit_id) OR qms_has_capability('risks.review',unit_id)));
CREATE FUNCTION validate_qms_risk() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE command text; actor uuid;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
    OR NEW.assessed_at IS NOT NULL OR NEW.reviewed_at IS NOT NULL OR NEW.closed_at IS NOT NULL THEN
   RAISE EXCEPTION 'risk must be created as an unassessed draft by the current actor' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=NEW.process_id
   AND p.tenant_id=NEW.tenant_id AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'risk requires an active scoped process' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.code,NEW.scoring_model,NEW.threshold_moderate,NEW.threshold_high,NEW.threshold_critical,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.code,OLD.scoring_model,OLD.threshold_moderate,OLD.threshold_high,OLD.threshold_critical,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 THEN
   RAISE EXCEPTION 'risk identity and scoring snapshot are immutable; version must advance once' USING ERRCODE='23514';
  END IF;
  IF OLD.state='closed' THEN
   RAISE EXCEPTION 'closed risks are immutable' USING ERRCODE='23514';
  END IF;
  command:=current_setting('app.risk_workflow',true);
  IF command IN ('transition','review') THEN
   IF NOT qms_has_capability('risks.review',NEW.unit_id) THEN
    RAISE EXCEPTION 'risk review authority required' USING ERRCODE='42501';
   END IF;
   IF (to_jsonb(NEW)-ARRAY['state','assessed_by_user_id','assessed_at','reviewed_by_user_id','reviewed_at','closed_by_user_id','closed_at','closure_notes','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','assessed_by_user_id','assessed_at','reviewed_by_user_id','reviewed_at','closed_by_user_id','closed_at','closure_notes','row_version','updated_at'])
    OR (NEW.state<>'closed' AND NEW.closure_notes IS DISTINCT FROM OLD.closure_notes) THEN
    RAISE EXCEPTION 'risk workflow cannot modify assessment content' USING ERRCODE='23514';
   END IF;
   IF command='review' THEN
    IF OLD.state<>'monitoring' OR NEW.state<>'monitoring' THEN
     RAISE EXCEPTION 'only monitoring risks support recurring review' USING ERRCODE='23514';
    END IF;
   ELSIF NOT ((OLD.state='draft' AND NEW.state='assessed') OR
    (OLD.state='assessed' AND NEW.state IN ('action_required','monitoring')) OR
    (OLD.state='action_required' AND NEW.state='monitoring') OR
    (OLD.state='monitoring' AND NEW.state IN ('action_required','closed'))) THEN
    RAISE EXCEPTION 'invalid risk transition' USING ERRCODE='23514';
   END IF;
   IF OLD.state='draft' THEN
    IF NEW.assessed_by_user_id IS DISTINCT FROM actor OR NEW.assessed_at IS NULL OR
     ROW(NEW.reviewed_by_user_id,NEW.reviewed_at,NEW.closed_by_user_id,NEW.closed_at)
       IS DISTINCT FROM ROW(OLD.reviewed_by_user_id,OLD.reviewed_at,OLD.closed_by_user_id,OLD.closed_at) THEN
     RAISE EXCEPTION 'assessment requires the current actor and time' USING ERRCODE='23514';
    END IF;
   ELSE
    IF ROW(NEW.assessed_by_user_id,NEW.assessed_at) IS DISTINCT FROM ROW(OLD.assessed_by_user_id,OLD.assessed_at)
     OR NEW.reviewed_by_user_id IS DISTINCT FROM actor OR NEW.reviewed_at IS NULL
     OR (NEW.state<>'closed' AND ROW(NEW.closed_by_user_id,NEW.closed_at) IS DISTINCT FROM ROW(OLD.closed_by_user_id,OLD.closed_at)) THEN
     RAISE EXCEPTION 'review requires current actor and cannot replace assessment history' USING ERRCODE='23514';
    END IF;
   END IF;
   IF NEW.state='closed' AND (NEW.closed_by_user_id IS DISTINCT FROM actor OR NEW.closed_at IS NULL OR length(btrim(NEW.closure_notes))=0) THEN
    RAISE EXCEPTION 'closure requires notes and the current actor' USING ERRCODE='23514';
   END IF;
  ELSE
   IF NEW.state IS DISTINCT FROM OLD.state OR
    ROW(NEW.assessed_by_user_id,NEW.assessed_at,NEW.reviewed_by_user_id,NEW.reviewed_at,NEW.closed_by_user_id,NEW.closed_at)
     IS DISTINCT FROM ROW(OLD.assessed_by_user_id,OLD.assessed_at,OLD.reviewed_by_user_id,OLD.reviewed_at,OLD.closed_by_user_id,OLD.closed_at) THEN
    RAISE EXCEPTION 'use risk workflow commands to change status or decision history' USING ERRCODE='23514';
   END IF;
   IF NOT qms_has_capability('risks.manage',NEW.unit_id) THEN
    RAISE EXCEPTION 'risk management authority required' USING ERRCODE='42501';
   END IF;
  END IF;
 END IF;
 IF NEW.owner_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id)
  AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'risk owner must be an active tenant member' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_risk() FROM PUBLIC;
CREATE TRIGGER qms_risk_validate BEFORE INSERT OR UPDATE ON qms_risks
 FOR EACH ROW EXECUTE FUNCTION validate_qms_risk();
""")


def downgrade() -> None:
    # Reject audit-history loss before removing risk data.
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected'));

ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read')));
$$;

DROP TABLE qms_risks; DROP FUNCTION validate_qms_risk();
""")
